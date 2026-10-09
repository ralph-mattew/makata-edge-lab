"""PoC 007 summary: recall@3 of Xylo's retrieval pipeline under two embedding backends.

Usage: python3 summarize.py [RAW_DIR [OUT_DIR]]

Reads from RAW_DIR (default results/raw): items.jsonl, chunks-index.jsonl, scores-{kw,nl,eg,bm25}.jsonl
and timing-{nl,eg}.jsonl. Writes summary.json and summary.md to OUT_DIR (default RAW_DIR/..).
Pure standard library. The decision rule is in README.md and is applied here without changes.
"""

import json
import random
import statistics
import sys
from pathlib import Path

TOP_K = 3
PROXIMITY_BOOST = 0.05
DIVERSITY_PENALTY = 0.03
HIT = 0.5  # recall: the retrieved text covers at least this share of the gold span
FULL = 0.9
GAIN_REJECT = 0.03
GAIN_ADOPT = 0.05
H2_GAIN = 0.10
H3_BAND = 0.05
EMBED_MS_LIMIT = 50.0
BOOTSTRAP = 10000
BOOTSTRAP_SEED = 0
SEMANTIC_WEIGHT = 0.7

# name -> (semantic backend or None, semantic weight, keyword weight)
ARMS = {
    "nl-hybrid": ("nl", 0.7, 0.3),
    "eg-hybrid": ("eg", 0.7, 0.3),
    "nl-only": ("nl", 1.0, 0.0),
    "eg-only": ("eg", 1.0, 0.0),
    "kw-only": (None, 0.0, 1.0),
}
SWEEP = [0.5, 0.7, 0.9, 1.0]


def read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def retrieve(sem, kw, pages, k, sem_w, kw_w):
    """Xylo's DocumentRetriever.retrieve: score, top (k+4), proximity boost, page diversity, top k."""
    scored = [(i, sem_w * (sem[i] if sem is not None and sem[i] is not None else 0.0) + kw_w * kw[i])
              for i in range(len(kw))]
    scored.sort(key=lambda t: -t[1])  # stable: ties keep document order
    selected = scored[:k + 4]
    present = {i for i, _ in selected}
    selected = [(i, s + PROXIMITY_BOOST if (i - 1 in present or i + 1 in present) else s) for i, s in selected]
    selected.sort(key=lambda t: -t[1])
    counts, out = {}, []
    for i, s in selected:
        count = counts.get(pages[i], 0)
        out.append((i, s - DIVERSITY_PENALTY * (count - 1) if count >= 2 else s))
        counts[pages[i]] = count + 1
    out.sort(key=lambda t: -t[1])
    return [i for i, _ in out[:k]]


def raw_top(scores, k):
    return sorted(range(len(scores)), key=lambda i: -scores[i])[:k]


def coverage(chosen, ranges, gold):
    a, b = gold  # inclusive word indexes
    covered = set()
    for i in chosen:
        lo, hi = max(ranges[i][0], a), min(ranges[i][1] - 1, b)
        covered.update(range(lo, hi + 1))
    return len(covered) / (b - a + 1)


def pct(x):
    return f"{100 * x:.1f}"


def main():
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "results" / "raw"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else raw.parent
    items = read(raw / "items.jsonl")
    index = {c["contract"]: c["chunks"] for c in read(raw / "chunks-index.jsonl")}
    scores = {m: {r["item"]: r for r in read(raw / f"scores-{m}.jsonl")} for m in ("kw", "nl", "eg", "bm25")}
    timing = {m: read(raw / f"timing-{m}.jsonl") for m in ("nl", "eg")}

    results = {}  # (arm, k) -> {item: (coverage)}
    def run(arm, backend, sem_w, kw_w, k, label=None):
        cov = {}
        for it in items:
            ranges = index[it["contract"]]
            pages = [r[2] for r in ranges]
            sem = scores[backend][it["item"]]["scores"] if backend else None
            chosen = retrieve(sem, scores["kw"][it["item"]]["scores"], pages, k, sem_w, kw_w)
            cov[it["item"]] = (coverage(chosen, ranges, it["gold_words"]),
                               sum(ranges[i][1] - ranges[i][0] for i in chosen))
        results[(label or arm, k)] = cov

    for arm, (backend, sw, kw) in ARMS.items():
        for k in (1, 3, 5):
            run(arm, backend, sw, kw, k)
    for backend in ("nl", "eg"):
        for sw in SWEEP:
            if sw not in (0.7, 1.0):  # 0.7 and 1.0 are arms already
                run(None, backend, sw, 1 - sw, TOP_K, label=f"{backend}-w{sw}")
    for k in (1, 3, 5):  # BM25 reference: raw ranking, no re-rank
        cov = {}
        for it in items:
            ranges = index[it["contract"]]
            chosen = raw_top(scores["bm25"][it["item"]]["scores"], k)
            cov[it["item"]] = (coverage(chosen, ranges, it["gold_words"]),
                               sum(ranges[i][1] - ranges[i][0] for i in chosen))
        results[("bm25", k)] = cov
    # Oracle: best 3 chunks by coverage of the span (an upper bound for any ranker).
    cov = {}
    for it in items:
        ranges = index[it["contract"]]
        a, b = it["gold_words"]
        single = sorted(range(len(ranges)),
                        key=lambda i: -(max(0, min(ranges[i][1] - 1, b) - max(ranges[i][0], a) + 1)))[:TOP_K]
        cov[it["item"]] = (coverage(single, ranges, it["gold_words"]), 0)
    results[("oracle", TOP_K)] = cov

    by_item = {it["item"]: it for it in items}
    n = len(items)

    def recall(arm, k=TOP_K, threshold=HIT, subset=None):
        keys = subset if subset is not None else by_item
        vals = [results[(arm, k)][i][0] for i in keys]
        return sum(v >= threshold for v in vals) / len(vals)

    def any_overlap(arm, k=TOP_K):
        return sum(v[0] > 0 for v in results[(arm, k)].values()) / n

    arms = list(ARMS) + ["bm25"]
    table = {}
    for arm in arms:
        table[arm] = {
            "recall@1": recall(arm, 1), "recall@3": recall(arm, 3), "recall@5": recall(arm, 5),
            "full@3": recall(arm, 3, FULL), "any_overlap@3": any_overlap(arm),
            "mean_coverage@3": statistics.mean(v[0] for v in results[(arm, 3)].values()),
            "median_words_read@3": statistics.median(v[1] for v in results[(arm, 3)].values()),
        }
    table["oracle"] = {"recall@3": recall("oracle"), "full@3": recall("oracle", TOP_K, FULL)}

    # Paired bootstrap over contracts.
    contracts = sorted({it["contract"] for it in items})
    per_contract = {}
    for it in items:
        per_contract.setdefault(it["contract"], []).append(it["item"])

    def paired(a, b):
        agg = []
        for c in contracts:
            ids = per_contract[c]
            agg.append((sum(results[(a, TOP_K)][i][0] >= HIT for i in ids) -
                        sum(results[(b, TOP_K)][i][0] >= HIT for i in ids), len(ids)))
        rng = random.Random(BOOTSTRAP_SEED)
        diffs = []
        for _ in range(BOOTSTRAP):
            total = size = 0
            for _ in contracts:
                d, m = agg[rng.randrange(len(agg))]
                total += d
                size += m
            diffs.append(total / size)
        diffs.sort()
        point = sum(d for d, _ in agg) / n
        return {"gain": point, "ci95": [diffs[int(0.025 * BOOTSTRAP)], diffs[int(0.975 * BOOTSTRAP) - 1]]}

    primary = paired("eg-hybrid", "nl-hybrid")
    h2 = paired("eg-only", "nl-only")
    h3 = paired("nl-hybrid", "kw-only")

    ms = {m: [x for t in timing[m] for x in t["chunk_ms"]] for m in timing}
    embed = {m: {"median_ms": statistics.median(v), "mean_ms": statistics.mean(v),
                 "p95_ms": sorted(v)[int(0.95 * len(v))], "chunks": len(v)} for m, v in ms.items()}
    embed["eg"]["tokens"] = sum(t["tokens"] for t in timing["eg"])
    embed["eg"]["truncated_chunks"] = sum(t["truncated"] for t in timing["eg"])
    embed["nl"]["nil_chunks"] = sum(t["nil_chunks"] for t in timing["nl"])
    embed["eg"]["median_contract_s"] = statistics.median(sum(t["chunk_ms"]) / 1000 for t in timing["eg"])
    embed["nl"]["median_contract_s"] = statistics.median(sum(t["chunk_ms"]) / 1000 for t in timing["nl"])

    def spread(backend):
        gaps, ranges_ = [], []
        for it in items:
            s = [x for x in scores[backend][it["item"]]["scores"] if x is not None]
            gaps.append(max(s) - statistics.median(s))
            ranges_.append(max(s) - min(s))
        return {"median_top_minus_median": statistics.median(gaps), "median_range": statistics.median(ranges_)}

    spreads = {m: spread(m) for m in ("nl", "eg")}
    languages = {}
    for it in items:
        r = scores["nl"][it["item"]]
        key = f"doc={r['language']} query={r['query_language']}"
        languages[key] = languages.get(key, 0) + 1

    categories = sorted({it["category"] for it in items})
    per_category = {}
    for cat in categories:
        subset = [it["item"] for it in items if it["category"] == cat]
        per_category[cat] = {"n": len(subset), **{arm: recall(arm, TOP_K, HIT, subset) for arm in arms}}
    macro = {arm: statistics.mean(per_category[c][arm] for c in categories) for arm in arms}

    sweep = {}
    for backend in ("nl", "eg"):
        for sw in SWEEP:
            label = {0.7: f"{backend}-hybrid", 1.0: f"{backend}-only"}.get(sw, f"{backend}-w{sw}")
            sweep[f"{backend} semantic weight {sw}"] = recall(label)

    c1 = primary["gain"] >= GAIN_ADOPT and primary["ci95"][0] > 0
    c2 = embed["eg"]["median_ms"] <= EMBED_MS_LIMIT
    if primary["gain"] < GAIN_REJECT:
        verdict = "reject: no gain"
    elif c1 and c2:
        verdict = "adopt (host stage)"
    elif c1:
        verdict = "reject: cost"
    else:
        failing = []
        if primary["gain"] < GAIN_ADOPT:
            failing.append("gain below 5 points")
        if primary["ci95"][0] <= 0:
            failing.append("confidence interval includes 0")
        verdict = "inconclusive (" + ", ".join(failing) + ")"

    summary = {
        "items": n, "contracts": len(contracts), "chunks": sum(len(v) for v in index.values()),
        "verdict": verdict, "c1": c1, "c2": c2, "primary": primary,
        "hypotheses": {
            "H1": {"claim": "eg-hybrid recall@3 >= nl-hybrid + 5 points", **primary,
                   "holds": primary["gain"] >= GAIN_ADOPT},
            "H2": {"claim": "eg-only recall@3 >= nl-only + 10 points", **h2, "holds": h2["gain"] >= H2_GAIN},
            "H3": {"claim": "nl-hybrid recall@3 no more than 5 points above kw-only", **h3,
                   "holds": h3["gain"] <= H3_BAND},
        },
        "arms": table, "per_category": per_category, "macro_recall@3": macro,
        "embedding": embed, "score_spread": spreads, "languages_nl": languages,
        "exploratory_weight_sweep_not_registered": sweep,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [f"# PoC 007 summary", "",
             f"{n} items, {len(contracts)} contracts, {summary['chunks']} chunks. Verdict: **{verdict}**.", "",
             "## Recall of the answer-bearing text (percent of items)", "",
             "| Arm | recall@1 | recall@3 | recall@5 | full@3 | any overlap@3 | mean coverage@3 | median words read@3 |",
             "|---|---|---|---|---|---|---|---|"]
    for arm in arms:
        t = table[arm]
        lines.append(f"| {arm} | {pct(t['recall@1'])} | {pct(t['recall@3'])} | {pct(t['recall@5'])} | "
                     f"{pct(t['full@3'])} | {pct(t['any_overlap@3'])} | {pct(t['mean_coverage@3'])} | "
                     f"{t['median_words_read@3']:.0f} |")
    lines.append(f"| oracle (best 3 chunks) | | {pct(table['oracle']['recall@3'])} | | "
                 f"{pct(table['oracle']['full@3'])} | | | |")
    lines += ["", "recall = the retrieved chunks, overlap included, cover at least 50% of the gold span's words. "
                  "full = at least 90%. bm25 is a reference outside Xylo's pipeline (raw top-k, no re-ranking).", "",
              "## Decision", "",
              f"- eg-hybrid minus nl-hybrid, recall@3: {100 * primary['gain']:+.1f} points, "
              f"95% CI [{100 * primary['ci95'][0]:+.1f}, {100 * primary['ci95'][1]:+.1f}] (contract-level paired bootstrap).",
              f"- c1 (gain >= 5 points, CI above 0): {'yes' if c1 else 'no'}.",
              f"- c2 (median EmbeddingGemma embed time <= 50 ms per chunk on the host): "
              f"{'yes' if c2 else 'no'} ({embed['eg']['median_ms']:.1f} ms).",
              f"- Verdict: {verdict}.", "", "## Hypotheses", ""]
    for name, h in summary["hypotheses"].items():
        lines.append(f"- {name}, {h['claim']}: {100 * h['gain']:+.1f} points, 95% CI "
                     f"[{100 * h['ci95'][0]:+.1f}, {100 * h['ci95'][1]:+.1f}]. {'Holds' if h['holds'] else 'Does not hold'}.")
    lines += ["", "## Per category, recall@3 (percent)", "",
              "| Category | n | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]
    for cat in categories:
        lines.append(f"| {cat} | {per_category[cat]['n']} | " +
                     " | ".join(pct(per_category[cat][a]) for a in arms) + " |")
    lines.append("| macro average | | " + " | ".join(pct(macro[a]) for a in arms) + " |")
    lines += ["", "## Embedding cost on the host", "",
              "| Backend | chunks | median ms | mean ms | p95 ms | median seconds per contract |", "|---|---|---|---|---|---|"]
    for m in ("nl", "eg"):
        e = embed[m]
        lines.append(f"| {m} | {e['chunks']} | {e['median_ms']:.1f} | {e['mean_ms']:.1f} | {e['p95_ms']:.1f} | "
                     f"{e['median_contract_s']:.1f} |")
    lines += ["", f"EmbeddingGemma tokens embedded: {embed['eg']['tokens']}, chunks truncated at 2048 tokens: "
                  f"{embed['eg']['truncated_chunks']}. NLEmbedding chunks with no vector: {embed['nl']['nil_chunks']}.",
              "", "## Score spread (per item, over all chunks of the contract)", "",
              "| Backend | median (top minus median score) | median (max minus min) |", "|---|---|---|"]
    for m in ("nl", "eg"):
        lines.append(f"| {m} | {spreads[m]['median_top_minus_median']:.3f} | {spreads[m]['median_range']:.3f} |")
    lines += ["", "## Detected languages (NLEmbedding path)", ""]
    lines += [f"- {k}: {v} items" for k, v in sorted(languages.items())]
    lines += ["", "## Semantic-weight sweep, recall@3 (exploratory, not registered)", "",
              "| Setting | recall@3 |", "|---|---|"]
    lines += [f"| {k} | {pct(v)} |" for k, v in sweep.items()]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:4]))


if __name__ == "__main__":
    main()
