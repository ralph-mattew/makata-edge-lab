#!/usr/bin/env python3
"""PoC 022 — UIBK-Embedding-v1 (179M) late-interaction MaxSim retrieval vs EmbeddingGemma.

UIBK-Embedding-v1 (DataScience-UIBK/uibk-embedding-v1, Apache 2.0) is a ColBERT-style model
whose plain MaxSim equals token-MaxSim + 0.75*dense-cosine in a single pass. We test whether it
lifts recall@3 on CUAD over the EmbeddingGemma 0.9/0.1 hybrid baseline (61.4%).

Host stage only: measures recall@3 (H1) and per-category recall incl. hard categories (H3).
H2 (<=420 MB device RAM) and the CoreML/ONNX export are DEVICE-bound and out of scope here
(parked like PoC-012) — this host run decides whether the retrieval quality is even worth the
device work.

Scorer reuses the validated recall path: PoC-007 items (gold word-spans) + PoC-014 chunk text +
per-chunk spans. Retrieval candidates for a query = that contract's chunks (same as 007/014).
recall@3 = top-3 cover >= 50% of the gold span (PoC-007 defn). Contract-level bootstrap CI.

Needs PyLate + the model (downloads on first use):
  pip install pylate
  python3 uibk-maxsim.py                 # full run (encodes all CUAD chunks)
  python3 uibk-maxsim.py --limit 100     # quick smoke
"""
from __future__ import annotations
import argparse, json, random, re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
MODEL = "DataScience-UIBK/uibk-embedding-v1"
EG_BASELINE = 61.4  # EmbeddingGemma hybrid recall@3 (PoC-007)


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
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()

    import numpy as np
    from pylate import models  # imported here so --help works without pylate

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    work = [it for it in items if it.get("gold_words") and it["contract"] in by_contract]
    if args.limit:
        work = work[:args.limit]
    # Group queries by contract so we only hold ONE contract's token vectors at a time
    # (ColBERT token-level vectors for all 79k chunks at once is multi-GB -> OOM).
    work_by_contract = defaultdict(list)
    for it in work:
        work_by_contract[it["contract"]].append(it)
    contracts = sorted(work_by_contract)
    print(f"items: {len(work)}  contracts: {len(contracts)}  model: {MODEL}")

    model = models.ColBERT(model_name_or_path=MODEL, trust_remote_code=True)

    per_cat, per_contract = defaultdict(list), defaultdict(list)
    done = 0
    CHUNK_SUB = 96  # stream a contract's chunks in sub-batches -> bounded memory on giant contracts
    for n, c in enumerate(contracts, 1):
        idxs = by_contract[c]
        its = work_by_contract[c]
        q_list = [np.asarray(e, dtype=np.float32) for e in
                  model.encode([it["question"] for it in its], is_query=True,
                               batch_size=args.batch, show_progress_bar=False)]
        # Stack all query tokens; MaxSim per (query,chunk) = segment-sum over query tokens of the
        # per-query-token max similarity to the chunk's tokens. Vectorized over queries via reduceat.
        Q = np.vstack(q_list)                                   # (sum_nq, 128)
        starts = np.cumsum([0] + [len(q) for q in q_list[:-1]]) # segment starts per query
        q_scores = np.zeros((len(its), len(idxs)), dtype=np.float32)
        for s in range(0, len(idxs), CHUNK_SUB):
            sub = idxs[s:s + CHUNK_SUB]
            d_emb = [np.asarray(e, dtype=np.float32) for e in
                     model.encode([rows[i]["chunk"] for i in sub], is_query=False,
                                  batch_size=args.batch, show_progress_bar=False)]
            for local, d in enumerate(d_emb):
                rowmax = (Q @ d.T).max(axis=1)                  # (sum_nq,)
                q_scores[:, s + local] = np.add.reduceat(rowmax, starts)
            del d_emb
        for qi, it in enumerate(its):
            top = np.argsort(-q_scores[qi])[:args.topk]
            hit = any(covers(spans[idxs[int(j)]], tuple(it["gold_words"])) for j in top)
            per_cat[it["category"]].append(1 if hit else 0)
            per_contract[c].append(1 if hit else 0)
        done += len(its)
        del q_list, Q, q_scores
        if n % 25 == 0 or n == len(contracts):
            print(f"  {n}/{len(contracts)} contracts, {done}/{len(work)} items", flush=True)

    flat = [h for g in per_contract.values() for h in g]
    recall = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap(per_contract)
    cats = {c: (100 * sum(v) / len(v), len(v)) for c, v in per_cat.items()}
    hard_mean = sum(cats[c][0] for c in HARD if c in cats) / max(len([c for c in HARD if c in cats]), 1)

    OUT.mkdir(parents=True, exist_ok=True)
    res = {"model": MODEL, "recall_at_k": recall, "ci": [lo, hi], "n_items": len(flat),
           "eg_baseline": EG_BASELINE, "delta_vs_eg": recall - EG_BASELINE,
           "hard_mean": hard_mean,
           "per_category": {c: {"recall": r, "n": n} for c, (r, n) in sorted(cats.items())}}
    (OUT / "uibk-maxsim.json").write_text(json.dumps(res, indent=2))

    print(f"\nUIBK MaxSim recall@{args.topk} = {recall:.1f}% (CI {lo:.1f}-{hi:.1f}) over {len(flat)} items")
    print(f"EmbeddingGemma baseline {EG_BASELINE:.1f}%  ->  Δ {recall-EG_BASELINE:+.1f}  "
          f"[adopt >= +3 (>=64.4%); reject < +1]")
    print(f"hard-category mean recall@{args.topk} = {hard_mean:.1f}")
    for c in HARD:
        if c in cats:
            print(f"  {c:20} {cats[c][0]:5.1f}%  (n={cats[c][1]})")


if __name__ == "__main__":
    main()
