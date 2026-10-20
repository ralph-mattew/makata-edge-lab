#!/usr/bin/env python3
"""PoC 016 — per-category recall@3 for one (chunk-cond × query-cond) combination.

chunk-cond: page  (PoC 014 chunks-page + emb-page) | xref (016 chunks-xref + emb-xref)
query-cond: raw   (PoC 014 emb-queries, one vector per item)
            decomp(hard-category items: union of top-3 per template sub-query, re-ranked by
                   max hybrid; non-hard items fall back to the raw query)

Hybrid 0.9/0.1, top-3, recall = top-3 cover >=50% of the gold span (PoC 007 defn). Reuses
each chunk's stored word `span` (so appended xref text never corrupts span location).
Contract-level bootstrap CIs. Writes results/recall-<chunk>-<query>.json.
"""
from __future__ import annotations
import argparse, json, math, random, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
RAW = HERE / "results" / "raw"
OUT = HERE / "results"
HARD = {"Exclusivity", "Non-Compete", "Change Of Control"}


def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())


def bm25(qt, docs, k1=1.5, b=0.75):
    N = len(docs); avgdl = sum(len(d) for d in docs) / max(N, 1)
    df = Counter(t for d in docs for t in set(d))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    out = []
    for d in docs:
        tf = Counter(d)
        out.append(sum(idf.get(t, 0) * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl)) for t in qt))
    return out


def norm01(xs):
    lo, hi = min(xs, default=0), max(xs, default=0)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def covers(span, gold, frac=0.5):
    if not span or not gold: return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed); groups = list(per_contract.values()); boot = []
    for _ in range(n):
        samp = [random.choice(groups) for _ in groups]
        xs = [h for g in samp for h in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def hybrid_rank(qvec, qterms, idxs, cvec, dterms, sw=0.9):
    sem = [cosine(qvec, cvec[i]) for i in idxs]
    bm = norm01(bm25(qterms, [dterms[i] for i in idxs]))
    return [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-cond", choices=["page", "xref"], required=True)
    ap.add_argument("--query-cond", choices=["raw", "decomp"], required=True)
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args()

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    # Both conditions share the PoC 014 page vectors as the base. For xref we overlay
    # the freshly-embedded changed rows (emb-xref-changed.jsonl, keyed by row index) and
    # use the augmented chunk text for BM25.
    if args.chunk_cond == "page":
        rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    else:
        rows = [json.loads(l) for l in open(RAW / "chunks-xref.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    assert len(rows) == len(cvec), f"{len(rows)} rows vs {len(cvec)} page vecs"
    if args.chunk_cond == "xref":
        n_overlay = 0
        for l in open(RAW / "emb-xref-changed.jsonl"):
            d = json.loads(l); cvec[d["key"]] = d["vec"]; n_overlay += 1
        print(f"  overlaid {n_overlay} changed xref vectors onto the page base")
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    subvec = {}
    if args.query_cond == "decomp":
        subvec = {d["key"]: d["vec"] for d in map(json.loads, open(RAW / "emb-subqueries.jsonl"))}
        templates = json.loads((RAW / "decomp-templates.json").read_text())

    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    per_contract, per_cat = defaultdict(list), defaultdict(list)
    tk = args.topk
    for it in items:
        idxs = by_contract.get(it["contract"], [])
        if not idxs or it["qa_id"] not in qvec:
            continue
        gold = tuple(it["gold_words"]) if it.get("gold_words") else None
        use_decomp = args.query_cond == "decomp" and it["category"] in HARD \
            and all(f'{it["qa_id"]}#{k}' in subvec for k in range(len(templates.get(it["category"], []))))
        if not use_decomp:
            h = hybrid_rank(qvec[it["qa_id"]], terms(it["question"]), idxs, cvec, dterms)
            top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:tk]
            hit = any(covers(spans[idxs[j]], gold) for j in top)
        else:
            subs = templates[it["category"]]
            best = {}  # local-pos -> max hybrid across sub-queries
            for k, s in enumerate(subs):
                h = hybrid_rank(subvec[f'{it["qa_id"]}#{k}'], terms(s), idxs, cvec, dterms)
                for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:tk]:
                    best[j] = max(best.get(j, -1), h[j])
            top = sorted(best, key=lambda j: best[j], reverse=True)[:tk]
            hit = any(covers(spans[idxs[j]], gold) for j in top)
        per_contract[it["contract"]].append(1 if hit else 0)
        per_cat[it["category"]].append(1 if hit else 0)

    flat = [h for g in per_contract.values() for h in g]
    recall = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap(per_contract)
    cats = {c: (100 * sum(v) / len(v), len(v)) for c, v in per_cat.items()}
    hard_mean = sum(cats[c][0] for c in HARD if c in cats) / max(len([c for c in HARD if c in cats]), 1)
    res = {"chunk_cond": args.chunk_cond, "query_cond": args.query_cond,
           "recall": recall, "ci": [lo, hi], "n_items": len(flat),
           "hard_mean": hard_mean,
           "per_category": {c: {"recall": r, "n": n} for c, (r, n) in cats.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"recall-{args.chunk_cond}-{args.query_cond}.json").write_text(json.dumps(res, indent=2))
    print(f"[{args.chunk_cond}/{args.query_cond}] recall@{tk} = {recall:.1f}% (CI {lo:.1f}-{hi:.1f}), "
          f"hard-cat mean = {hard_mean:.1f}% over {len(flat)} items")
    if args.chunk_cond == "page" and args.query_cond == "raw":
        print("  VALIDATE: page/raw should reproduce PoC 014 page = 61.8%.")


if __name__ == "__main__":
    main()
