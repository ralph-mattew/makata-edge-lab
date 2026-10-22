#!/usr/bin/env python3
"""PoC 023 — per-category adaptive hybrid weight for the hard categories (OP-1).

Global sweeps (PoC-013) found alpha=0.9 (0.9 semantic / 0.1 BM25) optimal overall but left the
hard categories stuck. This tests whether a *category-specific* alpha — calibrated on a small
held-out split per hard category — lifts hard-category recall@3 without hurting overall, using
only routing logic on top of the existing retrieval (committed vectors; no model, no server).

For each hard category: hold out a seeded calibration split, sweep alpha in {0.1..0.9} on it, pick
the alpha maximising recall@3, and apply it to that category's eval items. All other categories
keep alpha=0.9. Compare per-category + overall recall@3 vs the global-alpha=0.9 baseline on the
SAME eval set (calibration items excluded from both, so no train-on-test).

Reuses committed PoC-014 vectors + PoC-007 items/spans. Run: python3 per-category-weight.py
"""
from __future__ import annotations
import argparse, json, math, random, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
ALPHAS = [round(0.1 * i, 1) for i in range(1, 10)]  # 0.1 .. 0.9


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--calib", type=int, default=20, help="calibration items per hard category")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    items = [it for it in items if it.get("gold_words") and it["contract"] in by_contract
             and it["qa_id"] in qvec]

    # Precompute, per item, the semantic cosines and normalized BM25 over its contract's chunks,
    # so an alpha sweep is just a reweighting (fast, no re-embedding / re-BM25).
    prep = {}  # qa_id -> (idxs, sem[list], bm[list], gold)
    for it in items:
        idxs = by_contract[it["contract"]]
        sem = [cosine(qvec[it["qa_id"]], cvec[i]) for i in idxs]
        bm = norm01(bm25(terms(it["question"]), [dterms[i] for i in idxs]))
        prep[it["qa_id"]] = (idxs, sem, bm, tuple(it["gold_words"]))

    def hit_at(qa_id, alpha):
        idxs, sem, bm, gold = prep[qa_id]
        h = [alpha * s + (1 - alpha) * b for s, b in zip(sem, bm)]
        top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
        return any(covers(spans[idxs[j]], gold) for j in top)

    def recall(ids, alpha):
        return 100 * sum(hit_at(q, alpha) for q in ids) / len(ids) if ids else 0.0

    # Split hard categories into calibration + eval
    rng = random.Random(args.seed)
    by_cat = defaultdict(list)
    for it in items:
        by_cat[it["category"]].append(it["qa_id"])
    calib_ids, eval_ids_hard = {}, {}
    for c in HARD:
        ids = sorted(by_cat.get(c, []))
        rng.shuffle(ids)
        calib_ids[c] = ids[:args.calib]
        eval_ids_hard[c] = ids[args.calib:]
    calib_all = {q for c in HARD for q in calib_ids[c]}
    eval_ids_all = [it["qa_id"] for it in items if it["qa_id"] not in calib_all]

    # Calibrate alpha per hard category on its calibration split
    chosen = {}
    for c in HARD:
        scores = {a: recall(calib_ids[c], a) for a in ALPHAS}
        best_a = max(ALPHAS, key=lambda a: (scores[a], -abs(a - 0.9)))  # tie-break toward 0.9
        chosen[c] = {"alpha": best_a, "calib_recall": scores[best_a],
                     "calib_recall_at_0.9": scores[0.9], "sweep": scores}

    # Evaluate (calibration items excluded). Per-category on hard eval splits; overall on eval_ids_all.
    percat = {}
    for c in HARD:
        ids = eval_ids_hard[c]
        r_global = recall(ids, 0.9)
        r_percat = recall(ids, chosen[c]["alpha"])
        percat[c] = {"alpha": chosen[c]["alpha"], "n": len(ids),
                     "recall_global_0.9": r_global, "recall_percat": r_percat,
                     "delta": r_percat - r_global}

    cat_of = {it["qa_id"]: it["category"] for it in items}
    overall_global = recall(eval_ids_all, 0.9)
    overall_percat = 100 * sum(
        hit_at(q, chosen[cat_of[q]]["alpha"] if cat_of[q] in HARD else 0.9) for q in eval_ids_all
    ) / len(eval_ids_all)

    OUT.mkdir(parents=True, exist_ok=True)
    res = {"calib_per_cat": args.calib, "seed": args.seed, "topk": args.topk,
           "chosen_alpha": {c: chosen[c]["alpha"] for c in HARD},
           "per_category": percat,
           "overall": {"recall_global_0.9": overall_global, "recall_percat": overall_percat,
                       "delta": overall_percat - overall_global, "n": len(eval_ids_all)},
           "calibration_detail": chosen}
    (OUT / "per-category-weight.json").write_text(json.dumps(res, indent=2))

    print(f"calibration: {args.calib} items/hard-cat (seed {args.seed}); eval excludes them\n")
    print(f"{'category':20} {'alpha*':>6} {'global@0.9':>11} {'per-cat':>9} {'Δ':>7}  (n)")
    for c in HARD:
        p = percat[c]
        print(f"{c:20} {p['alpha']:>6.1f} {p['recall_global_0.9']:>10.1f}% {p['recall_percat']:>8.1f}% "
              f"{p['delta']:>+6.1f}  (n={p['n']})")
    o = res["overall"]
    print(f"\noverall recall@3: global 0.9 = {o['recall_global_0.9']:.1f}%  ->  per-category = "
          f"{o['recall_percat']:.1f}%  (Δ {o['delta']:+.1f}, n={o['n']})")
    print("\nDecision rule: adopt if Exclusivity +>=5 AND overall regression <=1; "
          "reject if Exclusivity <+3 or overall regression >2.")
    for c in HARD:
        d = chosen[c]
        print(f"  {c}: alpha*={d['alpha']} (|Δ0.9|={abs(d['alpha']-0.9):.1f})  "
              f"calib {d['calib_recall_at_0.9']:.0f}%->{d['calib_recall']:.0f}%")


if __name__ == "__main__":
    main()
