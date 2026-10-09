#!/usr/bin/env python3
"""Summarize PoC 005 results into summary.json and summary.md.

Usage: python3 summarize.py [RESULTS_DIR]

RESULTS_DIR defaults to results/ next to this script. Reads RESULTS_DIR/raw/inputs.jsonl and
RESULTS_DIR/raw/generations.jsonl, and writes RESULTS_DIR/summary.json and summary.md.
Scoring (clean stop, four sections, complete, unsupported numbers, exemplar leak, loops, section
count, END lines) is imported from PoC 003's summarize.py so the PoCs measure the same way. The
one new measure, thin sections, is defined here.
The hypotheses and the decision rule are the ones registered in README.md; change them there
first, as a deviation, never only here.
"""
import importlib.util
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
POC003 = HERE.parent / "003-qwen-sampler-stop-behavior"
_spec = importlib.util.spec_from_file_location("poc003_summarize", POC003 / "summarize.py")
p3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p3)

SHIPPED, INSERT, SUPPRESS = "b-shipped", "b-insert-heading", "b-suppress-end"
THIN_CHARS = 15
LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\[[ xX]?\]|\d+[.)])\s*", re.M)


def section_bodies(text):
    """The text under each of the four headings, by first occurrence, as in PoC 003's check."""
    heads = list(p3.HEADING.finditer(text))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.setdefault(m.group(1).lower(), text[m.end():end])
    return out


def thin(text):
    """True if any section that is present has fewer than THIN_CHARS characters of content,
    after list markers and whitespace are removed."""
    return any(len(LIST_MARKER.sub("", body).strip()) < THIN_CHARS for body in section_bodies(text).values())


def score(gen, source):
    sc = p3.score(gen, source)
    sc["thin"] = thin(gen["text"])
    sc["inserted"] = len(gen.get("inserted", []))
    sc["any_inserted"] = sc["inserted"] > 0
    return sc


def decide(s, complete_ci):
    gain = s[INSERT]["complete"] - s[SHIPPED]["complete"]
    criteria = {
        "c1_complete_gain_30": gain >= 0.30 and complete_ci[0] > 0,
        "c2_clean_at_least_90pct": s[INSERT]["clean"] >= 0.90,
        "c3_unsupported_within_5pts": s[INSERT]["any_unsupported"] <= s[SHIPPED]["any_unsupported"] + 0.05,
        "c4_thin_at_most_10pct": s[INSERT]["thin"] <= 0.10,
        "c5_leak_at_most_5pct": s[INSERT]["leak"] <= 0.05,
    }
    if gain < 0.20:
        verdict = "reject: no gain"
    elif all(criteria.values()):
        verdict = "adopt"
    elif criteria["c1_complete_gain_30"] and not (
        criteria["c3_unsupported_within_5pts"] and criteria["c4_thin_at_most_10pct"] and criteria["c5_leak_at_most_5pct"]
    ):
        verdict = "reject: trade-off"
    else:
        failing = [k for k, v in criteria.items() if not v]
        verdict = "inconclusive (fails " + ", ".join(failing) + ")"
    return {"complete_gain_insert_minus_shipped": gain, "criteria": criteria, "verdict": verdict}


def hypotheses(s):
    return {
        "H1_insert_complete_80": s[INSERT]["complete"] >= 0.80,
        "H2_suppress_complete_80": s[SUPPRESS]["complete"] >= 0.80,
        "H3_unsupported_within_5pts": all(
            s[arm]["any_unsupported"] <= s[SHIPPED]["any_unsupported"] + 0.05 for arm in (INSERT, SUPPRESS)
        ),
    }


def reproducibility(gens):
    """Token-for-token match of b-shipped with PoC 003's b-qwen-recipe (same inputs and seeds)."""
    path = POC003 / "results" / "raw" / "generations.jsonl"
    if not path.exists():
        return None
    old = {(g["doc"], g["seed"]): g["tokens"] for g in p3.load_jsonl(path) if g["arm"] == "b-qwen-recipe"}
    mine = [g for g in gens if g["arm"] == SHIPPED]
    return {"identical": sum(old.get((g["doc"], g["seed"])) == g["tokens"] for g in mine), "of": len(mine)}


# EXPLORATORY: added after the run, not registered. Nothing below feeds the verdict.
GENERIC_VERB = re.compile(
    r"^(ensure|review|confirm|verify|monitor|maintain|comply|coordinate|check)\b", re.I)


def action_item_lines(text):
    body = section_bodies(text).get("action items", "")
    return [LIST_MARKER.sub("", l).strip() for l in body.splitlines() if LIST_MARKER.sub("", l).strip()]


def exploratory(gens, by_doc, arm_order):
    out = {}
    for arm in (INSERT, SUPPRESS):
        cmp = Counter()
        for d in by_doc:
            a = sum(x["complete"] for x in by_doc[d][arm])
            b = sum(x["complete"] for x in by_doc[d][SHIPPED])
            cmp["higher" if a > b else "equal" if a == b else "lower"] += 1
        out[f"docs_{arm}_vs_shipped"] = dict(cmp)
    out["docs_with_no_complete_output"] = {
        arm: sum(not any(x["complete"] for x in by_doc[d][arm]) for d in by_doc) for arm in arm_order}
    out["inserted_by_heading"] = dict(Counter(
        h["heading"] for g in gens if g["arm"] == INSERT for h in g.get("inserted", [])))
    sup_cap = [g for g in gens if g["arm"] == SUPPRESS and g["stop"] != "eos"]
    out["suppress_cap_sections_found"] = dict(sorted(Counter(
        len({m.group(1).lower() for m in p3.HEADING.finditer(g["text"])}) for g in sup_cap).items()))

    def generic(gs):
        lines = [l for g in gs for l in action_item_lines(g["text"])]
        return {"lines": len(lines), "generic_verb": sum(bool(GENERIC_VERB.match(l)) for l in lines)}

    ins = [g for g in gens if g["arm"] == INSERT]
    forced = [g for g in ins if any(h["heading"] == "Action Items" for h in g.get("inserted", []))]
    written = [g for g in gens if g["arm"] in (SHIPPED, INSERT) and g not in forced
               and "action items" in section_bodies(g["text"])]
    out["action_items_generic_verb"] = {"inserted_heading": generic(forced), "model_written_heading": generic(written)}
    return out


def pct(x):
    return f"{100 * x:.0f}%"


def ci_line(label, bs):
    return (f"- {label}: {100 * bs['diff']:+.1f} points, "
            f"95% CI [{100 * bs['ci95'][0]:+.1f}, {100 * bs['ci95'][1]:+.1f}]")


def main():
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
    raw = results / "raw"
    sources = {r["doc"]: r["input"] for r in p3.load_jsonl(raw / "inputs.jsonl")}
    gens = p3.load_jsonl(raw / "generations.jsonl")
    arm_order = [a["name"] for a in json.loads((HERE / "arms.json").read_text())]

    rows = defaultdict(list)
    by_doc = defaultdict(lambda: defaultdict(list))
    for g in gens:
        sc = score(g, sources[g["doc"]])
        rows[g["arm"]].append(sc)
        by_doc[g["doc"]][g["arm"]].append(sc)

    keys = ("clean", "cap", "four", "complete", "any_unsupported", "leak", "loop", "end_marker", "thin", "any_inserted")
    s = {}
    for arm in arm_order:
        r = rows[arm]
        speeds = [x["tok_s"] for x in r if x["tok_s"]]
        s[arm] = {
            "n": len(r),
            **{k: p3.rate(r, k) for k in keys},
            "inserted_headings": dict(sorted(Counter(x["inserted"] for x in r).items())),
            "sections_found": dict(sorted(Counter(x["sections_found"] for x in r).items())),
            "median_tokens": statistics.median(x["tokens"] for x in r) if r else None,
            "median_decode_tok_s": statistics.median(speeds) if speeds else None,
        }

    bs = {
        "complete_insert_minus_shipped": p3.bootstrap_diff(by_doc, "complete", INSERT, SHIPPED),
        "complete_suppress_minus_shipped": p3.bootstrap_diff(by_doc, "complete", SUPPRESS, SHIPPED),
        "unsupported_insert_minus_shipped": p3.bootstrap_diff(by_doc, "any_unsupported", INSERT, SHIPPED),
        "unsupported_suppress_minus_shipped": p3.bootstrap_diff(by_doc, "any_unsupported", SUPPRESS, SHIPPED),
    }
    decision = decide(s, bs["complete_insert_minus_shipped"]["ci95"])
    hyp = hypotheses(s)
    stops = {arm: dict(Counter(g["stop"] for g in gens if g["arm"] == arm)) for arm in arm_order}
    repro = reproducibility(gens)
    explore = exploratory(gens, by_doc, arm_order)

    summary = {
        "generations": len(gens),
        "documents": len(by_doc),
        "arms": s,
        "stops": stops,
        "bootstrap": bs,
        "hypotheses": hyp,
        "decision": decision,
        "reproduces_poc003_b_tokens": repro,
        "exploratory_not_registered": explore,
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    lines = [
        "# PoC 005 summary",
        "",
        f"{len(gens)} generations, {len(by_doc)} documents. Rates are shares of generations per arm.",
        "",
        "| Arm | n | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Thin section | Exemplar leak | Loop | END line | Headings inserted (0/1/2/3) | Median tokens | Median decode tok/s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in arm_order:
        a = s[arm]
        tok_s = f"{a['median_decode_tok_s']:.1f}" if a["median_decode_tok_s"] else "n/a"
        ins = " / ".join(str(a["inserted_headings"].get(k, 0)) for k in (0, 1, 2, 3))
        lines.append(
            f"| {arm} | {a['n']} | {pct(a['clean'])} | {pct(a['cap'])} | {pct(a['four'])} | {pct(a['complete'])} "
            f"| {pct(a['any_unsupported'])} | {pct(a['thin'])} | {pct(a['leak'])} | {pct(a['loop'])} "
            f"| {pct(a['end_marker'])} | {ins} | {a['median_tokens']} | {tok_s} |"
        )
    lines += [
        "",
        "Document-level bootstrap (10,000 resamples, seed 0):",
        "",
        ci_line("Complete, b-insert-heading minus b-shipped", bs["complete_insert_minus_shipped"]),
        ci_line("Complete, b-suppress-end minus b-shipped", bs["complete_suppress_minus_shipped"]),
        ci_line("Any unsupported number, b-insert-heading minus b-shipped", bs["unsupported_insert_minus_shipped"]),
        ci_line("Any unsupported number, b-suppress-end minus b-shipped", bs["unsupported_suppress_minus_shipped"]),
        "",
        "## Hypotheses",
        "",
        *[f"- {k}: {'holds' if v else 'does not hold'}" for k, v in hyp.items()],
        "",
        "## Decision rule (b-insert-heading vs b-shipped, first match wins)",
        "",
        *[f"- {k}: {'pass' if v else 'fail'}" for k, v in decision["criteria"].items()],
        "",
        f"Verdict: **{decision['verdict']}**",
        "",
        "## Reproducibility check against PoC 003",
        "",
    ]
    if repro is None:
        lines.append("PoC 003's generations not found; check skipped.")
    else:
        lines.append(f"- b-shipped: {repro['identical']} of {repro['of']} generations token-identical to PoC 003's b-qwen-recipe")
    gv = explore["action_items_generic_verb"]
    lines += [
        "",
        "## Exploratory (added after the run, not registered; does not affect the verdict)",
        "",
        *[f"- Documents, {arm} vs b-shipped on complete count (higher/equal/lower): "
          f"{c.get('higher', 0)} / {c.get('equal', 0)} / {c.get('lower', 0)}"
          for arm, c in ((INSERT, explore[f'docs_{INSERT}_vs_shipped']), (SUPPRESS, explore[f'docs_{SUPPRESS}_vs_shipped']))],
        "- Documents with no complete output in 5 seeds: "
        + ", ".join(f"{a} {n}" for a, n in explore["docs_with_no_complete_output"].items()),
        "- Headings inserted by b-insert-heading: "
        + ", ".join(f"{h} {n}" for h, n in explore["inserted_by_heading"].items()),
        "- b-suppress-end outputs that hit the cap, by sections found: "
        + ", ".join(f"{k}: {n}" for k, n in explore["suppress_cap_sections_found"].items()),
        "- Action-item lines starting with a generic verb (ensure, review, confirm, verify, monitor, "
        "maintain, comply, coordinate, check): "
        f"inserted heading {gv['inserted_heading']['generic_verb']} of {gv['inserted_heading']['lines']}, "
        f"model-written heading {gv['model_written_heading']['generic_verb']} of {gv['model_written_heading']['lines']}",
    ]
    lines.append("")
    (results / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
