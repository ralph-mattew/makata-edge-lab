#!/bin/bash
# Automated Research-to-PoC Pipeline Orchestrator
# Run this weekly to discover and validate new PoC ideas

set -e

# Configuration
AUTOMATION_DIR="$(cd "$(dirname "$0")" && pwd)"
SCAN_DATE="$(date +%Y-%m-%d)"
SCAN_DIR="$AUTOMATION_DIR/scans/$SCAN_DATE"

mkdir -p "$SCAN_DIR"

echo "==============================================="
echo "Weekly Research Scan: $SCAN_DATE"
echo "==============================================="
echo ""

# Stage 1: Research Discovery (5-10 min)
echo "=== Stage 1: Research Discovery ==="
python3 "$AUTOMATION_DIR/1-discover-research.py" \
  --output "$SCAN_DIR/research-candidates.jsonl"
echo ""

# Check if we found any candidates
CANDIDATES=$(wc -l < "$SCAN_DIR/research-candidates.jsonl" | tr -d ' ')
if [ "$CANDIDATES" -eq 0 ]; then
  echo "No new research found. Exiting."
  exit 0
fi

# Stage 2: Relevance Filtering (10-15 min)
echo "=== Stage 2: Relevance Filtering ==="
python3 "$AUTOMATION_DIR/2-filter-relevance.py" \
  --input "$SCAN_DIR/research-candidates.jsonl" \
  --output "$SCAN_DIR/relevant-research.jsonl"
echo ""

# Check if we have relevant papers
RELEVANT=$(wc -l < "$SCAN_DIR/relevant-research.jsonl" | tr -d ' ')
if [ "$RELEVANT" -eq 0 ]; then
  echo "No relevant research found. Exiting."
  exit 0
fi

# Stage 3: Idea Extraction (20-30 min)
echo "=== Stage 3: Idea Extraction ==="
python3 "$AUTOMATION_DIR/3-extract-ideas.py" \
  --input "$SCAN_DIR/relevant-research.jsonl" \
  --output "$SCAN_DIR/extracted-ideas.jsonl"
echo ""

# Check if we extracted ideas
IDEAS=$(wc -l < "$SCAN_DIR/extracted-ideas.jsonl" | tr -d ' ')
if [ "$IDEAS" -eq 0 ]; then
  echo "No ideas extracted. Exiting."
  exit 0
fi

# Stage 4: Quality Gate Validation (15-20 min)
echo "=== Stage 4: Quality Gate Validation ==="
python3 "$AUTOMATION_DIR/4-validate-quality-gate.py" \
  --input "$SCAN_DIR/extracted-ideas.jsonl" \
  --output "$SCAN_DIR/validated-ideas.jsonl"
echo ""

# Check if any ideas passed quality gates
VALIDATED=$(wc -l < "$SCAN_DIR/validated-ideas.jsonl" | tr -d ' ')
if [ "$VALIDATED" -eq 0 ]; then
  echo "No ideas passed quality gates. Exiting."
  exit 0
fi

# Stage 5: Prioritization (5 min)
echo "=== Stage 5: Prioritization ==="
python3 "$AUTOMATION_DIR/5-prioritize-ideas.py" \
  --input "$SCAN_DIR/validated-ideas.jsonl" \
  --output "$SCAN_DIR/prioritized-ideas.jsonl"
echo ""

# Stage 6: Idea Bank Update (5 min)
echo "=== Stage 6: Idea Bank Update ==="
python3 "$AUTOMATION_DIR/6-update-idea-bank.py" \
  --input "$SCAN_DIR/prioritized-ideas.jsonl" \
  --idea-bank "$AUTOMATION_DIR/../POC-IDEAS.md" \
  --summary "$SCAN_DIR/weekly-summary.md"
echo ""

# Final summary
echo "==============================================="
echo "Weekly Scan Complete!"
echo "==============================================="
echo ""
echo "Results saved to: $SCAN_DIR/"
echo "Summary: $SCAN_DIR/weekly-summary.md"
echo ""
echo "Next steps:"
echo "1. Review weekly-summary.md (10 minutes)"
echo "2. Select highest priority idea to execute"
echo "3. Create PoC registration"
echo ""
