#!/usr/bin/env python3
"""PoC 033 — per-category selective fusion routing (disable BM25 for hard categories) (OP-1).

The "fusion tax" per-category follow-up to PoC-032: route Exclusivity / Non-Compete / Change-of-Control
queries to dense-only (1.0/0.0) while keeping the 0.9/0.1 hybrid elsewhere. Does each hard category
gain ≥+5pp recall@3, overall not dropping >1pp? Committed vectors only — no model/server.

Reports per hard category: hybrid vs dense-only vs sparse-only recall@3; the routed policy (dense for
hard cats, hybrid otherwise) overall; and an oracle per-category best-of{hybrid,dense}. Run:
  python3 selective-fusion.py
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
    # per item, precompute hit under each scorer
    hit = defaultdict(dict)  # qa_id -> scorer -> bool ; and cat map
    cat = {}
    for it in items:
        idxs = by_contract[it["contract"]]; gold = tuple(it["gold_words"]); cat[it["qa_id"]] = it["category"]
        sem = [dot(qvec[it["qa_id"]], cvec[i]) for i in idxs]
        bm = norm01(bm25(terms(it["question"]), [dterms[i] for i in idxs]))
        semn = norm01(sem)
        for name, score in (("dense", sem),
                            ("sparse", bm),
                            ("hybrid", [0.9 * s + 0.1 * b for s, b in zip(semn, bm)])):
            top = sorted(range(len(idxs)), key=lambda j: score[j], reverse=True)[:k]
            hit[it["qa_id"]][name] = any(covers(spans[idxs[j]], gold) for j in top)

    def recall(ids, scorer): return 100 * sum(hit[q][scorer] for q in ids) / len(ids) if ids else 0.0
    by_cat = defaultdict(list)
    for q, c in cat.items():
        by_cat[c].append(q)
    allids = list(cat)

    print(f"{'category':20} {'hybrid':>7} {'dense':>7} {'sparse':>7}   {'dense-hybrid':>12}")
    percat = {}
    for c in HARD:
        ids = by_cat[c]; h = recall(ids, "hybrid"); d = recall(ids, "dense"); s = recall(ids, "sparse")
        percat[c] = {"hybrid": h, "dense": d, "sparse": s, "dense_minus_hybrid": d - h}
        print(f"{c:20} {h:6.1f}% {d:6.1f}% {s:6.1f}%   {d-h:+11.1f}")

    overall_hybrid = recall(allids, "hybrid")
    # routed policy: dense for hard cats, hybrid elsewhere
    routed = 100 * sum((hit[q]["dense"] if cat[q] in HARD else hit[q]["hybrid"]) for q in allids) / len(allids)
    # oracle per-category best of {hybrid, dense} (upper bound for routing)
    best_scorer = {c: ("dense" if percat.get(c, {}).get("dense_minus_hybrid", 0) > 0 else "hybrid") for c in set(cat.values())}
    oracle = 100 * sum(hit[q][best_scorer[cat[q]]] for q in allids) / len(allids)

    OUT.mkdir(parents=True, exist_ok=True)
    res = {"per_category_hard": percat, "overall_hybrid": overall_hybrid,
           "overall_routed_dense_hardcats": routed, "overall_oracle_percat_bestof": oracle,
           "hard_mean_hybrid": sum(percat[c]["hybrid"] for c in HARD) / 3,
           "hard_mean_routed": sum(percat[c]["dense"] for c in HARD) / 3}
    (OUT / "selective-fusion.json").write_text(json.dumps(res, indent=2))

    print(f"\noverall recall@3: hybrid {overall_hybrid:.1f} -> routed(dense@hard) {routed:.1f} "
          f"(Δ {routed-overall_hybrid:+.1f})  [H2: overall drop <=1pp]")
    print(f"hard-mean: hybrid {res['hard_mean_hybrid']:.1f} -> dense@hard {res['hard_mean_routed']:.1f}")
    print(f"oracle per-category best-of{{hybrid,dense}} overall: {oracle:.1f}")
    gains = {c: percat[c]["dense_minus_hybrid"] for c in HARD}
    n_lt3 = sum(1 for c in HARD if gains[c] < 3)
    print(f"\nDECISION: adopt if ALL hard cats +>=5 AND overall drop<=1; reject if <+3 on any two of three.")
    print(f"  per-cat dense-vs-hybrid: " + ", ".join(f"{c.split()[0]} {gains[c]:+.1f}" for c in HARD))
    verdict = "ADOPT" if all(g >= 5 for g in gains.values()) and (routed - overall_hybrid) >= -1 else \
              ("REJECT" if n_lt3 >= 2 else "INCONCLUSIVE")
    print(f"  -> {verdict}  ({n_lt3}/3 hard cats gain <+3pp)")


if __name__ == "__main__":
    main()
