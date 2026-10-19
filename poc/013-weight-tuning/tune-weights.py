#!/usr/bin/env python3
"""
PoC 013: Hybrid Retrieval Weight Tuning
Tests different semantic/BM25 weight combinations to find optimal balance.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

# Path to PoC 007 results
POC_007_DIR = Path(__file__).parent.parent / "007-embedding-retrieval-recall" / "results" / "raw"

def load_scores(scores_file):
    """Load scores from JSONL file: {item_id: [scores]} """
    scores_dict = {}
    with open(scores_file) as f:
        for line in f:
            data = json.loads(line)
            scores_dict[data['item']] = data['scores']
    return scores_dict

def load_items(items_file):
    """Load gold answers with metadata"""
    items = []
    with open(items_file) as f:
        for line in f:
            items.append(json.loads(line))
    return items

def load_chunks_index(chunks_file):
    """Load chunk index: [chunk_data]"""
    chunks = []
    with open(chunks_file) as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks

def chunk_covers_answer(chunk_range, gold_words, min_coverage=0.5):
    """Check if chunk covers ≥50% of gold answer span"""
    chunk_start, chunk_end, page = chunk_range
    gold_start, gold_end = gold_words

    # Check page match
    if page != -1 and gold_start != -1:  # -1 means no page info
        # Simplified: assume same page for now
        pass

    # Calculate word overlap
    overlap_start = max(chunk_start, gold_start)
    overlap_end = min(chunk_end, gold_end)

    if overlap_start > overlap_end:
        return False

    overlap_words = overlap_end - overlap_start + 1
    gold_words_count = gold_end - gold_start + 1

    coverage = overlap_words / gold_words_count if gold_words_count > 0 else 0
    return coverage >= min_coverage

def compute_recall_at_k(items, chunks_index, semantic_scores, bm25_scores, semantic_weight, k=3):
    """Compute recall@k with hybrid scoring"""
    bm25_weight = 1.0 - semantic_weight
    recall_count = 0

    for item in items:
        item_id = item['item']

        # Get scores for this item
        sem_scores = semantic_scores.get(item_id, [])
        bm25_scores_item = bm25_scores.get(item_id, [])

        if not sem_scores or not bm25_scores_item:
            continue

        # Compute hybrid scores
        hybrid_scores = [
            semantic_weight * sem + bm25_weight * bm25
            for sem, bm25 in zip(sem_scores, bm25_scores_item)
        ]

        # Get top-k chunks
        chunk_scores = list(enumerate(hybrid_scores))
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        top_k_chunks = [idx for idx, score in chunk_scores[:k]]

        # Check if any top-k chunk covers the answer
        chunks = chunks_index[item['contract']]
        found = any(
            chunk_covers_answer(chunks[idx], item['gold_words'])
            for idx in top_k_chunks if idx < len(chunks)
        )

        if found:
            recall_count += 1

    return 100.0 * recall_count / len(items), recall_count

def compute_recall_by_category(items, chunks_index, semantic_scores, bm25_scores, semantic_weight, k=3):
    """Compute recall@k per category"""
    bm25_weight = 1.0 - semantic_weight
    category_counts = defaultdict(int)
    category_correct = defaultdict(int)

    for item in items:
        item_id = item['item']
        category = item['category']

        category_counts[category] += 1

        # Get scores
        sem_scores = semantic_scores.get(item_id, [])
        bm25_scores_item = bm25_scores.get(item_id, [])

        if not sem_scores or not bm25_scores_item:
            continue

        # Hybrid scores
        hybrid_scores = [
            semantic_weight * sem + bm25_weight * bm25
            for sem, bm25 in zip(sem_scores, bm25_scores_item)
        ]

        # Top-k
        chunk_scores = list(enumerate(hybrid_scores))
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        top_k_chunks = [idx for idx, score in chunk_scores[:k]]

        # Check coverage
        chunks = chunks_index[item['contract']]
        found = any(
            chunk_covers_answer(chunks[idx], item['gold_words'])
            for idx in top_k_chunks if idx < len(chunks)
        )

        if found:
            category_correct[category] += 1

    # Compute recall per category
    category_recall = {}
    for category in category_counts:
        recall = 100.0 * category_correct[category] / category_counts[category]
        category_recall[category] = {
            "recall": round(recall, 1),
            "correct": category_correct[category],
            "total": category_counts[category]
        }

    return category_recall

def main():
    print("=== PoC 013: Hybrid Retrieval Weight Tuning ===")
    print()

    # Load data
    print("Loading PoC 007 data...")
    semantic_scores = load_scores(POC_007_DIR / "scores-eg.jsonl")
    bm25_scores = load_scores(POC_007_DIR / "scores-bm25.jsonl")
    items = load_items(POC_007_DIR / "items.jsonl")

    # Load chunks index (organized by contract)
    print("Loading chunks index...")
    chunks_by_contract = {}
    with open(POC_007_DIR / "chunks-index.jsonl") as f:
        for line in f:
            data = json.loads(line)
            contract = data['contract']
            chunks_by_contract[contract] = data['chunks']  # chunks is already an array of [start, end, page]

    print(f"Loaded {len(items)} items from {len(chunks_by_contract)} contracts")
    print()

    # Grid search over weights
    weights_to_test = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    results = {
        "baseline_weight": 0.7,
        "weights_tested": weights_to_test,
        "results": []
    }

    print("Testing weights (semantic weight, BM25 weight = 1 - semantic):")
    print()

    best_recall = 0.0
    best_weight = 0.7

    for semantic_weight in weights_to_test:
        bm25_weight = 1.0 - semantic_weight

        print(f"Weight: {semantic_weight:.1f} semantic + {bm25_weight:.1f} BM25...", end=" ")

        # Overall recall
        recall, correct = compute_recall_at_k(
            items, chunks_by_contract, semantic_scores, bm25_scores, semantic_weight
        )

        # Per-category recall
        category_recall = compute_recall_by_category(
            items, chunks_by_contract, semantic_scores, bm25_scores, semantic_weight
        )

        results["results"].append({
            "semantic_weight": semantic_weight,
            "bm25_weight": bm25_weight,
            "overall_recall": round(recall, 1),
            "items_correct": correct,
            "items_total": len(items),
            "category_recall": category_recall
        })

        print(f"Recall@3: {recall:.1f}% ({correct}/{len(items)})")

        if recall > best_recall:
            best_recall = recall
            best_weight = semantic_weight

    print()
    print("=== Results Summary ===")
    print(f"Baseline (0.7 semantic): {[r for r in results['results'] if r['semantic_weight'] == 0.7][0]['overall_recall']}%")
    print(f"Best weight: {best_weight:.1f} semantic ({1.0-best_weight:.1f} BM25)")
    print(f"Best recall: {best_recall:.1f}%")
    print(f"Improvement: {best_recall - results['results'][6]['overall_recall']:.1f} points")
    print()

    # Save results
    output_dir = Path(__file__).parent / "results" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "weight-tuning-results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {output_file}")

    # Decision
    baseline_recall = results['results'][6]['overall_recall']  # 0.7 is index 6
    improvement = best_recall - baseline_recall

    print()
    print("=== Decision ===")
    if abs(best_weight - 0.7) < 0.1:
        print("REJECT: Optimal weight is essentially 0.7 (current baseline)")
        print(f"Reason: Best weight {best_weight:.1f} differs from 0.7 by <0.1")
    elif improvement >= 1.0:
        print(f"ADOPT: Use {best_weight:.1f} semantic weight (improves recall by {improvement:.1f} points)")
        print(f"Reason: Improvement ≥1.0 point threshold")
    else:
        print(f"INCONCLUSIVE: Best weight {best_weight:.1f} improves recall by only {improvement:.1f} points")
        print(f"Reason: Improvement <1.0 point threshold (not worth changing)")

if __name__ == "__main__":
    main()
