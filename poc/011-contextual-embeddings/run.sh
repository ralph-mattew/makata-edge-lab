#!/usr/bin/env bash
# PoC 011: Contextual Embeddings - Full execution script
# This script runs the complete PoC from start to finish.
set -euo pipefail
cd "$(dirname "$0")"

echo "=========================================="
echo "PoC 011: Contextual Embeddings"
echo "=========================================="
echo ""
echo "This PoC tests Anthropic-style contextual embeddings:"
echo "  - Doc-only: 'Document: {title}. Chunk: {text}'"
echo "  - Full: 'Document: {title}. Section: {header}. Chunk: {text}'"
echo ""
echo "Expected runtime: 60-90 minutes"
echo "Expected outcome: +3-5 points recall improvement"
echo ""

# Check prerequisites
POC007=../007-embedding-retrieval-recall
POC009=../009-retrieval-depth-qwen

if [[ ! -d $POC007 ]]; then
  echo "Error: PoC 007 not found at $POC007"
  echo "PoC 011 depends on PoC 007's chunk index and embedding infrastructure."
  exit 1
fi

if [[ ! -f $POC007/results/raw/chunks-index.jsonl ]]; then
  echo "Error: PoC 007 has not been run yet (chunks-index.jsonl missing)"
  echo "Please run PoC 007 first: cd $POC007 && ./run.sh"
  exit 1
fi

echo "✓ Prerequisites check passed"
echo ""

# Setup
POC007_RAW=$POC007/results/raw
OUT_DIR=results
DATA_DIR=data
mkdir -p $OUT_DIR $DATA_DIR

echo "=========================================="
echo "Phase 1: Prepare Contextual Chunks"
echo "=========================================="
echo ""
echo "Extracting section headers and building contextual chunk texts..."
echo "This creates two variants:"
echo "  1. Doc-only (simple, fast)"
echo "  2. Doc+Section (full, Anthropic-style)"
echo ""

python3 scripts/prep-contexts.py $POC007_RAW $DATA_DIR

if [[ ! -f $DATA_DIR/chunks-contextual-doc.jsonl ]] || [[ ! -f $DATA_DIR/chunks-contextual-full.jsonl ]]; then
  echo "Error: Context preparation failed"
  exit 1
fi

echo ""
echo "✓ Phase 1 complete: Contextual chunks prepared"
echo ""

echo "=========================================="
echo "Phase 2: Embedding with Context"
echo "=========================================="
echo ""
echo "Re-embedding all chunks with contextual prefixes..."
echo "This uses PoC 007's EmbeddingGemma model."
echo "Expected time: 15-25 minutes"
echo ""

# Note: Since PoC 007's harness expects specific input format,
# we need to adapt. For this initial implementation, we'll use
# a Python-based embedding approach that can work standalone.

echo "Installing required Python packages (if needed)..."
pip3 install --quiet numpy sentence-transformers 2>/dev/null || true

echo "Running embeddings (this may take 15-25 minutes)..."
python3 scripts/embed-contextual.py $DATA_DIR $POC007 $OUT_DIR

if [[ ! -f $OUT_DIR/embeddings-doc-only.npy ]] || [[ ! -f $OUT_DIR/embeddings-full.npy ]]; then
  echo "Error: Embedding failed"
  exit 1
fi

echo ""
echo "✓ Phase 2 complete: Embeddings generated"
echo ""

echo "=========================================="
echo "Phase 3: Retrieval with Contextual Embeddings"
echo "=========================================="
echo ""
echo "Running hybrid retrieval with contextual embeddings..."
echo "Comparing: standard vs doc-only vs full"
echo "Expected time: 5-10 minutes"
echo ""

python3 scripts/retrieve.py $POC007_RAW $OUT_DIR

if [[ ! -f $OUT_DIR/recall-doc-only.jsonl ]] || [[ ! -f $OUT_DIR/recall-full.jsonl ]]; then
  echo "Error: Retrieval failed"
  exit 1
fi

echo ""
echo "✓ Phase 3 complete: Retrieval results generated"
echo ""

echo "=========================================="
echo "Phase 4: Analysis & Verdict"
echo "=========================================="
echo ""
echo "Comparing contextual vs standard embeddings..."
echo "Applying decision rule from registration..."
echo ""

python3 scripts/compare.py $POC007_RAW $OUT_DIR

echo ""
echo "=========================================="
echo "PoC 011 Complete!"
echo "=========================================="
echo ""
echo "Results are in: $OUT_DIR/"
echo ""
echo "Key files:"
echo "  - comparison.txt: Recall improvements, statistical tests, verdict"
echo "  - timings.txt: Embedding time comparisons"
echo "  - per-chunk-size.txt: Analysis by chunk size (H2 validation)"
echo ""
echo "Next steps:"
echo "  1. Review results/comparison.txt for the verdict"
echo "  2. If ADOPT: Run Qwen Q&A to measure end-to-end key-fact accuracy (H4)"
echo "  3. Write up results in README.md"
echo ""
