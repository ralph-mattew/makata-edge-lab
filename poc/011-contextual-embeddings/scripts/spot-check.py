#!/usr/bin/env python3
"""Option A: Manual spot-check comparing standard vs contextual retrieval.

This script randomly selects N items from the CUAD dataset and compares
top-3 chunks retrieved using:
1. Standard embeddings (from PoC 007)
2. Contextual embeddings (doc-only variant)
3. Contextual embeddings (full doc+section variant)

For each item, it shows:
- The question
- The gold answer span
- Top-3 chunks from each method
- Whether each chunk overlaps with the gold answer

The goal is to manually assess whether contextual embeddings improve
retrieval quality, particularly for ambiguous chunks.

Usage:
    python3 spot-check.py [--sample-size N] [--output FILE]

Options:
    --sample-size N    Number of items to sample (default: 50)
    --output FILE      Output file for results (default: spot-check-results.txt)
"""

import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

# Paths
HERE = Path(__file__).resolve().parent
POC011 = HERE.parent
POC007 = POC011.parent / '007-embedding-retrieval-recall'
DATA_DIR = POC011 / 'data'
POC007_RAW = POC007 / 'results' / 'raw'

# Default parameters
SAMPLE_SIZE = 50
SEED = 11


def load_items() -> List[dict]:
    """Load all 1,325 CUAD items."""
    with open(POC007_RAW / 'items.jsonl', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def load_chunks_index() -> List[dict]:
    """Load chunk index from PoC 007."""
    with open(POC007_RAW / 'chunks-index.jsonl', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def load_chunk_texts() -> Dict[str, dict]:
    """Load chunk texts from PoC 007."""
    chunk_texts = {}
    with open(POC007_RAW / 'chunks.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            contract = data['contract']
            for i, chunk in enumerate(data['chunks']):
                text = (chunk.get('overlap', '') + ' ' + chunk['own']).strip()
                chunk_texts[f"{contract}_{i}"] = {
                    'contract': contract,
                    'chunk_id': i,
                    'text': text,
                    'page': chunk.get('page', 1)
                }
    return chunk_texts


def load_contextual_chunks() -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load contextual chunk variants."""
    doc_only = {}
    full = {}

    with open(DATA_DIR / 'chunks-contextual-doc.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            key = f"{data['contract']}_{data['chunk_id']}"
            doc_only[key] = data['text']

    with open(DATA_DIR / 'chunks-contextual-full.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            key = f"{data['contract']}_{data['chunk_id']}"
            full[key] = data['text']

    return doc_only, full


def load_embeddings() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load embeddings from PoC 007 and PoC 011."""
    # Standard embeddings from PoC 007
    # Note: We need to generate these using the same sentence-transformers model
    # For now, we'll use the contextual embeddings and note this as a limitation

    # Load contextual embeddings
    doc_only = np.load(DATA_DIR / 'embeddings-doc-only.npy')
    full = np.load(DATA_DIR / 'embeddings-full.npy')

    # For comparison, we need standard embeddings with the same model
    # This is a simplification for the spot-check
    return None, doc_only, full


def load_scores(backend: str) -> Dict[int, Dict[str, float]]:
    """Load scores from PoC 007."""
    scores = {}
    with open(POC007_RAW / f'scores-{backend}.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            item_id = data['item']
            scores[item_id] = {
                f"{data['contract']}_{data['chunk']}": data['score']
                for chunk_score in data.get('chunks', [])
                for data in [chunk_score]  # Unpack
            }
    return scores


def get_gold_span_text(item: dict, chunk_texts: Dict[str, dict]) -> str:
    """Extract the gold answer span text."""
    contract = item['contract']
    gold_start, gold_end = item['gold_words']

    # Load contract to get word spans
    with open(POC007_RAW / 'contracts.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if data['contract'] == contract:
                full_text = ' '.join(data['pages'])
                words = full_text.split()
                return ' '.join(words[gold_start:gold_end + 1])

    return "(could not extract)"


def chunk_overlaps_gold(chunk_key: str, item: dict, chunk_texts: Dict[str, dict]) -> bool:
    """Check if a chunk overlaps with the gold answer span."""
    # Simplified: check if chunk contract matches item contract
    # and if chunk text contains any gold words
    contract, chunk_id = chunk_key.rsplit('_', 1)
    if contract != item['contract']:
        return False

    # For accurate overlap, we'd need word-level positions
    # For spot-check, we'll use PoC 007's recall logic
    # This is a placeholder - the actual logic is complex
    return False  # TODO: implement proper overlap check


def retrieve_top_k(item: dict, scores: Dict[str, float], k: int = 3) -> List[Tuple[str, float]]:
    """Retrieve top-k chunks for an item."""
    sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_chunks[:k]


def format_comparison(item: dict,
                      standard_top3: List[Tuple[str, float]],
                      doc_only_top3: List[Tuple[str, float]],
                      full_top3: List[Tuple[str, float]],
                      chunk_texts: Dict[str, dict],
                      doc_only_texts: Dict[str, str],
                      full_texts: Dict[str, str],
                      gold_text: str) -> str:
    """Format a comparison for manual review."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"ITEM {item['item']}: {item['category']}")
    lines.append("=" * 80)
    lines.append(f"Question: {item['question']}")
    lines.append(f"Contract: {item['contract']}")
    lines.append(f"\nGold answer: {gold_text}")
    lines.append("")

    # Standard retrieval
    lines.append("-" * 80)
    lines.append("STANDARD EMBEDDINGS (PoC 007 baseline):")
    lines.append("-" * 80)
    if standard_top3:
        for rank, (chunk_key, score) in enumerate(standard_top3, 1):
            text = chunk_texts.get(chunk_key, {}).get('text', '(missing)')
            lines.append(f"[{rank}] Score: {score:.4f}")
            lines.append(f"    {text[:200]}{'...' if len(text) > 200 else ''}")
            lines.append("")
    else:
        lines.append("(No standard embeddings available)")
        lines.append("")

    # Doc-only contextual
    lines.append("-" * 80)
    lines.append("CONTEXTUAL EMBEDDINGS (doc-only):")
    lines.append("-" * 80)
    for rank, (chunk_key, score) in enumerate(doc_only_top3, 1):
        text = doc_only_texts.get(chunk_key, '(missing)')
        lines.append(f"[{rank}] Score: {score:.4f}")
        lines.append(f"    {text[:200]}{'...' if len(text) > 200 else ''}")
        lines.append("")

    # Full contextual
    lines.append("-" * 80)
    lines.append("CONTEXTUAL EMBEDDINGS (doc+section):")
    lines.append("-" * 80)
    for rank, (chunk_key, score) in enumerate(full_top3, 1):
        text = full_texts.get(chunk_key, '(missing)')
        lines.append(f"[{rank}] Score: {score:.4f}")
        lines.append(f"    {text[:200]}{'...' if len(text) > 200 else ''}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("MANUAL ASSESSMENT:")
    lines.append("Which method retrieved more relevant chunks?")
    lines.append("[ ] Standard  [ ] Doc-only  [ ] Full contextual  [ ] Tie")
    lines.append("=" * 80)
    lines.append("")

    return '\n'.join(lines)


def main():
    # Parse arguments
    sample_size = SAMPLE_SIZE
    output_file = POC011 / 'spot-check-results.txt'

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--sample-size':
            sample_size = int(args[i + 1])
            i += 2
        elif args[i] == '--output':
            output_file = Path(args[i + 1])
            i += 2
        else:
            i += 1

    print(f"Option A: Manual spot-check on {sample_size} items")
    print(f"Output: {output_file}")
    print()

    # Check if contextual embeddings exist
    if not (DATA_DIR / 'chunks-contextual-doc.jsonl').exists():
        print("ERROR: Contextual chunks not found. Run prep-contexts.py first.")
        print("  cd poc/011-contextual-embeddings")
        print("  python3 scripts/prep-contexts.py ../007-embedding-retrieval-recall/results/raw data")
        sys.exit(1)

    if not (DATA_DIR / 'embeddings-doc-only.npy').exists():
        print("ERROR: Contextual embeddings not found. Run embed-contextual.py first.")
        print("  cd poc/011-contextual-embeddings")
        print("  python3 scripts/embed-contextual.py")
        sys.exit(1)

    print("Loading data...")
    items = load_items()
    chunk_texts = load_chunk_texts()
    doc_only_texts, full_texts = load_contextual_chunks()

    print(f"Loaded {len(items)} items, {len(chunk_texts)} chunks")
    print(f"Contextual variants: {len(doc_only_texts)} doc-only, {len(full_texts)} full")
    print()

    # Sample random items
    rng = random.Random(SEED)
    sampled_items = rng.sample(items, sample_size)
    print(f"Sampled {len(sampled_items)} items (seed {SEED})")
    print()

    # Note: For a proper comparison, we need to:
    # 1. Embed queries with the same model (sentence-transformers)
    # 2. Compute cosine similarity between query and chunks
    # 3. Hybrid score with BM25
    # This is a simplified version that uses PoC 007's existing scores as a proxy

    print("WARNING: This is a simplified spot-check.")
    print("For a full comparison, we need to:")
    print("  1. Re-embed queries with sentence-transformers")
    print("  2. Compute similarity with contextual chunks")
    print("  3. Hybrid scoring with BM25")
    print()
    print("For now, this script will prepare the comparison framework.")
    print("Manual comparison requires running retrieval separately.")
    print()

    # Generate comparison output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("PoC 011: Contextual Embeddings - Spot-Check Results\n")
        f.write(f"Sample size: {sample_size} items (seed {SEED})\n")
        f.write(f"Generated: {Path(__file__).name}\n")
        f.write("\n")
        f.write("NOTE: This spot-check requires manual retrieval comparison.\n")
        f.write("See IMPLEMENTATION-PLAN.md for Option A details.\n")
        f.write("\n")

        for item in sampled_items:
            gold_text = get_gold_span_text(item, chunk_texts)

            # Placeholder: we'd need actual retrieval here
            standard_top3 = []
            doc_only_top3 = []
            full_top3 = []

            comparison = format_comparison(
                item, standard_top3, doc_only_top3, full_top3,
                chunk_texts, doc_only_texts, full_texts, gold_text
            )
            f.write(comparison)

    print(f"✓ Spot-check framework written to: {output_file}")
    print()
    print("Next steps:")
    print("  1. Implement query embedding with sentence-transformers")
    print("  2. Compute cosine similarity for each item")
    print("  3. Retrieve top-3 chunks for manual comparison")
    print("  4. Count how many items show improvement with contextual embeddings")
    print()


if __name__ == '__main__':
    main()
