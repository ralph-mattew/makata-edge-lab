#!/usr/bin/env python3
"""PoC 032 — sparse-dense overlap diagnostic: does BM25 earn its 0.1 in the hybrid? (OP-3)

For every CUAD query, compare dense-only (1.0/0.0), BM25-only, and hybrid (0.9/0.1) top-3:
  - H1: on <15% of queries does a gold-covering chunk sit in BM25 top-3 but NOT dense top-3
        (sparse-exclusive coverage) — i.e. BM25 rarely contributes anything dense misses.
  - H2: dense-only recall@3 within 1pp of the 0.9/0.1 hybrid (>=60.4%).
Committed vectors only; no model/server. Run: python3 sparse-dense.py
"""
from __future__ import annotations
import argparse, json, math, re, time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = {"Exclusivity", "Non-Compete", "Change Of Control"}


def dot(a, b): return sum(x * y for x, y in zip(a, b))
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


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--topk", type=int, default=3); args = ap.parse_args()
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]
    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words") and json.loads(l)["contract"] in by_contract
             and json.loads(l)["qa_id"] in qvec]

    k = args.topk
    rec = defaultdict(lambda: defaultdict(list))  # arm -> cat -> [hits]
    sparse_excl = 0; sparse_excl_hard = 0; n_hard = 0
    t_bm = t_dense = 0.0
    for it in items:
        idxs = by_contract[it["contract"]]; gold = tuple(it["gold_words"]); cat = it["category"]
        t0 = time.time(); sem = [dot(qvec[it["qa_id"]], cvec[i]) for i in idxs]; t_dense += time.time() - t0
        t0 = time.time(); bmraw = bm25(terms(it["question"]), [dterms[i] for i in idxs]); t_bm += time.time() - t0
        bm = norm01(bmraw)
        dense_top = sorted(range(len(idxs)), key=lambda j: sem[j], reverse=True)[:k]
        bm_top = sorted(range(len(idxs)), key=lambda j: bm[j], reverse=True)[:k]
        hyb = [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]
        hyb_top = sorted(range(len(idxs)), key=lambda j: hyb[j], reverse=True)[:k]
        for arm, top in (("dense", dense_top), ("bm25", bm_top), ("hybrid", hyb_top)):
            hit = any(covers(spans[idxs[j]], gold) for j in top)
            rec[arm][cat].append(hit); rec[arm]["__all__"].append(hit)
        # sparse-exclusive: a gold-covering chunk in BM25 top-3 but not dense top-3
        dense_set = set(dense_top)
        excl = any(covers(spans[idxs[j]], gold) and j not in dense_set for j in bm_top)
        sparse_excl += excl
        if cat in HARD:
            n_hard += 1; sparse_excl_hard += excl

    def R(arm, cat="__all__"):
        v = rec[arm][cat]; return 100 * sum(v) / len(v) if v else 0.0

    n = len(items)
    sx = 100 * sparse_excl / n
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"n": n, "recall": {a: {"overall": R(a), **{c: R(a, c) for c in HARD}} for a in ("dense", "bm25", "hybrid")},
           "sparse_exclusive_pct": sx, "sparse_exclusive_hard_pct": 100 * sparse_excl_hard / max(n_hard, 1),
           "dense_vs_hybrid_delta": R("dense") - R("hybrid"),
           "host_bm25_ms_per_q": 1000 * t_bm / n, "host_dense_ms_per_q": 1000 * t_dense / n}
    (OUT / "sparse-dense.json").write_text(json.dumps(res, indent=2))

    print(f"items: {n}\n")
    print(f"{'arm':10} {'overall':>8}  Excl / NonC / CoC")
    for a in ("dense", "bm25", "hybrid"):
        print(f"{a:10} {R(a):7.1f}%  {R(a,'Exclusivity'):.0f}/{R(a,'Non-Compete'):.0f}/{R(a,'Change Of Control'):.0f}")
    print(f"\nsparse-exclusive coverage: {sx:.1f}% overall ({res['sparse_exclusive_hard_pct']:.1f}% on hard)  [H1 <15%]")
    print(f"dense-only vs hybrid recall@3: {R('dense'):.1f} vs {R('hybrid'):.1f}  (Δ {R('dense')-R('hybrid'):+.1f})  [H2 within 1pp & >=60.4]")
    print(f"host BM25 cost: {res['host_bm25_ms_per_q']:.1f} ms/q (vs dense {res['host_dense_ms_per_q']:.1f} ms/q) [H3 device latency]")
    h1 = sx < 15; h2 = abs(R('dense') - R('hybrid')) <= 1.0 and R('dense') >= 60.4
    print(f"\nH1 {'PASS' if h1 else 'FAIL'} · H2 {'PASS' if h2 else 'FAIL'} -> "
          f"{'ADOPT dense-only (drop BM25)' if (h1 and h2) else ('REJECT' if R('dense')<60.4 else 'INCONCLUSIVE')}")


if __name__ == "__main__":
    main()
