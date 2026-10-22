#!/usr/bin/env python3
"""PoC 025 — evidence-retention depth diagnostic (OP-1).

Where do the gold chunks rank under the current hybrid 0.9/0.1 retrieval? This decides whether a
wider candidate pool + reranking (the sibling reranking proposal) could help at all:

  - If hard-category gold chunks sit at rank 4-10 (retrieved but truncated before top-3), a reranker
    has something to recover.
  - If they're beyond top-10 or not retrieved at all, depth/reranking is futile and the bottleneck is
    the embedder representation (consistent with PoC-013 / PoC-023).

Reports, per category (hard called out) and overall: recall@{1,3,5,10,20} and the rank histogram of
the best-covering gold chunk (top-3 / 4-10 / 11-20 / 21+ / never-covers). "Covers" = chunk span
overlaps >=50% of the gold span (PoC-007 defn). Committed vectors only — no model, no server.

Also checks the registration's H2 intervention claim ("filter top-10 then take top-3 by combined
score"): proves it is a no-op vs the hybrid top-3 (filtering low-scoring candidates cannot promote
anything into the top-3), so the only real lever on a wider pool is a *different* scorer (reranker).

Run: python3 evidence-depth.py
"""
from __future__ import annotations
import argparse, json, math, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = {"Exclusivity", "Non-Compete", "Change Of Control"}
KS = [1, 3, 5, 10, 20]


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


def bucket(rank):
    if rank is None: return "never"
    if rank <= 3: return "top3"
    if rank <= 10: return "r4_10"
    if rank <= 20: return "r11_20"
    return "r21+"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--sw", type=float, default=0.9); args = ap.parse_args()
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words")]
    items = [it for it in items if it["contract"] in by_contract and it["qa_id"] in qvec]

    recall_hits = {k: defaultdict(list) for k in KS}      # k -> category -> [0/1]
    buckets = defaultdict(lambda: Counter())               # category -> bucket counts
    for it in items:
        idxs = by_contract[it["contract"]]
        sem = [cosine(qvec[it["qa_id"]], cvec[i]) for i in idxs]
        bm = norm01(bm25(terms(it["question"]), [dterms[i] for i in idxs]))
        h = [args.sw * s + (1 - args.sw) * b for s, b in zip(sem, bm)]
        order = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)
        gold = tuple(it["gold_words"])
        # rank (1-based) of the best-covering gold chunk
        gold_rank = None
        for pos, j in enumerate(order, 1):
            if covers(spans[idxs[j]], gold):
                gold_rank = pos; break
        cat = it["category"]
        for k in KS:
            recall_hits[k][cat].append(1 if (gold_rank is not None and gold_rank <= k) else 0)
            recall_hits[k]["__all__"].append(1 if (gold_rank is not None and gold_rank <= k) else 0)
        buckets[cat][bucket(gold_rank)] += 1
        buckets["__all__"][bucket(gold_rank)] += 1

    def rec(cat, k):
        v = recall_hits[k][cat]; return 100 * sum(v) / len(v) if v else 0.0

    cats = ["__all__"] + sorted(c for c in buckets if c != "__all__")
    print("recall@k by category (hard *):")
    print(f"{'category':22} " + " ".join(f"@{k:>2}" for k in KS))
    for c in cats:
        tag = "*" if c in HARD else (" " if c != "__all__" else " ")
        name = "OVERALL" if c == "__all__" else c
        print(f"{tag}{name:21} " + " ".join(f"{rec(c,k):4.0f}" for k in KS))

    print("\ngold-chunk rank histogram (share of items):")
    print(f"{'category':22} {'top3':>6} {'r4-10':>6} {'r11-20':>7} {'r21+':>6} {'never':>6}  gap(4-10)")
    recoverable = {}
    for c in cats:
        tot = sum(buckets[c].values()) or 1
        b = buckets[c]
        gap = 100 * b['r4_10'] / tot
        recoverable[c] = gap
        name = "OVERALL" if c == "__all__" else c
        tag = "*" if c in HARD else " "
        print(f"{tag}{name:21} {100*b['top3']/tot:5.0f}% {100*b['r4_10']/tot:5.0f}% "
              f"{100*b['r11_20']/tot:6.0f}% {100*b['r21+']/tot:5.0f}% {100*b['never']/tot:5.0f}% {gap:9.1f}%")

    hard_gap = sum(buckets[c]['r4_10'] for c in HARD) / max(sum(sum(buckets[c].values()) for c in HARD), 1) * 100
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"sw": args.sw,
           "recall_at_k": {c: {k: rec(c, k) for k in KS} for c in cats},
           "rank_buckets": {c: dict(buckets[c]) for c in cats},
           "hard_cat_gap_4_10_pct": hard_gap,
           "n_items": len(items)}
    (OUT / "evidence-depth.json").write_text(json.dumps(res, indent=2))

    print(f"\nH1 (>=15% of hard-cat gold in rank 4-10, i.e. recoverable by a wider pool): "
          f"hard-cat 4-10 gap = {hard_gap:.1f}%  -> {'PASS' if hard_gap >= 15 else 'FAIL'}")
    print("Note: the registration's H2 'filter top-10 then take top-3 by combined score' is a NO-OP for")
    print("recall@3 — removing lower-scored candidates cannot promote anything into the top-3. The only")
    print("lever on a wider pool is a DIFFERENT scorer (cross-encoder reranker = the sibling proposal).")


if __name__ == "__main__":
    main()
