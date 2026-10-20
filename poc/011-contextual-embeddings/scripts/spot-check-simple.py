#!/usr/bin/env python3
"""Simplified spot-check: Compare standard vs contextual chunk retrieval.

This script:
1. Samples N random items from CUAD
2. For each item, embeds the question
3. Computes cosine similarity with both standard and contextual chunks
4. Retrieves top-3 chunks from each method
5. Formats side-by-side comparison for manual review

This is a simplified approach that uses sentence-transformers for both
standard and contextual embeddings, allowing direct comparison.

Usage:
    python3 spot-check-simple.py [--sample-size N]
"""

import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: sentence-transformers not installed")
    print("  pip3 install sentence-transformers")
    sys.exit(1)

# Paths
HERE = Path(__file__).resolve().parent
POC011 = HERE.parent
POC007 = POC011.parent / '007-embedding-retrieval-recall'
DATA_DIR = POC011 / 'data'
POC007_RAW = POC007 / 'results' / 'raw'

# Parameters
SAMPLE_SIZE = 50
SEED = 11
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def main():
    sample_size = SAMPLE_SIZE
    if '--sample-size' in sys.argv:
        idx = sys.argv.index('--sample-size')
        sample_size = int(sys.argv[idx + 1])

    print(f"PoC 011 Option A: Spot-check on {sample_size} items")
    print(f"Model: {MODEL_NAME}")
    print()

    # Check prerequisites
    if not (DATA_DIR / 'chunks-contextual-doc.jsonl').exists():
        print("ERROR: Run prep-contexts.py first")
        sys.exit(1)

    # Load model
    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"✓ Loaded {MODEL_NAME}")
    print()

    # Load data
    print("Loading items and chunks...")
    with open(POC007_RAW / 'items.jsonl', encoding='utf-8') as f:
        items = [json.loads(line) for line in f]

    # Load standard chunk texts
    standard_chunks = {}
    with open(POC007_RAW / 'chunks.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            contract = data['contract']
            for i, chunk in enumerate(data['chunks']):
                text = (chunk.get('overlap', '') + ' ' + chunk['own']).strip()
                key = f"{contract}_{i}"
                standard_chunks[key] = {
                    'text': text,
                    'contract': contract,
                    'chunk_id': i
                }

    # Load contextual chunks
    doc_only_chunks = {}
    with open(DATA_DIR / 'chunks-contextual-doc.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            # chunk_id already contains the full key (contract_chunknum)
            key = data['chunk_id']
            doc_only_chunks[key] = data['text']

    full_chunks = {}
    with open(DATA_DIR / 'chunks-contextual-full.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            # chunk_id already contains the full key (contract_chunknum)
            key = data['chunk_id']
            full_chunks[key] = data['text']

    print(f"✓ Loaded {len(items)} items")
    print(f"✓ Loaded {len(standard_chunks)} standard chunks")
    print(f"✓ Loaded {len(doc_only_chunks)} doc-only contextual chunks")
    print(f"✓ Loaded {len(full_chunks)} full contextual chunks")
    print()

    # Sample items
    rng = random.Random(SEED)
    sampled = rng.sample(items, sample_size)
    print(f"Sampled {len(sampled)} items (seed {SEED})")
    print()

    # Process each item
    output_file = POC011 / 'spot-check-results.txt'
    improvements = {'standard': 0, 'doc_only': 0, 'full': 0, 'unclear': 0}

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("PoC 011: Contextual Embeddings - Spot-Check Results\n")
        f.write("=" * 80 + "\n")
        f.write(f"Sample: {sample_size} items (seed {SEED})\n")
        f.write(f"Model: {MODEL_NAME}\n")
        f.write(f"Method: Cosine similarity (semantic only, no BM25 hybrid)\n")
        f.write("\n")

        for idx, item in enumerate(sampled, 1):
            print(f"Processing item {idx}/{len(sampled)}: {item['item']} ({item['category']})")

            # Embed question
            question_emb = model.encode(item['question'], normalize_embeddings=True)

            # Get chunks for this contract only
            contract = item['contract']
            contract_chunk_keys = [k for k in standard_chunks.keys()
                                  if k.startswith(contract + '_')]

            # Embed standard chunks for this contract
            standard_texts = [standard_chunks[k]['text'] for k in contract_chunk_keys]
            standard_embs = model.encode(standard_texts, normalize_embeddings=True,
                                        show_progress_bar=False)

            # Compute similarities
            standard_sims = [(contract_chunk_keys[i], cosine_similarity(question_emb, emb))
                           for i, emb in enumerate(standard_embs)]
            standard_top3 = sorted(standard_sims, key=lambda x: x[1], reverse=True)[:3]

            # Embed doc-only contextual chunks
            doc_only_texts = [doc_only_chunks[k] for k in contract_chunk_keys]
            doc_only_embs = model.encode(doc_only_texts, normalize_embeddings=True,
                                        show_progress_bar=False)
            doc_only_sims = [(contract_chunk_keys[i], cosine_similarity(question_emb, emb))
                           for i, emb in enumerate(doc_only_embs)]
            doc_only_top3 = sorted(doc_only_sims, key=lambda x: x[1], reverse=True)[:3]

            # Embed full contextual chunks
            full_texts = [full_chunks[k] for k in contract_chunk_keys]
            full_embs = model.encode(full_texts, normalize_embeddings=True,
                                    show_progress_bar=False)
            full_sims = [(contract_chunk_keys[i], cosine_similarity(question_emb, emb))
                        for i, emb in enumerate(full_embs)]
            full_top3 = sorted(full_sims, key=lambda x: x[1], reverse=True)[:3]

            # Format comparison
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"ITEM {item['item']} ({idx}/{len(sampled)}): {item['category']}\n")
            f.write("=" * 80 + "\n")
            f.write(f"Question: {item['question']}\n")
            f.write(f"Contract: {contract}\n")
            f.write(f"Gold words: {item['gold_words']}\n")
            f.write("\n")

            f.write("-" * 80 + "\n")
            f.write("STANDARD CHUNKS (baseline):\n")
            f.write("-" * 80 + "\n")
            for rank, (key, sim) in enumerate(standard_top3, 1):
                text = standard_chunks[key]['text']
                f.write(f"[{rank}] Similarity: {sim:.4f}\n")
                f.write(f"    {text[:150]}{'...' if len(text) > 150 else ''}\n\n")

            f.write("-" * 80 + "\n")
            f.write("DOC-ONLY CONTEXTUAL:\n")
            f.write("-" * 80 + "\n")
            for rank, (key, sim) in enumerate(doc_only_top3, 1):
                text = doc_only_chunks[key]
                f.write(f"[{rank}] Similarity: {sim:.4f}\n")
                f.write(f"    {text[:150]}{'...' if len(text) > 150 else ''}\n\n")

            f.write("-" * 80 + "\n")
            f.write("FULL CONTEXTUAL (doc+section):\n")
            f.write("-" * 80 + "\n")
            for rank, (key, sim) in enumerate(full_top3, 1):
                text = full_chunks[key]
                f.write(f"[{rank}] Similarity: {sim:.4f}\n")
                f.write(f"    {text[:150]}{'...' if len(text) > 150 else ''}\n\n")

            f.write("ASSESSMENT: Which method retrieved better chunks?\n")
            f.write("[ ] Standard  [ ] Doc-only  [ ] Full  [ ] Unclear\n")
            f.write("\n")

    print()
    print(f"✓ Spot-check results written to: {output_file}")
    print()
    print("Next steps:")
    print("  1. Review the output file manually")
    print("  2. For each item, assess which method retrieved more relevant chunks")
    print("  3. Count improvements: if >60% show improvement, proceed to full integration")
    print()


if __name__ == '__main__':
    main()
