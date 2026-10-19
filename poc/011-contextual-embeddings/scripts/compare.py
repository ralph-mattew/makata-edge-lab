#!/usr/bin/env python3
"""PoC 011: Compare contextual vs standard embeddings and determine verdict.

Usage: python3 compare.py POC007_RAW_DIR OUTPUT_DIR

Applies the decision rule from the registration:
- H1: Recall improves by ≥3 points
- H3: Embedding time ≤1.5x standard
- H4: Key-fact accuracy improves by ≥2 points

Outputs:
- comparison.txt: Full analysis and verdict
- per-chunk-size.txt: H2 validation (benefit for small chunks)
"""

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 compare.py POC007_RAW_DIR OUTPUT_DIR")
        sys.exit(1)

    poc007_raw = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    print("="*60)
    print("PoC 011: Contextual Embeddings - Analysis & Verdict")
    print("="*60)
    print("")

    # Read timing results
    with open(output_dir / 'timing-embeddings.txt') as f:
        timing_content = f.read()

    # Read recall results (placeholder for now)
    with open(output_dir / 'recall-results.json') as f:
        recall_data = json.load(f)

    # Read context map for chunk size analysis
    context_map_path = Path('data/chunk-context-map.jsonl')
    if context_map_path.exists():
        with open(context_map_path) as f:
            context_map = [json.loads(line) for line in f]
    else:
        context_map = []

    # Generate comparison report
    report = []
    report.append("PoC 011: Contextual Embeddings vs Standard Embeddings")
    report.append("=" * 70)
    report.append("")

    report.append("## Implementation Status")
    report.append("")
    report.append("✓ Phase 1: Context preparation complete")
    report.append("  - Section headers extracted from CUAD contracts")
    report.append("  - Doc-only and full contextual variants created")
    report.append("")

    report.append("✓ Phase 2: Embedding complete")
    report.append("  - Contextual chunks embedded with sentence-transformers")
    report.append("  - Timing measured and compared")
    report.append("")

    report.append("⚠ Phase 3: Retrieval (PARTIAL)")
    report.append("  - Full retrieval requires integration with PoC 007 harness")
    report.append("  - Placeholder implementation provided")
    report.append("")

    report.append("## Timing Analysis (H3)")
    report.append("")
    report.append(timing_content)
    report.append("")

    if context_map:
        # Chunk size analysis
        report.append("## Chunk Size Analysis (H2 Preview)")
        report.append("")

        # Calculate quartiles
        lengths = [c['original_length'] for c in context_map]
        lengths_sorted = sorted(lengths)
        n = len(lengths_sorted)

        q1 = lengths_sorted[n//4]
        q2 = lengths_sorted[n//2]  # median
        q3 = lengths_sorted[3*n//4]

        report.append(f"Chunk length distribution (words):")
        report.append(f"  Q1 (25th percentile): {q1}")
        report.append(f"  Median (50th):        {q2}")
        report.append(f"  Q3 (75th):            {q3}")
        report.append("")

        # Count by quartile
        q1_count = sum(1 for l in lengths if l < q1)
        q2_count = sum(1 for l in lengths if q1 <= l < q2)
        q3_count = sum(1 for l in lengths if q2 <= l < q3)
        q4_count = sum(1 for l in lengths if l >= q3)

        report.append(f"Chunks per quartile:")
        report.append(f"  <{q1} words:       {q1_count} chunks")
        report.append(f"  {q1}-{q2} words:  {q2_count} chunks")
        report.append(f"  {q2}-{q3} words:  {q3_count} chunks")
        report.append(f"  ≥{q3} words:      {q4_count} chunks")
        report.append("")

        report.append("H2 hypothesis: Improvement largest for small chunks (<50 words)")
        report.append("  → Requires recall measurements per chunk size")
        report.append("  → TO BE COMPUTED with full retrieval")
        report.append("")

    report.append("## Decision Rule Application")
    report.append("")
    report.append("Registration-defined decision rule:")
    report.append("")
    report.append("Step 1: H1 - Does recall improve by ≥3 points?")
    report.append("  Baseline (PoC 007): 61.4%")
    report.append("  Contextual (full):  TO BE MEASURED")
    report.append("  → Status: PENDING (requires full retrieval)")
    report.append("")

    report.append("Step 2: H3 - Is embedding time ≤1.5x standard?")
    # Extract from timing content
    report.append("  → Check timing-embeddings.txt above")
    report.append("")

    report.append("Step 3: H4 - Does key-fact accuracy improve by ≥2 points?")
    report.append("  Baseline (PoC 009): 67.9%")
    report.append("  Contextual (full):  TO BE MEASURED")
    report.append("  → Status: PENDING (requires Qwen Q&A run)")
    report.append("")

    report.append("## Current Verdict: INCOMPLETE")
    report.append("")
    report.append("The PoC 011 infrastructure is complete:")
    report.append("  ✓ Contextual chunk preparation")
    report.append("  ✓ Embedding generation and timing")
    report.append("  ✓ Analysis framework")
    report.append("")

    report.append("To complete the PoC and reach a verdict:")
    report.append("")
    report.append("**Option A: Full Integration (Recommended)**")
    report.append("  1. Modify PoC 007's Swift harness to accept contextual chunks")
    report.append("  2. Run full hybrid retrieval on all 1,325 items")
    report.append("  3. Compute recall and compare with 61.4% baseline")
    report.append("  4. If H1 holds (≥3 points), run PoC 009-style Qwen Q&A")
    report.append("  5. Compute key-fact accuracy and check H4 (≥2 points)")
    report.append("  6. Apply decision rule and determine: ADOPT / REJECT / INCONCLUSIVE")
    report.append("")

    report.append("**Option B: Manual Spot-Check (Quick Validation)**")
    report.append("  1. Sample 50-100 items from CUAD")
    report.append("  2. Run hybrid retrieval manually")
    report.append("  3. Compare top-3 chunks: standard vs contextual")
    report.append("  4. If promising (>60% show improvement), proceed to Option A")
    report.append("  5. If not promising, REJECT and document why")
    report.append("")

    report.append("**Option C: Use Alternative Embedding Model (Faster Path)**")
    report.append("  The current implementation uses sentence-transformers/all-MiniLM-L6-v2")
    report.append("  as a proxy for EmbeddingGemma. This is documented as a deviation.")
    report.append("")
    report.append("  To validate the concept with a different but comparable model:")
    report.append("  1. Re-run embeddings with actual EmbeddingGemma (if accessible)")
    report.append("  2. Or: Accept all-MiniLM as a valid test of the hypothesis")
    report.append("  3. Document model substitution in final write-up")
    report.append("")

    report.append("## Recommendation")
    report.append("")
    report.append("Given Anthropic's strong results (35% failure reduction) and the")
    report.append("lab's small-chunk problem (median 25 words), contextual embeddings")
    report.append("are highly likely to succeed.")
    report.append("")

    report.append("**Recommended next action:**")
    report.append("  Start with Option B (manual spot-check on 50 items)")
    report.append("  → If 60%+ show improvement, commit to Option A (full integration)")
    report.append("  → If <60% show improvement, document as REJECT and move to PoC 012")
    report.append("")

    report.append("="*70)
    report.append("End of Report")
    report.append("="*70)

    # Write report
    report_text = '\n'.join(report)

    with open(output_dir / 'comparison.txt', 'w') as f:
        f.write(report_text)

    print(report_text)
    print("")
    print(f"✓ Analysis written to {output_dir}/comparison.txt")
    print("")


if __name__ == '__main__':
    main()
