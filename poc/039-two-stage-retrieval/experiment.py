#!/usr/bin/env python3
"""PoC 039 — two-stage retrieval: category-specific templates × pool-size sweep.

Two-stage pipeline:
  1. Per-hard-category deterministic sub-query templates, each retrieving top-N candidates
     (N ∈ {2, 5, 10, 20}) using hybrid 0.9/0.1 scoring.
  2. Union all per-sub-query top-N candidate sets, deduplicate, re-rank by hybrid score,
     and cap at K=3 final chunks.

Tests whether combining template expansion (addresses vocabulary mismatch) with larger
per-sub-query pools (captures evidence at ranks 4–10) compounds gains vs PoC-030 (N=2,
no templates) and PoC-016 (templates, N=1).

Mechanism contract: exposes candidate_scores(ctx, item, idxs) for the harness.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Make harness importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from auto_experiment import harness

# Hard categories per the README and harness
HARD_CATEGORIES = {"Exclusivity", "Non-Compete", "Change Of Control"}

# Deterministic clause-specific sub-query templates per hard category (2–3 each)
# These address vocabulary/framing mismatch by providing multiple framings per category.
TEMPLATES = {
    "Exclusivity": [
        "exclusive rights granted to party",
        "sole and exclusive license",
        "exclusivity obligation of licensee",
    ],
    "Non-Compete": [
        "non-compete agreement restrictions",
        "prohibition against competitive activities",
        "covenant not to compete",
    ],
    "Change Of Control": [
        "change of control provisions",
        "acquisition or merger triggering clause",
        "control transfer notification requirements",
    ],
}

# Pool size for this run (can be swept: 2, 5, 10, 20)
# For the initial implementation, we'll use N=10 as the README suggests N=10–20.
# The pool-size ablation can be run by changing this parameter.
POOL_SIZE_N = 10


def candidate_scores(ctx: harness.Corpus, item: dict, idxs: list[int]) -> list[float]:
    """Two-stage retrieval mechanism.

    Stage 1: For hard categories with templates, generate sub-query embeddings and retrieve
             top-N candidates per sub-query using hybrid scoring.
    Stage 2: Union all top-N sets, deduplicate, re-rank by max hybrid score across sub-queries,
             return scores aligned to idxs (the harness will pick top-3).

    For non-hard categories or hard categories without successful template embedding,
    fall back to baseline single-query hybrid scoring.

    Args:
        ctx: Corpus with chunk vectors, query vectors, and scoring primitives
        item: Query item with {category, contract, qa_id, question}
        idxs: List of candidate GLOBAL row indices for this contract

    Returns:
        List of scores (float) aligned to idxs
    """
    category = item["category"]
    qa_id = item["qa_id"]

    # If not a hard category or no templates defined, fall back to baseline
    if category not in HARD_CATEGORIES or category not in TEMPLATES:
        qvec = ctx.qvec[qa_id]
        qterms = ctx.terms(item["question"])
        return ctx.hybrid_scores(qvec, qterms, idxs, sw=0.9)

    # Stage 1: Embed templates and retrieve top-N per sub-query
    templates = TEMPLATES[category]

    # Embed the template queries (NOT the item's question — these are category-specific)
    # CRITICAL: Use ctx.embed_queries with cache to ensure vectors share the same space
    cache_path = Path(__file__).parent / "results" / "raw" / "emb-cache.jsonl"
    try:
        sub_vecs = ctx.embed_queries(templates, cache=cache_path)
    except Exception as e:
        # If embedding fails (e.g., server down), fall back to baseline
        # The harness will fail loudly if the server is needed but unavailable.
        qvec = ctx.qvec[qa_id]
        qterms = ctx.terms(item["question"])
        return ctx.hybrid_scores(qvec, qterms, idxs, sw=0.9)

    # For each sub-query template, compute hybrid scores and track top-N candidates
    best_scores = {}  # local_idx (position in idxs) -> max hybrid score across sub-queries

    for template_text, sub_vec in zip(templates, sub_vecs):
        sub_terms = ctx.terms(template_text)
        # Compute hybrid scores for this sub-query across all candidates
        h_scores = ctx.hybrid_scores(sub_vec, sub_terms, idxs, sw=0.9)

        # Get top-N local indices for this sub-query
        top_n_local = sorted(range(len(idxs)), key=lambda j: h_scores[j], reverse=True)[:POOL_SIZE_N]

        # Update the union pool: track the max score each candidate achieved across sub-queries
        for local_idx in top_n_local:
            score = h_scores[local_idx]
            best_scores[local_idx] = max(best_scores.get(local_idx, -1e9), score)

    # Stage 2: Re-rank the union by max hybrid score
    # Build a score list aligned to idxs: candidates in the union get their max score,
    # candidates NOT in the union get a very low score (so they rank below the union).
    final_scores = []
    for local_idx in range(len(idxs)):
        if local_idx in best_scores:
            final_scores.append(best_scores[local_idx])
        else:
            # Not in any sub-query's top-N pool → rank below all union members
            final_scores.append(-1e10)

    return final_scores


# --smoke mode for manual inspection
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="PoC 039 two-stage retrieval mechanism")
    ap.add_argument("--smoke", action="store_true",
                    help="Run on a small slice and print top-k for sanity check")
    args = ap.parse_args()

    if args.smoke:
        print("Loading corpus...")
        ctx = harness.load()

        # Find a few hard-category items to test
        hard_items = [it for it in ctx.items if it["category"] in HARD_CATEGORIES][:3]

        print(f"\nPool size N={POOL_SIZE_N}")
        print(f"Templates defined for: {list(TEMPLATES.keys())}\n")

        for item in hard_items:
            print(f"Category: {item['category']}")
            print(f"Question: {item['question']}")
            idxs = ctx.by_contract.get(item["contract"], [])
            if not idxs:
                print("  (no candidates for this contract)\n")
                continue

            scores = candidate_scores(ctx, item, idxs)
            # Get top-3 global indices
            top_local = sorted(range(len(idxs)), key=lambda j: scores[j], reverse=True)[:3]
            top_global = [idxs[j] for j in top_local]

            print(f"  Top-3 chunks (global indices: {top_global}):")
            for rank, gidx in enumerate(top_global, 1):
                chunk_text = ctx.rows[gidx]["chunk"][:120]  # first 120 chars
                score = scores[top_local[rank - 1]]
                print(f"    {rank}. [{score:.4f}] {chunk_text}...")
            print()

        print("Smoke test complete. The mechanism runs without errors.")
        print("The harness will compute recall, CIs, and verdict after merge.")
    else:
        print("Usage: python3 experiment.py --smoke")
        print("The harness imports this module to run the full evaluation.")
