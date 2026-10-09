#!/usr/bin/env python3
"""Summarize PoC 004 results into summary.json and summary.md.

Usage: python3 summarize.py [RESULTS_DIR]

RESULTS_DIR defaults to results/ next to this script. Reads RESULTS_DIR/raw/inputs-*.jsonl and
RESULTS_DIR/raw/generations-*.jsonl, and writes RESULTS_DIR/summary.json and summary.md.
Scoring (clean stop, four sections, complete, unsupported numbers, exemplar leak, loops, section
count, END lines) is imported from PoC 003's summarize.py so both PoCs measure the same way.
The hypotheses and the decision rule are the ones registered in README.md; change them there
first, as a deviation, never only here.
"""
import importlib.util
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
POC003 = HERE.parent / "003-qwen-sampler-stop-behavior"
_spec = importlib.util.spec_from_file_location("poc003_summarize", POC003 / "summarize.py")
p3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p3)

A, A105 = "a-near-greedy", "a-repeat-1.05"
B, B115, B130, BNE = "b-qwen-recipe", "b-repeat-1.15", "b-repeat-1.3", "b-no-end-line"


def decide(s, complete_ci):
    gain = s[BNE]["complete"] - s[B]["complete"]
    criteria = {
        "c1_complete_gain": gain >= 0.15 and complete_ci[0] > 0,
        "c2_clean_at_least_90pct": s[BNE]["clean"] >= 0.90,
        "c3_unsupported_within_5pts": s[BNE]["any_unsupported"] <= s[B]["any_unsupported"] + 0.05,
        "c4_leak_at_most_5pct": s[BNE]["leak"] <= 0.05,
    }
    if gain < 0.10:
        verdict = "reject: no gain"
    elif all(criteria.values()):
        verdict = "adopt"
    elif criteria["c1_complete_gain"] and not (criteria["c3_unsupported_within_5pts"] and criteria["c4_leak_at_most_5pct"]):
        verdict = "reject: trade-off"
    else:
        failing = [k for k, v in criteria.items() if not v]
        verdict = "inconclusive (fails " + ", ".join(failing) + ")"
    return {"complete_gain_no_end_minus_b": gain, "criteria": criteria, "verdict": verdict}


def hypotheses(s):
    return {
        "H1_b_side_repeat_lowers_four": s[B]["four"] >= s[B115]["four"] >= s[B130]["four"]
        and s[B]["four"] - s[B130]["four"] >= 0.25,
        "H2_a_side_repeat_raises_four": s[A105]["four"] - s[A]["four"] >= 0.25,
        "H3_no_end_line_raises_four": s[BNE]["four"] - s[B]["four"] >= 0.15,
    }


def reproducibility(gens):
    """Token-for-token match of the A and B arms with PoC 003's host run (same inputs and seeds)."""
    path = POC003 / "results" / "raw" / "generations.jsonl"
    if not path.exists():
        return None
    old = {(g["arm"], g["doc"], g["seed"]): g["tokens"] for g in p3.load_jsonl(path)}
    out = {}
    for arm in (A, B):
        mine = [g for g in gens if g["arm"] == arm]
        out[arm] = {"identical": sum(old.get((arm, g["doc"], g["seed"])) == g["tokens"] for g in mine), "of": len(mine)}
    return out


def pct(x):
    return f"{100 * x:.0f}%"


# Exploratory only (added after the run, not part of the registered rule).
EXPLORATORY_PAIRS = [(BNE, B), (A105, A), (A105, B)]


def doc_compare(by_doc, hi, lo):
    out = Counter()
    for d in sorted(by_doc):
        x, y = p3.rate(by_doc[d][hi], "complete"), p3.rate(by_doc[d][lo], "complete")
        out["higher" if x > y else "equal" if x == y else "lower"] += 1
    return {k: out[k] for k in ("higher", "equal", "lower")}


def ci_line(label, bs):
    return (f"- {label}: {100 * bs['diff']:+.1f} points, "
            f"95% CI [{100 * bs['ci95'][0]:+.1f}, {100 * bs['ci95'][1]:+.1f}]")


def main():
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
    raw = results / "raw"
    sources = {}
    for path in sorted(raw.glob("inputs-*.jsonl")):
        for r in p3.load_jsonl(path):
            if sources.setdefault(r["doc"], r["input"]) != r["input"]:
                sys.exit(f"doc {r['doc']}: input differs between prompt variants")
    gens = [g for path in sorted(raw.glob("generations-*.jsonl")) for g in p3.load_jsonl(path)]
    arm_order = [a["name"] for a in json.loads((HERE / "arms.json").read_text())]

    rows = defaultdict(list)
    by_doc = defaultdict(lambda: defaultdict(list))
    for g in gens:
        sc = p3.score(g, sources[g["doc"]])
        rows[g["arm"]].append(sc)
        by_doc[g["doc"]][g["arm"]].append(sc)

    s = {}
    for arm in arm_order:
        r = rows[arm]
        speeds = [x["tok_s"] for x in r if x["tok_s"]]
        s[arm] = {
            "n": len(r),
            **{k: p3.rate(r, k) for k in ("clean", "cap", "four", "complete", "any_unsupported", "leak", "loop", "end_marker")},
            "sections_found": dict(sorted(Counter(x["sections_found"] for x in r).items())),
            "median_tokens": statistics.median(x["tokens"] for x in r) if r else None,
            "median_decode_tok_s": statistics.median(speeds) if speeds else None,
        }

    bs = {
        "complete_no_end_minus_b": p3.bootstrap_diff(by_doc, "complete", BNE, B),
        "four_no_end_minus_b": p3.bootstrap_diff(by_doc, "four", BNE, B),
        "four_b_repeat_1.3_minus_b": p3.bootstrap_diff(by_doc, "four", B130, B),
        "four_a_repeat_1.05_minus_a": p3.bootstrap_diff(by_doc, "four", A105, A),
    }
    decision = decide(s, bs["complete_no_end_minus_b"]["ci95"])
    hyp = hypotheses(s)
    stops = {arm: dict(Counter(g["stop"] for g in gens if g["arm"] == arm)) for arm in arm_order}
    repro = reproducibility(gens)
    exploratory = {
        "docs_complete": {f"{hi} vs {lo}": doc_compare(by_doc, hi, lo) for hi, lo in EXPLORATORY_PAIRS},
        "docs_with_no_complete_output": {
            arm: sum(not any(x["complete"] for x in by_doc[d][arm]) for d in by_doc) for arm in arm_order
        },
    }

    summary = {
        "generations": len(gens),
        "documents": len(by_doc),
        "arms": s,
        "stops": stops,
        "bootstrap": bs,
        "hypotheses": hyp,
        "decision": decision,
        "reproduces_poc003_tokens": repro,
        "exploratory_not_registered": exploratory,
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    lines = [
        "# PoC 004 summary",
        "",
        f"{len(gens)} generations, {len(by_doc)} documents. Rates are shares of generations per arm.",
        "",
        "| Arm | n | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Exemplar leak | Loop | END line | Headings found (1/2/3/4) | Median tokens | Median decode tok/s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in arm_order:
        a = s[arm]
        tok_s = f"{a['median_decode_tok_s']:.1f}" if a["median_decode_tok_s"] else "n/a"
        found = " / ".join(str(a["sections_found"].get(k, 0)) for k in (1, 2, 3, 4))
        lines.append(
            f"| {arm} | {a['n']} | {pct(a['clean'])} | {pct(a['cap'])} | {pct(a['four'])} | {pct(a['complete'])} "
            f"| {pct(a['any_unsupported'])} | {pct(a['leak'])} | {pct(a['loop'])} | {pct(a['end_marker'])} "
            f"| {found} | {a['median_tokens']} | {tok_s} |"
        )
    lines += [
        "",
        "Document-level bootstrap (10,000 resamples, seed 0):",
        "",
        ci_line("Complete, b-no-end-line minus b-qwen-recipe", bs["complete_no_end_minus_b"]),
        ci_line("Four sections, b-no-end-line minus b-qwen-recipe", bs["four_no_end_minus_b"]),
        ci_line("Four sections, b-repeat-1.3 minus b-qwen-recipe", bs["four_b_repeat_1.3_minus_b"]),
        ci_line("Four sections, a-repeat-1.05 minus a-near-greedy", bs["four_a_repeat_1.05_minus_a"]),
        "",
        "## Hypotheses",
        "",
        *[f"- {k}: {'holds' if v else 'does not hold'}" for k, v in hyp.items()],
        "",
        "## Decision rule (b-no-end-line vs b-qwen-recipe, first match wins)",
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
        lines += [f"- {arm}: {v['identical']} of {v['of']} generations token-identical to PoC 003" for arm, v in repro.items()]
    lines += [
        "",
        "## Exploratory (added after the run; not part of the decision rule)",
        "",
        "Documents by complete rate (of 20):",
        "",
        *[f"- {pair}: higher {v['higher']}, equal {v['equal']}, lower {v['lower']}"
          for pair, v in exploratory["docs_complete"].items()],
        "",
        "Documents where none of the 5 seeds gave a complete output: "
        + ", ".join(f"{arm} {n}" for arm, n in exploratory["docs_with_no_complete_output"].items()),
    ]
    lines.append("")
    (results / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
