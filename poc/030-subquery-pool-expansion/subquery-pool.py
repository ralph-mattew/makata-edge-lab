#!/usr/bin/env python3
"""PoC 030 — expanded per-sub-query candidate pool before union (OP-1).

PoC-016 decomposition takes top-1 per sub-query before the union; a relevant chunk a sub-query
ranks at 2-5 is discarded. This sweeps the per-sub-query pool size N in {1,2,3,5}: retrieve top-N
per sub-query (hybrid 0.9/0.1), union+dedupe, re-rank the union by max sub-query hybrid score, take
final K=3. Measures hard-category + overall recall@3 vs the single-query (raw) baseline and vs the
N=1 decomposition baseline. Committed vectors only — no model, no server.

Run: python3 subquery-pool.py
"""
from __future__ import annotations
import argparse, json, math, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
P016 = HERE.parent / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
NS = [1, 2, 3, 5]


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
    ap = argparse.ArgumentParser(); ap.add_argument("--topk", type=int, default=3); ap.add_argument("--sw", type=float, default=0.9); args = ap.parse_args()
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    subvec = {d["key"]: d["vec"] for d in map(json.loads, open(P016 / "emb-subqueries.jsonl"))}
    templates = json.loads((P016 / "decomp-templates.json").read_text())
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    items = [it for it in items if it.get("gold_words") and it["contract"] in by_contract and it["qa_id"] in qvec]

    def hybrid(qv, qt, idxs):
        sem = [dot(qv, cvec[i]) for i in idxs]
        bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        return [args.sw * s + (1 - args.sw) * b for s, b in zip(sem, bm)]

    def raw_top(it, idxs):
        h = hybrid(qvec[it["qa_id"]], terms(it["question"]), idxs)
        return sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]

    def has_decomp(it):
        return it["category"] in HARD and all(f'{it["qa_id"]}#{k}' in subvec
                                              for k in range(len(templates.get(it["category"], []))))

    def decomp_pool_top(it, idxs, N):
        """top-N per sub-query -> union -> re-rank union by max sub-query hybrid score -> top-K."""
        subs = templates[it["category"]]
        best = {}  # local idx -> max hybrid score across sub-queries (only among each sub-query's top-N)
        for k, s in enumerate(subs):
            h = hybrid(subvec[f'{it["qa_id"]}#{k}'], terms(s), idxs)
            for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:N]:
                best[j] = max(best.get(j, -1e9), h[j])
        return sorted(best, key=lambda j: best[j], reverse=True)[:args.topk]

    def evaluate(mode, N=1):
        per_cat, per_contract = defaultdict(list), defaultdict(list)
        for it in items:
            idxs = by_contract[it["contract"]]; gold = tuple(it["gold_words"])
            if mode == "raw" or not has_decomp(it):
                top = raw_top(it, idxs)
            else:
                top = decomp_pool_top(it, idxs, N)
            hit = any(covers(spans[idxs[j]], gold) for j in top)
            per_cat[it["category"]].append(hit); per_contract[it["contract"]].append(hit)
        flat = [h for g in per_contract.values() for h in g]
        overall = 100 * sum(flat) / len(flat)
        cats = {c: 100 * sum(per_cat[c]) / len(per_cat[c]) for c in per_cat if per_cat[c]}
        hard = sum(cats[c] for c in HARD if c in cats) / len([c for c in HARD if c in cats])
        return overall, hard, cats

    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    rawo, rawh, rawc = evaluate("raw"); res["raw"] = {"overall": rawo, "hard_mean": rawh, "per_category": rawc}
    print(f"{'arm':16} {'overall':>8} {'hard':>6}  Excl / NonC / CoC")
    print(f"{'raw (single-q)':16} {rawo:7.1f}% {rawh:5.1f}  {rawc.get('Exclusivity',0):.0f}/{rawc.get('Non-Compete',0):.0f}/{rawc.get('Change Of Control',0):.0f}")
    best = None
    for N in NS:
        o, h, c = evaluate("decomp", N); res[f"N{N}"] = {"overall": o, "hard_mean": h, "per_category": c}
        tag = f"decomp N={N}" + (" (PoC-016)" if N == 1 else "")
        print(f"{tag:16} {o:7.1f}% {h:5.1f}  {c.get('Exclusivity',0):.0f}/{c.get('Non-Compete',0):.0f}/{c.get('Change Of Control',0):.0f}")
        if best is None or h > best[1]:
            best = (N, h, o, c)
    (OUT / "subquery-pool.json").write_text(json.dumps(res, indent=2))
    N1 = res["N1"]
    bN, bh, bo, bc = best
    print(f"\nbest N={bN}: hard-mean {bh:.1f}")
    print(f"  vs raw single-query (hard {rawh:.1f}): Δ {bh-rawh:+.1f}  [H1 adopt >=+10]")
    print(f"  vs decomp N=1 (hard {N1['hard_mean']:.1f}): Δ {bh-N1['hard_mean']:+.1f}  [reject if <+3 at all N]")
    print(f"  Exclusivity {bc.get('Exclusivity',0):.0f}% [H2 >=30]  · overall {bo:.1f} vs decomp-N1 {N1['overall']:.1f} (Δ {bo-N1['overall']:+.1f}) [H3 regression <=2]")


if __name__ == "__main__":
    main()
