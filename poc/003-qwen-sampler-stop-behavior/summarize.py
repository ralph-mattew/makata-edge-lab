#!/usr/bin/env python3
"""Summarize PoC 003 results into summary.json and summary.md.

Usage: python3 summarize.py [RESULTS_DIR]

RESULTS_DIR defaults to results/ next to this script. Reads RESULTS_DIR/raw/inputs.jsonl and
RESULTS_DIR/raw/generations.jsonl, and writes RESULTS_DIR/summary.json and summary.md.
The hypotheses and the decision rule are the ones registered in README.md; change them there
first, as a deviation, never only here.
"""
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
A, B, C, D = "a-near-greedy", "b-qwen-recipe", "c-near-greedy-presence", "d-qwen-recipe-no-presence"
SECTIONS = ["introduction", "summary", "key points", "action items"]
HEADING = re.compile(r"^\s*#{2,3}\s*(introduction|summary|key points|action items)\s*:?\s*$", re.I | re.M)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
EXEMPLAR_TERMS = ["riverside", "eastside", "annex", "community center"]
BOOTSTRAP_RESAMPLES = 10_000
# Exploratory only (added after the run, not part of the registered rule): an output line that
# opens an "END" block, like the closing line of the prompt's worked example.
END_MARKER = re.compile(r"^\s*#+\s*END\b", re.I | re.M)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def numbers(text):
    found = set()
    for raw in NUMBER.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if sum(ch.isdigit() for ch in n) >= 2:
            found.add(n)
    return found


def four_in_order(text):
    first = {}
    for m in HEADING.finditer(text):
        first.setdefault(m.group(1).lower(), m.start())
    if any(s not in first for s in SECTIONS):
        return False
    positions = [first[s] for s in SECTIONS]
    return positions == sorted(positions)


def sections_found(text):
    return len({m.group(1).lower() for m in HEADING.finditer(text)})


def has_loop(text):
    words = text.lower().split()
    grams = Counter(tuple(words[i:i + 6]) for i in range(len(words) - 5))
    return any(c >= 3 for c in grams.values())


def score(gen, source):
    text = gen["text"]
    unsupported = sorted(numbers(text) - numbers(source))
    lower_text, lower_src = text.lower(), source.lower()
    clean = gen["stop"] in ("eos", "stop_string")
    four = four_in_order(text)
    return {
        "clean": clean,
        "cap": gen["stop"] == "cap",
        "four": four,
        "complete": clean and four,
        "unsupported": unsupported,
        "any_unsupported": bool(unsupported),
        "leak": any(t in lower_text and t not in lower_src for t in EXEMPLAR_TERMS),
        "loop": has_loop(text),
        "sections_found": sections_found(text),
        "end_marker": bool(END_MARKER.search(text)),
        "tokens": gen["generated_tokens"],
        "tok_s": gen["generated_tokens"] / (gen["generate_ms"] / 1000) if gen["generate_ms"] > 0 else None,
    }


def rate(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else float("nan")


def bootstrap_diff(by_doc, key, arm_hi, arm_lo):
    docs = sorted(by_doc)
    per_doc = [rate(by_doc[d][arm_hi], key) - rate(by_doc[d][arm_lo], key) for d in docs]
    rng = random.Random(0)
    draws = sorted(
        statistics.fmean(rng.choice(per_doc) for _ in docs) for _ in range(BOOTSTRAP_RESAMPLES)
    )
    return {
        "diff": statistics.fmean(per_doc),
        "ci95": [draws[int(0.025 * BOOTSTRAP_RESAMPLES)], draws[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]],
    }


def decide(s, clean_ci):
    d_clean = s[B]["clean"] - s[A]["clean"]
    criteria = {
        "c1_clean_gain": d_clean >= 0.40 and clean_ci[0] > 0,
        "c2_complete_not_worse": s[B]["complete"] >= s[A]["complete"],
        "c3_unsupported_within_10pts": s[B]["any_unsupported"] <= s[A]["any_unsupported"] + 0.10,
        "c4_leak_at_most_5pct": s[B]["leak"] <= 0.05,
    }
    if d_clean < 0.10:
        verdict = "reject: does not reproduce"
    elif all(criteria.values()):
        verdict = "adopt"
    elif criteria["c1_clean_gain"] and not (criteria["c3_unsupported_within_10pts"] and criteria["c4_leak_at_most_5pct"]):
        verdict = "reject: trade-off"
    else:
        failing = [k for k, v in criteria.items() if not v]
        verdict = "inconclusive (fails " + ", ".join(failing) + ")"
    return {"clean_gain_b_minus_a": d_clean, "criteria": criteria, "verdict": verdict}


def hypotheses(s):
    return {
        "H1_a_hits_cap_at_least_50pct": s[A]["cap"] >= 0.50,
        "H2_b_clean_90_and_four_80": s[B]["clean"] >= 0.90 and s[B]["four"] >= 0.80,
        "H3_presence_carries_effect": abs(s[C]["clean"] - s[B]["clean"]) <= 0.15 and s[B]["clean"] - s[D]["clean"] >= 0.30,
        "H4_b_unsupported_within_10pts_of_a": s[B]["any_unsupported"] <= s[A]["any_unsupported"] + 0.10,
        "H5_b_median_tokens_at_most_220": s[B]["median_tokens"] <= 220,
    }


def pct(x):
    return f"{100 * x:.0f}%"


def main():
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
    raw = results / "raw"
    sources = {r["doc"]: r["input"] for r in load_jsonl(raw / "inputs.jsonl")}
    gens = load_jsonl(raw / "generations.jsonl")
    arm_order = [a["name"] for a in json.loads((HERE / "arms.json").read_text())]

    rows = defaultdict(list)
    by_doc = defaultdict(lambda: defaultdict(list))
    for g in gens:
        sc = score(g, sources[g["doc"]])
        rows[g["arm"]].append(sc)
        by_doc[g["doc"]][g["arm"]].append(sc)

    s = {}
    for arm in arm_order:
        r = rows[arm]
        speeds = [x["tok_s"] for x in r if x["tok_s"]]
        s[arm] = {
            "n": len(r),
            **{k: rate(r, k) for k in ("clean", "cap", "four", "complete", "any_unsupported", "leak", "loop")},
            "median_tokens": statistics.median(x["tokens"] for x in r) if r else None,
            "median_decode_tok_s": statistics.median(speeds) if speeds else None,
        }

    clean_bs = bootstrap_diff(by_doc, "clean", B, A)
    complete_bs = bootstrap_diff(by_doc, "complete", B, A)
    decision = decide(s, clean_bs["ci95"])
    hyp = hypotheses(s)
    stops = {arm: dict(Counter(g["stop"] for g in gens if g["arm"] == arm)) for arm in arm_order}

    exploratory = {
        "sections_found": {arm: dict(sorted(Counter(x["sections_found"] for x in rows[arm]).items())) for arm in arm_order},
        "end_marker": {arm: rate(rows[arm], "end_marker") for arm in arm_order},
        "docs_complete_b_vs_a": dict(Counter(
            "b_higher" if rate(by_doc[d][B], "complete") > rate(by_doc[d][A], "complete")
            else "equal" if rate(by_doc[d][B], "complete") == rate(by_doc[d][A], "complete")
            else "a_higher" for d in sorted(by_doc))),
    }

    summary = {
        "generations": len(gens),
        "documents": len(by_doc),
        "arms": s,
        "stops": stops,
        "bootstrap_b_minus_a": {"clean": clean_bs, "complete": complete_bs},
        "hypotheses": hyp,
        "decision": decision,
        "exploratory_not_registered": exploratory,
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    lines = [
        "# PoC 003 summary",
        "",
        f"{len(gens)} generations, {len(by_doc)} documents. Rates are shares of generations per arm.",
        "",
        "| Arm | n | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Exemplar leak | Loop | Median tokens | Median decode tok/s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in arm_order:
        a = s[arm]
        tok_s = f"{a['median_decode_tok_s']:.1f}" if a["median_decode_tok_s"] else "n/a"
        lines.append(
            f"| {arm} | {a['n']} | {pct(a['clean'])} | {pct(a['cap'])} | {pct(a['four'])} | {pct(a['complete'])} "
            f"| {pct(a['any_unsupported'])} | {pct(a['leak'])} | {pct(a['loop'])} | {a['median_tokens']} | {tok_s} |"
        )
    lines += [
        "",
        "Document-level bootstrap of B minus A (10,000 resamples, seed 0):",
        "",
        f"- Clean stop: {100 * clean_bs['diff']:+.1f} points, 95% CI [{100 * clean_bs['ci95'][0]:+.1f}, {100 * clean_bs['ci95'][1]:+.1f}]",
        f"- Complete: {100 * complete_bs['diff']:+.1f} points, 95% CI [{100 * complete_bs['ci95'][0]:+.1f}, {100 * complete_bs['ci95'][1]:+.1f}]",
        "",
        "## Hypotheses",
        "",
        *[f"- {k}: {'holds' if v else 'does not hold'}" for k, v in hyp.items()],
        "",
        "## Decision rule (A vs B, first match wins)",
        "",
        *[f"- {k}: {'pass' if v else 'fail'}" for k, v in decision["criteria"].items()],
        "",
        f"Verdict: **{decision['verdict']}**",
        "",
        "## Exploratory (added after the run; not part of the decision rule)",
        "",
        "| Arm | Generations by number of distinct section headings found | Output contains an END block line |",
        "|---|---|---|",
        *[f"| {arm} | {', '.join(f'{k}: {v}' for k, v in exploratory['sections_found'][arm].items())} "
          f"| {pct(exploratory['end_marker'][arm])} |" for arm in arm_order],
        "",
        "Documents by complete rate, B against A: "
        + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(exploratory["docs_complete_b_vs_a"].items())),
        "",
    ]
    (results / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
