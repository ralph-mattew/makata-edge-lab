#!/usr/bin/env python3
"""PoC 010: Compute recall for BM25-only retrieval.

Reuses PoC 007's data (chunks, items, BM25 scores) to compute recall
when using pure BM25 scoring (no embeddings).

Usage:
    python3 compute-recall.py
"""

import json
from pathlib import Path
from collections import defaultdict

# Paths
HERE = Path(__file__).resolve().parent
POC007 = HERE.parent / '007-embedding-retrieval-recall'
RAW = POC007 / 'results' / 'raw'

def load_items():
    """Load all 1,325 items."""
    with open(RAW / 'items.jsonl', encoding='utf-8') as f:
        return [json.loads(line) for line in f]

def load_chunks_index():
    """Load chunk word ranges."""
    with open(RAW / 'chunks-index.jsonl', encoding='utf-8') as f:
        return {json.loads(line)['contract']: json.loads(line)
                for line in f}

def load_bm25_scores():
    """Load BM25 scores for all items."""
    scores = {}
    with open(RAW / 'scores-bm25.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            scores[data['item']] = data['scores']
    return scores

def chunk_covers_answer(chunk_range, gold_words, min_coverage=0.5):
    """Check if a chunk covers at least min_coverage of the answer span."""
    chunk_start, chunk_end, page = chunk_range
    gold_start, gold_end = gold_words

    # Calculate overlap
    overlap_start = max(chunk_start, gold_start)
    overlap_end = min(chunk_end, gold_end)

    if overlap_start > overlap_end:
        return False  # No overlap

    overlap_words = overlap_end - overlap_start + 1
    gold_words_count = gold_end - gold_start + 1

    coverage = overlap_words / gold_words_count
    return coverage >= min_coverage

def compute_recall_at_k(items, chunks_index, bm25_scores, k=3):
    """Compute recall@k using BM25-only scores."""
    recall_count = 0

    for item in items:
        item_id = item['item']
        contract = item['contract']
        gold_words = item['gold_words']

        # Get BM25 scores for this item
        scores = bm25_scores[item_id]

        # Get chunk ranges for this contract
        contract_chunks = chunks_index[contract]['chunks']

        # Get top-k chunks by BM25 score
        chunk_scores = list(enumerate(scores))
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        top_k_chunks = [idx for idx, score in chunk_scores[:k]]

        # Check if any top-k chunk covers the answer
        found = False
        for chunk_idx in top_k_chunks:
            chunk_range = contract_chunks[chunk_idx]
            if chunk_covers_answer(chunk_range, gold_words):
                found = True
                break

        if found:
            recall_count += 1

    recall = 100 * recall_count / len(items)
    return recall, recall_count

def compute_per_category_recall(items, chunks_index, bm25_scores, k=3):
    """Compute recall@k per category."""
    category_results = defaultdict(lambda: {'total': 0, 'found': 0})

    for item in items:
        item_id = item['item']
        contract = item['contract']
        category = item['category']
        gold_words = item['gold_words']

        # Get BM25 scores
        scores = bm25_scores[item_id]

        # Get chunk ranges
        contract_chunks = chunks_index[contract]['chunks']

        # Get top-k
        chunk_scores = list(enumerate(scores))
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        top_k_chunks = [idx for idx, score in chunk_scores[:k]]

        # Check coverage
        found = False
        for chunk_idx in top_k_chunks:
            chunk_range = contract_chunks[chunk_idx]
            if chunk_covers_answer(chunk_range, gold_words):
                found = True
                break

        category_results[category]['total'] += 1
        if found:
            category_results[category]['found'] += 1

    # Compute percentages
    results = {}
    for category, counts in category_results.items():
        recall = 100 * counts['found'] / counts['total']
        results[category] = {
            'recall': recall,
            'found': counts['found'],
            'total': counts['total']
        }

    return results

def main():
    print("PoC 010: BM25-Only Retrieval Recall")
    print("=" * 80)
    print()

    # Load data
    print("Loading data...")
    items = load_items()
    chunks_index = load_chunks_index()
    bm25_scores = load_bm25_scores()

    print(f"Loaded {len(items)} items from {len(chunks_index)} contracts")
    print()

    # Compute overall recall
    print("Computing recall@3 with BM25-only...")
    recall, found = compute_recall_at_k(items, chunks_index, bm25_scores, k=3)

    print(f"BM25-only recall@3: {recall:.1f}% ({found}/{len(items)} items)")
    print()

    # Compare with PoC 007 baseline
    print("Baseline comparison (from PoC 007):")
    print(f"  EmbeddingGemma hybrid (0.7 sem + 0.3 BM25): 61.4%")
    print(f"  BM25-only (this PoC):                      {recall:.1f}%")
    print(f"  Difference:                                 {recall - 61.4:.1f} points")
    print()

    # Compute per-category recall
    print("Per-category recall@3:")
    print("-" * 80)
    category_results = compute_per_category_recall(items, chunks_index, bm25_scores, k=3)

    # Sort by category name
    for category in sorted(category_results.keys()):
        result = category_results[category]
        print(f"{category:40} {result['recall']:5.1f}%  ({result['found']:3}/{result['total']:3})")

    print()

    # Decision rule check
    print("=" * 80)
    print("DECISION RULE CHECK (PoC 010 registration)")
    print("=" * 80)
    print()

    print("Step 1 (Viability): H1 - BM25 recall within 5 points of hybrid?")
    diff = recall - 61.4
    if diff >= -5:
        print(f"  ✓ H1 HOLDS: {recall:.1f}% is within 5 points of 61.4% (diff: {diff:+.1f})")
        print("  → Proceed to Step 2")
    else:
        print(f"  ✗ H1 FAILS: {recall:.1f}% is MORE than 5 points below 61.4% (diff: {diff:+.1f})")
        print("  → REJECT: Semantic component is necessary")
        print("  → Stop here (do not proceed to Step 2)")
        return

    print()
    print("Step 2 (Keyword categories): H2 - BM25 matches hybrid for ≥3/6 categories?")
    keyword_categories = [
        'Agreement Date',
        'Expiration Date',
        'Governing Law',
        'Notice Period To Terminate Renewal',
        'Renewal Term',
        'Warranty Duration'
    ]

    # PoC 007 baseline recall per category (from README)
    poc007_baseline = {
        'Agreement Date': 72.0,
        'Expiration Date': 54.0,
        'Governing Law': 73.0,
        'Notice Period To Terminate Renewal': 31.0,
        'Renewal Term': 57.0,
        'Warranty Duration': 45.1
    }

    matches = 0
    for cat in keyword_categories:
        if cat not in category_results:
            continue
        bm25_recall = category_results[cat]['recall']
        hybrid_recall = poc007_baseline.get(cat, 0)
        diff = bm25_recall - hybrid_recall

        within_2 = abs(diff) <= 2 or bm25_recall > hybrid_recall
        if within_2:
            matches += 1
            status = "✓"
        else:
            status = "✗"

        print(f"  {status} {cat:40} BM25: {bm25_recall:5.1f}%  Hybrid: {hybrid_recall:5.1f}%  (diff: {diff:+5.1f})")

    print()
    if matches >= 3:
        print(f"  ✓ H2 HOLDS: {matches}/6 categories match or exceed hybrid")
        print("  → ADOPT (conditional): BM25-only viable for keyword-heavy categories")
    else:
        print(f"  ✗ H2 FAILS: Only {matches}/6 categories match hybrid")
        print("  → INCONCLUSIVE: BM25 works for some but not others")

    print()
    print("=" * 80)
    print("Note: Step 3 (key-fact accuracy with Qwen) requires running full Q&A.")
    print("      That would take ~40 minutes. For this quick test, we stop here.")
    print("=" * 80)

if __name__ == '__main__':
    main()
