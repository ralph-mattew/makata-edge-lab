"""PoC 009 summary: Qwen2.5-1.5B on contract questions with 1, 3 or 5 retrieved chunks.

Usage: python3 summarize.py [RESULTS_DIR]   (default: results)

Reads RESULTS_DIR/raw/items.jsonl, selection-<condition>.jsonl and gen-<condition>-run<n>.jsonl.
Writes RESULTS_DIR/summary.json and RESULTS_DIR/summary.md. Pure standard library.

Scoring is PoC 008's (which is PoC 006's with the corrected detector), imported unchanged. The
verdict uses only the key-fact measure, the unsupported-number measure and the prefill time, none
of which depends on the answer-or-absent detector. The decision rule is in README.md and is
applied here without changes.
"""

import importlib.util
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P8 = HERE.parent / "008-absence-instruction-doc-qa"
sys.path.insert(0, str(HERE.parent / "006-doc-qa-fm-gemma-qwen"))
_spec = importlib.util.spec_from_file_location("summarize008", P8 / "summarize.py")
s8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s8)

CONDITIONS = ["eg-k1", "eg-k3", "eg-k5", "nl-k3", "nl-k5"]
RUN2 = ["eg-k3", "eg-k5"]
BOOTSTRAP_RESAMPLES = 10_000
COVERED = 0.5            # a prompt covers the answer when its chunks hold >= this share of the span
NO_GAIN = 0.015          # rule step 1
MIN_GAIN = 0.03          # c1
MAX_UNSUPPORTED_RISE = 0.03   # c2
MAX_PREFILL_RATIO = 2.0       # c3
H2_DROP = 0.02
H3_DROP = 0.10
FIELDS = ["n", "kf_n", "kf", "ans", "unsup", "c3_n", "c3_kf_n", "c3_kf"]


def read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def pct(x):
    return "n/a" if x != x else f"{100 * x:.1f}"


def pts(x):
    return f"{100 * x:+.1f}"


def load(raw, run):
    """{condition: [row]} for one run. Each row is PoC 008's score row plus the retrieval and cost
    fields."""
    items = {it["item"]: it for it in read(raw / "items.jsonl")}
    selection = {c: {s["item"]: s for s in read(raw / f"selection-{c}.jsonl")} for c in CONDITIONS}
    out = {}
    for c in CONDITIONS:
        path = raw / f"gen-{c}-run{run}.jsonl"
        if not path.exists():
            continue
        rows = []
        for g in read(path):
            it = dict(items[g["item"]])
            sel = selection[c][g["item"]]
            it["source"] = " ".join(sel["numbers"])
            r = s8.score(it, g)
            r["coverage"] = sel["coverage"]
            r["covered"] = sel["coverage"] >= COVERED
            r["covered3"] = selection["eg-k3"][g["item"]]["coverage"] >= COVERED
            r["section_words"] = sel["section_words"]
            r["dropped"] = sel["dropped"]
            r["prompt_tokens"] = g["prompt_tokens"]
            r["budget"] = g["budget"]
            r["prefill_ms"] = g["prefill_ms"]
            r["hit_budget"] = g["stop"] == "cap"
            rows.append(r)
        out[c] = sorted(rows, key=lambda r: r["item"])
    return out


def vector(r):
    kf = "key_fact" in r
    return [1, kf, kf and r["key_fact"], r["call"] == "answer", r["any_unsupported"],
            r["covered3"], kf and r["covered3"], kf and r["covered3"] and r["key_fact"]]


def totals(rows):
    t = [0] * len(FIELDS)
    for r in rows:
        for i, v in enumerate(vector(r)):
            t[i] += v
    return dict(zip(FIELDS, t))


def div(x, y):
    return x / y if y else float("nan")


def measure(t, name):
    return {"key_fact": div(t["kf"], t["kf_n"]), "answer_rate": div(t["ans"], t["n"]),
            "any_unsupported": div(t["unsup"], t["n"]),
            "key_fact_covered3": div(t["c3_kf"], t["c3_kf_n"])}[name]


def rates(rows):
    kf = [r for r in rows if "key_fact" in r]
    cov = [r for r in rows if r["covered"]]
    unc = [r for r in rows if not r["covered"]]

    def kfr(rs):
        rs = [r for r in rs if "key_fact" in r]
        return div(sum(r["key_fact"] for r in rs), len(rs))

    tokens = sorted(r["prompt_tokens"] for r in rows)
    return {
        "n": len(rows),
        "recall": len(cov) / len(rows),
        "key_fact_n": len(kf), "key_fact": kfr(rows),
        "key_fact_covered": kfr(cov), "key_fact_not_covered": kfr(unc),
        "answer_rate": sum(r["call"] == "answer" for r in rows) / len(rows),
        "answer_rate_covered": div(sum(r["call"] == "answer" for r in cov), len(cov)),
        "answer_rate_not_covered": div(sum(r["call"] == "answer" for r in unc), len(unc)),
        "absent_rate": sum(r["call"] == "absent" for r in rows) / len(rows),
        "any_unsupported": sum(r["any_unsupported"] for r in rows) / len(rows),
        "errors": sum(bool(r["error"]) for r in rows),
        "empty": sum(r["call"] == "empty" for r in rows),
        "hit_budget": sum(r["hit_budget"] for r in rows) / len(rows),
        "budget_below_200": sum(r["budget"] < 200 for r in rows),
        "items_with_dropped_chunks": sum(r["dropped"] > 0 for r in rows),
        "median_section_words": statistics.median(r["section_words"] for r in rows),
        "median_prompt_tokens": statistics.median(tokens),
        "p95_prompt_tokens": tokens[int(0.95 * len(tokens))],
        "max_prompt_tokens": tokens[-1],
        "median_prefill_ms": statistics.median(r["prefill_ms"] for r in rows),
        "median_total_ms": statistics.median(r["ms"] for r in rows),
        "median_words": statistics.median(r["words"] for r in rows),
    }


# Compared quantities: name -> (function of {condition: measure-reader}). Each reads totals only.
def spec():
    d = {}

    def diff(hi, lo, m):
        return lambda T: measure(T[hi], m) - measure(T[lo], m)

    d["eg5_minus_eg3:key_fact"] = diff("eg-k5", "eg-k3", "key_fact")
    d["eg5_minus_eg3:answer_rate"] = diff("eg-k5", "eg-k3", "answer_rate")
    d["eg5_minus_eg3:any_unsupported"] = diff("eg-k5", "eg-k3", "any_unsupported")
    d["eg5_minus_eg3:key_fact_covered3"] = diff("eg-k5", "eg-k3", "key_fact_covered3")
    d["eg3_minus_eg1:key_fact"] = diff("eg-k3", "eg-k1", "key_fact")
    d["eg3_minus_eg1:answer_rate"] = diff("eg-k3", "eg-k1", "answer_rate")
    d["nl5_minus_nl3:key_fact"] = diff("nl-k5", "nl-k3", "key_fact")
    d["nl5_minus_nl3:answer_rate"] = diff("nl-k5", "nl-k3", "answer_rate")
    d["nl5_minus_nl3:any_unsupported"] = diff("nl-k5", "nl-k3", "any_unsupported")
    return d


def bootstrap(rows):
    """Contract-level bootstrap of every compared quantity: contracts are resampled with all their
    items, 10,000 resamples, seed 0."""
    by_contract = {c: defaultdict(lambda: [0] * len(FIELDS)) for c in CONDITIONS}
    for c in CONDITIONS:
        for r in rows[c]:
            a = by_contract[c][r["contract"]]
            for i, v in enumerate(vector(r)):
                a[i] += v
    contracts = sorted({r["contract"] for r in rows["eg-k3"]})
    width = len(FIELDS)
    flat = {k: [x for c in CONDITIONS for x in by_contract[c][k]] for k in contracts}
    functions = spec()

    def evaluate(counts):
        acc = [0] * (width * len(CONDITIONS))
        for k, w in counts.items():
            v = flat[k]
            for i in range(len(acc)):
                acc[i] += w * v[i]
        T = {c: dict(zip(FIELDS, acc[j * width:(j + 1) * width])) for j, c in enumerate(CONDITIONS)}
        return {name: f(T) for name, f in functions.items()}

    point = evaluate({k: 1 for k in contracts})
    rng = random.Random(0)
    draws = {name: [] for name in functions}
    for _ in range(BOOTSTRAP_RESAMPLES):
        counts = defaultdict(int)
        for _ in contracts:
            counts[rng.choice(contracts)] += 1
        for name, v in evaluate(counts).items():
            if v == v:
                draws[name].append(v)
    out = {}
    for name, ds in draws.items():
        ds.sort()
        k = len(ds)
        out[name] = {"diff": point[name], "ci95": [ds[int(0.025 * k)], ds[int(0.975 * k) - 1]]}
    return out


def decide(b, s, r):
    """The rule for retriever r ("eg" or "nl"): depth 5 against depth 3."""
    g = b[f"{r}5_minus_{r}3:key_fact"]
    ratio = s[f"{r}-k5"]["median_prefill_ms"] / s[f"{r}-k3"]["median_prefill_ms"]
    c1 = g["diff"] >= MIN_GAIN and g["ci95"][0] > 0
    c2 = b[f"{r}5_minus_{r}3:any_unsupported"]["diff"] <= MAX_UNSUPPORTED_RISE
    c3 = ratio <= MAX_PREFILL_RATIO
    detail = {"gain": g["diff"], "ci95": g["ci95"], "c1": c1, "c2": c2, "c3": c3,
              "prefill_ratio": ratio}
    if g["diff"] < NO_GAIN:
        return "reject: no gain", detail
    if not c1:
        return "inconclusive (gain of 1.5 to 3 points, or an interval that includes zero)", detail
    if c2 and c3:
        return "adopt (host stage)", detail
    failing = [n for n, ok in (("c2", c2), ("c3", c3)) if not ok]
    return f"reject: trade-off ({' and '.join(failing)} fail)", detail


def hypotheses(b):
    g = b["eg5_minus_eg3:key_fact"]
    h2 = b["eg5_minus_eg3:key_fact_covered3"]
    h3 = b["eg3_minus_eg1:key_fact"]
    return {
        "H1": {"holds": g["diff"] < NO_GAIN, **g},
        "H2": {"holds": h2["diff"] <= -H2_DROP, **h2},
        "H3": {"holds": h3["diff"] >= H3_DROP, **h3},
    }


def main():
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
    raw = results / "raw"
    run1 = load(raw, 1)
    missing = [c for c in CONDITIONS if c not in run1]
    if missing:
        sys.exit(f"missing run 1 outputs for {missing}")
    s = {c: rates(run1[c]) for c in CONDITIONS}
    b = bootstrap(run1)
    verdict, detail = decide(b, s, "eg")
    verdict_nl, detail_nl = decide(b, s, "nl")
    hyp = hypotheses(b)

    run2 = load(raw, 2)
    r2 = {}
    if all(c in run2 for c in RUN2):
        t = {c: totals(run2[c]) for c in RUN2}
        r2["key_fact_gain"] = measure(t["eg-k5"], "key_fact") - measure(t["eg-k3"], "key_fact")
        for c in RUN2:
            a1 = {r["item"]: r["call"] for r in run1[c]}
            a2 = {r["item"]: r["call"] for r in run2[c]}
            r2[c] = {"key_fact": rates(run2[c])["key_fact"],
                     "same_call": sum(a1[i] == a2[i] for i in a1) / len(a1)}

    categories = defaultdict(lambda: defaultdict(list))
    for c in ("eg-k3", "eg-k5"):
        for r in run1[c]:
            categories[r["category"]][c].append(r)

    out = {"conditions": s, "comparisons": b, "decision": {"verdict": verdict, **detail},
           "decision_nl": {"verdict": verdict_nl, **detail_nl},
           "hypotheses": hyp, "run2": r2}
    (results / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")

    L = []
    L.append("# PoC 009 summary\n")
    n_items = s["eg-k3"]["n"]
    L.append(f"{n_items} items, run 1. Verdict (EmbeddingGemma retrieval): **{verdict}**. "
             f"With NLEmbedding retrieval: **{verdict_nl}**.\n")
    L.append("## Run 1, by condition (percent of items)\n")
    L.append("| Condition | Recall | Key fact right | Answers | Says absent | Any unsupported number | "
             "Hit budget | Median prompt tokens | p95 | Max | Median prefill ms | Median total ms |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in CONDITIONS:
        x = s[c]
        L.append(f"| {c} | {pct(x['recall'])} | {pct(x['key_fact'])} (n={x['key_fact_n']}) | "
                 f"{pct(x['answer_rate'])} | {pct(x['absent_rate'])} | {pct(x['any_unsupported'])} | "
                 f"{pct(x['hit_budget'])} | {x['median_prompt_tokens']:.0f} | {x['p95_prompt_tokens']} | "
                 f"{x['max_prompt_tokens']} | {x['median_prefill_ms']:.0f} | {x['median_total_ms']:.0f} |")
    L.append("\nRecall = the chunks cover at least half of CUAD's answer span (PoC 007's measure, with "
             "the word cap applied). An item is an answer or absent by detector v2; the verdict does "
             "not use it.\n")
    L.append("## Split by whether the chunks cover the answer\n")
    L.append("| Condition | Key fact, covered | Key fact, not covered | Answers, covered | "
             "Answers, not covered | Items with chunks dropped by the cap | Budget below 200 |")
    L.append("|---|---|---|---|---|---|---|")
    for c in CONDITIONS:
        x = s[c]
        L.append(f"| {c} | {pct(x['key_fact_covered'])} | {pct(x['key_fact_not_covered'])} | "
                 f"{pct(x['answer_rate_covered'])} | {pct(x['answer_rate_not_covered'])} | "
                 f"{x['items_with_dropped_chunks']} | {x['budget_below_200']} |")
    L.append("\n## Comparisons (points, 95% CI from a contract-level bootstrap)\n")
    L.append("| Comparison | Difference | 95% CI |")
    L.append("|---|---|---|")
    for name, v in b.items():
        L.append(f"| {name} | {pts(v['diff'])} | [{pts(v['ci95'][0])}, {pts(v['ci95'][1])}] |")
    L.append("\n## Decision\n")
    for r, label, g, v in (("eg", "EmbeddingGemma retrieval (the headline)", detail, verdict),
                           ("nl", "NLEmbedding retrieval (the fallback)", detail_nl, verdict_nl)):
        L.append(f"**{label}**\n")
        L.append(f"- {r}-k5 minus {r}-k3, key fact right: {pts(g['gain'])} points, 95% CI "
                 f"[{pts(g['ci95'][0])}, {pts(g['ci95'][1])}].")
        L.append(f"- c1 (gain >= 3 points, CI above 0): {'yes' if g['c1'] else 'no'}.")
        L.append(f"- c2 (any unsupported number rises by at most 3 points): "
                 f"{'yes' if g['c2'] else 'no'}.")
        L.append(f"- c3 (median prefill time at most 2.0 times {r}-k3's): "
                 f"{'yes' if g['c3'] else 'no'} ({g['prefill_ratio']:.2f}x).")
        L.append(f"- Verdict: {v}.\n")
    L.append("\n## Hypotheses\n")
    for name, h in hyp.items():
        L.append(f"- {name}: {pts(h['diff'])} points, 95% CI [{pts(h['ci95'][0])}, "
                 f"{pts(h['ci95'][1])}]. {'Holds' if h['holds'] else 'Does not hold'}.")
    if r2:
        L.append("\n## Run 2 (seed 2; not used in the verdict)\n")
        L.append(f"- eg-k5 minus eg-k3, key fact right: {pts(r2['key_fact_gain'])} points.")
        for c in RUN2:
            L.append(f"- {c}: key fact right {pct(r2[c]['key_fact'])}; same answer-or-absent call as "
                     f"run 1 on {pct(r2[c]['same_call'])}% of items.")
    L.append("\n## Per category, key fact right (percent; categories with parsable key facts)\n")
    L.append("| Category | n | eg-k3 | eg-k5 |")
    L.append("|---|---|---|---|")
    for cat in sorted(categories):
        k3 = [r for r in categories[cat]["eg-k3"] if "key_fact" in r]
        k5 = [r for r in categories[cat]["eg-k5"] if "key_fact" in r]
        if k3:
            L.append(f"| {cat} | {len(k3)} | {pct(sum(r['key_fact'] for r in k3) / len(k3))} | "
                     f"{pct(sum(r['key_fact'] for r in k5) / len(k5))} |")
    (results / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
