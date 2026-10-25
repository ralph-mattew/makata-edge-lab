#!/usr/bin/env python3
"""PoC 035 — binary (1-bit) quantized stored index vs float32 (OP-3).

Binarise the committed EmbeddingGemma chunk vectors to sign bits (768-dim float32 -> 768 bits = 96
bytes, 32x smaller). Measure recall@3 under:
  - float32 hybrid 0.9/0.1 (baseline),
  - binary hybrid (sign-dot semantic + BM25), no re-rank,
  - binary candidate-gen (top-50 by binary) -> exact float32 cosine re-rank -> top-3.
Reports overall + hard-category recall@3 and the index-size saving. Committed vectors only; no server.

Run: python3 binary-index.py
"""
from __future__ import annotations
import argparse, json, math, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]


def dot(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())
def sign(v): return [1 if x >= 0 else -1 for x in v]
def sdot(a, b): return sum(1 if x == y else -1 for x, y in zip(a, b))  # sign-dot of +-1 vectors


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
    ap = argparse.ArgumentParser(); ap.add_argument("--topk", type=int, default=3); ap.add_argument("--pool", type=int, default=50); args = ap.parse_args()
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    cbin = [sign(v) for v in cvec]
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
    rec = {m: defaultdict(list) for m in ("float", "binary", "binary_rerank")}
    for it in items:
        idxs = by_contract[it["contract"]]; gold = tuple(it["gold_words"]); c = it["category"]
        q = qvec[it["qa_id"]]; qb = sign(q); qt = terms(it["question"])
        bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        # float hybrid
        semf = norm01([dot(q, cvec[i]) for i in idxs])
        hf = [0.9 * s + 0.1 * b for s, b in zip(semf, bm)]
        topf = sorted(range(len(idxs)), key=lambda j: hf[j], reverse=True)[:k]
        # binary hybrid (sign-dot)
        semb = norm01([sdot(qb, cbin[i]) for i in idxs])
        hb = [0.9 * s + 0.1 * b for s, b in zip(semb, bm)]
        order_b = sorted(range(len(idxs)), key=lambda j: hb[j], reverse=True)
        topb = order_b[:k]
        # binary candidate pool -> exact float cosine re-rank
        pool = order_b[:args.pool]
        rr = sorted(pool, key=lambda j: dot(q, cvec[idxs[j]]), reverse=True)[:k]
        for m, top in (("float", topf), ("binary", topb), ("binary_rerank", rr)):
            hit = any(covers(spans[idxs[j]], gold) for j in top)
            rec[m][c].append(hit); rec[m]["__all__"].append(hit)

    def R(m, c="__all__"):
        v = rec[m][c]; return 100 * sum(v) / len(v) if v else 0.0

    n_chunks = len(rows)
    float_mb = n_chunks * 768 * 4 / 1e6
    bin_mb = n_chunks * 768 / 8 / 1e6
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"n_chunks": n_chunks, "index_float_MB": float_mb, "index_binary_MB": bin_mb,
           "freed_MB": float_mb - bin_mb,
           "recall": {m: {"overall": R(m), **{c: R(m, c) for c in HARD}} for m in rec}}
    (OUT / "binary-index.json").write_text(json.dumps(res, indent=2))

    print(f"index: float32 {float_mb:.0f} MB -> binary {bin_mb:.1f} MB  (frees {float_mb-bin_mb:.0f} MB, 32x)  [H2 >=200MB? note: {n_chunks} chunks]")
    print(f"\n{'mode':16} {'overall':>8}  Excl / NonC / CoC")
    for m in ("float", "binary", "binary_rerank"):
        print(f"{m:16} {R(m):7.1f}%  {R(m,'Exclusivity'):.0f}/{R(m,'Non-Compete'):.0f}/{R(m,'Change Of Control'):.0f}")
    dfl = R("float")
    print(f"\nH1 (binary+rerank within 2pp of float): {R('binary_rerank'):.1f} vs {dfl:.1f} "
          f"(Δ {R('binary_rerank')-dfl:+.1f})  -> {'PASS' if R('binary_rerank') >= dfl-2 else 'FAIL'}")
    print(f"   pure binary (no rerank): {R('binary'):.1f} (Δ {R('binary')-dfl:+.1f})")
    hard_gap = (sum(R('binary_rerank',c) for c in HARD) - sum(R('float',c) for c in HARD))/3
    print(f"H4 (hard-cat not meaningfully worse): hard-mean Δ {hard_gap:+.1f}")


if __name__ == "__main__":
    main()
