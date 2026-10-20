#!/usr/bin/env python3
"""PoC 015 — per-category recall@3 for one query-transform condition.

Chunks fixed = PoC 014 page chunks + emb-page. Query varies:
  raw      : PoC 014 emb-queries (per-item vector)
  gloss    : the category's gloss vector (one per category)
  keywords : the category's keyword vector
  decomp   : union of top-3 per category sub-query, re-ranked by max hybrid

Categories lacking a variant fall back to the raw question. Hybrid 0.9/0.1, top-3,
recall = top-3 cover >=50% of gold span (PoC 007). Contract-level bootstrap CIs.
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
WEAK = {"Exclusivity", "Non-Compete", "Agreement Date", "Warranty Duration",
        "Liquidated Damages", "Cap On Liability"}


def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())


def bm25(qt, docs, k1=1.5, b=0.75):
    N = len(docs); avgdl = sum(len(d) for d in docs) / max(N, 1)
    df = Counter(t for d in docs for t in set(d))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    return [sum(idf.get(t, 0) * (Counter(d)[t] * (k1 + 1)) /
               (Counter(d)[t] + k1 * (1 - b + b * len(d) / avgdl)) for t in qt) for d in docs]


def norm01(xs):
    lo, hi = min(xs, default=0), max(xs, default=0)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def covers(span, gold, frac=0.5):
    if not span or not gold: return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def bootstrap(pc, n=10000, seed=0):
    random.seed(seed); groups = list(pc.values()); boot = []
    for _ in range(n):
        xs = [h for g in (random.choice(groups) for _ in groups) for h in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def rank(qvec, qterms, idxs, cvec, dterms, sw=0.9):
    sem = [cosine(qvec, cvec[i]) for i in idxs]
    bm = norm01(bm25(qterms, [dterms[i] for i in idxs]))
    return [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", choices=["raw", "gloss", "keywords", "decomp"], required=True)
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args()

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qraw = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    variants = json.loads((RAW / "query-variants.json").read_text())
    vvec = {}
    if args.cond != "raw":
        vvec = {d["key"]: d["vec"] for d in map(json.loads, open(RAW / "emb-queryvariants.jsonl"))}

    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    per_contract, per_cat = defaultdict(list), defaultdict(list)
    tk = args.topk
    for it in items:
        idxs = by_contract.get(it["contract"], [])
        if not idxs or it["qa_id"] not in qraw:
            continue
        cat = it["category"]; gold = tuple(it["gold_words"]) if it.get("gold_words") else None
        has_var = cat in variants
        if args.cond == "raw" or not has_var:
            h = rank(qraw[it["qa_id"]], terms(it["question"]), idxs, cvec, dterms)
            top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:tk]
        elif args.cond in ("gloss", "keywords"):
            key = f"{cat}::{args.cond}"
            qt = terms(variants[cat][args.cond if args.cond == "gloss" else "keywords"])
            h = rank(vvec[key], qt, idxs, cvec, dterms)
            top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:tk]
        else:  # decomp
            subs = variants[cat]["subqueries"]; best = {}
            for k, s in enumerate(subs):
                h = rank(vvec[f"{cat}::sub{k}"], terms(s), idxs, cvec, dterms)
                for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:tk]:
                    best[j] = max(best.get(j, -1), h[j])
            top = sorted(best, key=lambda j: best[j], reverse=True)[:tk]
        hit = any(covers(spans[idxs[j]], gold) for j in top)
        per_contract[it["contract"]].append(1 if hit else 0)
        per_cat[cat].append(1 if hit else 0)

    flat = [h for g in per_contract.values() for h in g]
    recall = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap(per_contract)
    cats = {c: (100 * sum(v) / len(v), len(v)) for c, v in per_cat.items()}
    weak_mean = sum(cats[c][0] for c in WEAK if c in cats) / max(len([c for c in WEAK if c in cats]), 1)
    res = {"cond": args.cond, "recall": recall, "ci": [lo, hi], "n_items": len(flat),
           "weak_mean": weak_mean,
           "per_category": {c: {"recall": r, "n": n} for c, (r, n) in cats.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"recall-{args.cond}.json").write_text(json.dumps(res, indent=2))
    print(f"[{args.cond}] recall@{tk} = {recall:.1f}% (CI {lo:.1f}-{hi:.1f}), "
          f"weak-cat mean = {weak_mean:.1f}% over {len(flat)} items")
    if args.cond == "raw":
        print("  VALIDATE: raw should reproduce PoC 014/016 page = 61.8%.")


if __name__ == "__main__":
    main()
