#!/usr/bin/env python3
"""PoC 028 — Directional Posterior Feedback Fusion (DPFF): pseudo-relevance feedback on the query
embedding for hard-category retrieval (OP-1).

After an initial retrieval, move the query embedding toward the centroid of its top-k retrieved
chunks (Rocchio-style, direction-only), renormalise, and re-retrieve. Pure vector arithmetic on the
committed EmbeddingGemma vectors — no model, no server. Sweep alpha and feedback rounds.

Arms (hard categories = Exclusivity / Non-Compete / Change Of Control):
  - raw            : PoC-007/014 raw-query hybrid 0.9/0.1 top-3 (baseline)
  - decomp         : PoC-016 decomposed sub-queries, max-pool hybrid top-3 (baseline b)
  - raw+DPFF       : DPFF on the raw query
  - decomp+DPFF    : DPFF on each decomposed sub-query, then max-pool (the headline arm)

Update rule per round: q' = normalize( q + alpha * (centroid(top-k chunks) - q) ).
recall@3 = top-3 cover >=50% of the gold span (PoC-007 defn); contract-level bootstrap CI.

Run: python3 dpff.py
"""
from __future__ import annotations
import argparse, json, math, random, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
P016 = HERE.parent / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
ALPHAS = [0.1, 0.3, 0.5]
ROUNDS = [1, 2]


def dot(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())
def norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


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
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--sw", type=float, default=0.9)
    args = ap.parse_args()

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

    def rank_once(qv, qt, idxs):
        sem = [dot(qv, cvec[i]) for i in idxs]
        bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        h = [args.sw * s + (1 - args.sw) * b for s, b in zip(sem, bm)]
        return sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)

    def dpff_top(qv, qt, idxs, alpha, rounds):
        q = qv
        order = rank_once(q, qt, idxs)
        for _ in range(rounds):
            top = order[:args.topk]
            cen = [sum(cvec[idxs[j]][d] for j in top) / len(top) for d in range(len(q))]
            q = norm([q[d] + alpha * (cen[d] - q[d]) for d in range(len(q))])
            order = rank_once(q, qt, idxs)
        return order[:args.topk]

    def decomp_order(it, idxs, qmap, qtext_map, alpha=0.0, rounds=0):
        """016 max-pool over sub-queries; if alpha>0 apply DPFF to each sub-query first."""
        subs = templates[it["category"]]
        best = {}
        for k, s in enumerate(subs):
            qv = qmap[f'{it["qa_id"]}#{k}']; qt = terms(s)
            if alpha > 0:
                top = dpff_top(qv, qt, idxs, alpha, rounds)
                for rankpos, j in enumerate(top):
                    best[j] = max(best.get(j, -1), args.topk - rankpos)  # rank-based pool
            else:
                order = rank_once(qv, qt, idxs)
                for rankpos, j in enumerate(order[:args.topk]):
                    best[j] = max(best.get(j, -1), args.topk - rankpos)
        return sorted(best, key=lambda j: best[j], reverse=True)[:args.topk]

    # only items that have full decomposition vectors (hard cats) for the decomp arms
    def has_decomp(it):
        return it["category"] in HARD and all(f'{it["qa_id"]}#{k}' in subvec
                                              for k in range(len(templates.get(it["category"], []))))

    def evaluate(which, alpha=0.0, rounds=0):
        per_cat, per_contract = defaultdict(list), defaultdict(list)
        for it in items:
            idxs = by_contract[it["contract"]]; gold = tuple(it["gold_words"])
            if which == "raw":
                top = rank_once(qvec[it["qa_id"]], terms(it["question"]), idxs)[:args.topk]
            elif which == "raw_dpff":
                top = dpff_top(qvec[it["qa_id"]], terms(it["question"]), idxs, alpha, rounds)
            else:  # decomp / decomp_dpff — hard cats only; others fall back to raw
                if not has_decomp(it):
                    top = rank_once(qvec[it["qa_id"]], terms(it["question"]), idxs)[:args.topk]
                else:
                    top = decomp_order(it, idxs, subvec, None, alpha if which == "decomp_dpff" else 0.0, rounds)
            hit = any(covers(spans[idxs[j]], gold) for j in top)
            per_cat[it["category"]].append(hit); per_contract[it["contract"]].append(hit)
        return per_cat, per_contract

    def summ(per_cat, per_contract):
        flat = [h for g in per_contract.values() for h in g]
        overall = 100 * sum(flat) / len(flat) if flat else 0.0
        cats = {c: 100 * sum(per_cat[c]) / len(per_cat[c]) for c in per_cat if per_cat[c]}
        hard = sum(cats[c] for c in HARD if c in cats) / max(len([c for c in HARD if c in cats]), 1)
        return overall, hard, cats, bootstrap(per_contract)

    results = {}
    base_raw = summ(*evaluate("raw")); results["raw"] = base_raw
    base_dec = summ(*evaluate("decomp")); results["decomp"] = base_dec
    print(f"{'arm':22} {'overall':>8} {'hard':>6}  Excl / NonC / CoC")
    def show(tag, r):
        o, h, c, ci = r
        print(f"{tag:22} {o:7.1f}% {h:5.1f}  {c.get('Exclusivity',0):.0f}/{c.get('Non-Compete',0):.0f}/{c.get('Change Of Control',0):.0f}")
    show("raw (baseline)", base_raw); show("decomp (PoC-016)", base_dec)

    best = None
    for a in ALPHAS:
        for r in ROUNDS:
            rd = summ(*evaluate("decomp_dpff", a, r)); results[f"decomp_dpff_a{a}_r{r}"] = rd
            rr = summ(*evaluate("raw_dpff", a, r)); results[f"raw_dpff_a{a}_r{r}"] = rr
            show(f"decomp+DPFF a{a} r{r}", rd)
            cand = (rd[1] - base_dec[1], a, r, rd)
            if best is None or cand[0] > best[0]:
                best = cand
    dhard, ba, br, brd = best
    print(f"\nbest decomp+DPFF: alpha={ba} rounds={br}  hard-mean {brd[1]:.1f} vs decomp {base_dec[1]:.1f} (Δ {dhard:+.1f})")
    print(f"overall {brd[0]:.1f} vs decomp {base_dec[0]:.1f} (Δ {brd[0]-base_dec[0]:+.1f})")
    print("Decision: adopt if hard-mean +>=10 over decomp AND overall regression <=1; reject if <+5.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dpff.json").write_text(json.dumps(
        {k: {"overall": v[0], "hard_mean": v[1], "per_category": v[2], "ci": list(v[3])}
         for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    main()
