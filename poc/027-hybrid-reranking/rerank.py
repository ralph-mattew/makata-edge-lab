#!/usr/bin/env python3
"""PoC 027 — cross-encoder reranking of a hybrid top-10 pool (OP-1), executes PoC-012's host stage.

Retrieve top-10 via hybrid 0.9/0.1 (committed PoC-014 vectors), rerank the 10 chunk texts against the
question with a cross-encoder, take top-3, measure recall@3 overall + per hard category vs the hybrid
top-3 baseline. PoC-025 established the ceiling (a perfect top-10 reranker = recall@10): overall 79,
Non-Compete 51, Exclusivity 25, Change-of-Control 78 — so reranking can only help where gold is in
the top-10 (Non-Compete; not Exclusivity, whose gold is mostly rank 21+).

No llama server — committed vectors for retrieval + a sentence-transformers CrossEncoder (MPS/CPU)
for reranking. H3 (on-device latency ≤4s) is device-bound (parked like PoC-012); host rerank latency
is logged as INFERRED.

Run: python3 rerank.py                                  # default ms-marco-MiniLM-L-6-v2
     python3 rerank.py --model BAAI/bge-reranker-base   # stronger/heavier
"""
from __future__ import annotations
import argparse, json, math, random, re, time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
EG_BASELINE = 61.4


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
    if not span or not gold:
        return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed); groups = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for g in (random.choice(groups) for _ in groups) for v in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    ap.add_argument("--pool", type=int, default=10)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    from sentence_transformers import CrossEncoder

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    items = [it for it in items if it.get("gold_words") and it["contract"] in by_contract and it["qa_id"] in qvec]
    if args.limit:
        items = items[:args.limit]
    print(f"items: {len(items)}  reranker: {args.model}  pool: top-{args.pool}")

    ce = CrossEncoder(args.model)

    base_cat, base_contract = defaultdict(list), defaultdict(list)
    rr_cat, rr_contract = defaultdict(list), defaultdict(list)
    t_rr = 0.0; n_rr = 0
    for w, it in enumerate(items, 1):
        idxs = by_contract[it["contract"]]
        sem = [cosine(qvec[it["qa_id"]], cvec[i]) for i in idxs]
        bm = norm01(bm25(terms(it["question"]), [dterms[i] for i in idxs]))
        h = [0.9 * s + 0.1 * b for s, b in zip(sem, bm)]
        order = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)
        gold = tuple(it["gold_words"]); cat = it["category"]

        base_top = order[:args.topk]
        base_hit = any(covers(spans[idxs[j]], gold) for j in base_top)
        base_cat[cat].append(base_hit); base_contract[it["contract"]].append(base_hit)

        pool = order[:args.pool]
        pairs = [[it["question"], rows[idxs[j]]["chunk"]] for j in pool]
        t0 = time.time(); scores = ce.predict(pairs, show_progress_bar=False); t_rr += time.time() - t0; n_rr += 1
        reranked = [pool[k] for k in sorted(range(len(pool)), key=lambda k: scores[k], reverse=True)[:args.topk]]
        rr_hit = any(covers(spans[idxs[j]], gold) for j in reranked)
        rr_cat[cat].append(rr_hit); rr_contract[it["contract"]].append(rr_hit)
        if w % 200 == 0:
            print(f"  {w}/{len(items)}")

    def recall(d):
        flat = [h for g in d.values() for h in g]; return 100 * sum(flat) / len(flat) if flat else 0.0
    def catrec(d, c): return 100 * sum(d[c]) / len(d[c]) if d.get(c) else 0.0

    base_overall, rr_overall = recall(base_contract), recall(rr_contract)
    lo, hi = bootstrap(rr_contract)
    res = {"model": args.model, "pool": args.pool, "n_items": sum(len(v) for v in base_cat.values()),
           "baseline_overall": base_overall, "reranked_overall": rr_overall,
           "reranked_ci": [lo, hi], "delta_overall": rr_overall - base_overall,
           "per_category": {c: {"baseline": catrec(base_cat, c), "reranked": catrec(rr_cat, c),
                                "delta": catrec(rr_cat, c) - catrec(base_cat, c), "n": len(base_cat.get(c, []))}
                            for c in sorted(base_cat)},
           "host_rerank_ms_per_query": 1000 * t_rr / max(n_rr, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rerank.json").write_text(json.dumps(res, indent=2))

    print(f"\noverall recall@3: baseline {base_overall:.1f}% -> reranked {rr_overall:.1f}% "
          f"(CI {lo:.1f}-{hi:.1f}, Δ {rr_overall-base_overall:+.1f})")
    print(f"{'category':20} {'base':>6} {'rerank':>7} {'Δ':>6}")
    for c in sorted(base_cat):
        tag = "*" if c in HARD else " "
        print(f"{tag}{c:19} {catrec(base_cat,c):>5.1f}% {catrec(rr_cat,c):>6.1f}% {catrec(rr_cat,c)-catrec(base_cat,c):>+5.1f}")
    print(f"\nhost rerank latency: {res['host_rerank_ms_per_query']:.0f} ms/query (INFERRED; device H3 is on-iPhone)")
    print("Decision: adopt if overall +>=3 AND >=1 hard cat +>=5 (AND device latency<=4s); reject if overall <+1.")


if __name__ == "__main__":
    main()
