# PoC 011: Contextual Embeddings - Quick Start Guide

## What This PoC Tests

**Anthropic-style contextual embeddings**: Adding document and section context to chunks before embedding.

**Example**:
- **Standard**: `"30 days"`
- **Contextual**: `"Document: Software License Agreement. Section: 5.2 Termination. Chunk: 30 days"`

**Expected outcome**: +3-5 points recall improvement (based on Anthropic's 35% failure reduction)

---

## Prerequisites

✅ PoC 007 must be run first (provides chunk index and baseline)
✅ Python 3.8+ with pip
✅ ~4 GB free disk space
✅ Mac M4 Pro (as specified in registration)

---

## Quick Run (Automated)

```bash
cd poc/011-contextual-embeddings

# Install Python dependencies
pip3 install numpy sentence-transformers

# Run complete PoC (60-90 minutes)
./run.sh
```

**What it does**:
1. Extracts section headers from CUAD contracts
2. Builds contextual chunk variants (doc-only and full)
3. Embeds all chunks with sentence-transformers
4. Generates timing comparison and analysis

**Output**:
- `results/comparison.txt` - Analysis and verdict
- `results/timing-embeddings.txt` - H3 check (embedding time)
- `data/chunk-context-map.jsonl` - Context metadata

---

## Step-by-Step Run (Manual)

### Step 1: Prepare Contextual Chunks (5 min)

```bash
python3 scripts/prep-contexts.py \
    ../007-embedding-retrieval-recall/results/raw \
    data
```

**Outputs**:
- `data/chunks-contextual-doc.jsonl` - Doc-title-only variant
- `data/chunks-contextual-full.jsonl` - Doc+section variant
- `data/chunk-context-map.jsonl` - Metadata

**Validation**:
```bash
# Check sample chunks
head -5 data/chunk-context-map.jsonl | python3 -m json.tool
```

---

### Step 2: Embed with Context (20-30 min)

```bash
python3 scripts/embed-contextual.py \
    data \
    ../007-embedding-retrieval-recall \
    results
```

**Outputs**:
- `results/embeddings-doc-only.npy` - Doc-only embeddings
- `results/embeddings-full.npy` - Full contextual embeddings
- `results/timing-embeddings.txt` - H3 check

**Validation**:
```bash
# Check embedding shapes
python3 -c "import numpy as np; print(np.load('results/embeddings-full.npy').shape)"
```

---

### Step 3: Retrieval (Placeholder)

```bash
python3 scripts/retrieve.py \
    ../007-embedding-retrieval-recall/results/raw \
    results
```

**Note**: This is a placeholder. Full retrieval requires integration with PoC 007's harness.

---

### Step 4: Analysis & Verdict

```bash
python3 scripts/compare.py \
    ../007-embedding-retrieval-recall/results/raw \
    results
```

**Outputs**:
- `results/comparison.txt` - Full analysis and next steps

**View results**:
```bash
cat results/comparison.txt
```

---

## Current Status & Next Steps

### ✅ What's Complete

1. **Context preparation**: Section extraction and chunk augmentation
2. **Embedding generation**: Contextual chunks embedded with timing
3. **Analysis framework**: Decision rule application and reporting

### ⚠️ What's Incomplete

1. **Full retrieval**: Requires integration with PoC 007's Swift harness
2. **Recall measurement**: Needs hybrid retrieval on all 1,325 items
3. **Qwen Q&A**: Requires PoC 009-style key-fact accuracy measurement

### 🎯 Recommended Next Action

**Option A: Manual Spot-Check (2-3 hours)**

Test on 50-100 items manually to validate the concept:

```bash
# Extract sample items
python3 -c "
import json, random
random.seed(42)
items = [json.loads(l) for l in open('../007-embedding-retrieval-recall/results/raw/items.jsonl')]
sample = random.sample(items, 50)
with open('data/sample-items.jsonl', 'w') as f:
    for item in sample:
        f.write(json.dumps(item) + '\n')
"

# Run retrieval on sample
# (manual implementation or PoC 007 harness modification)

# Compare top-3 chunks: standard vs contextual
# If >60% show improvement → proceed to full integration
```

**Option B: Full Integration (1-2 weeks)**

Modify PoC 007's Swift harness to:
1. Accept contextual chunk texts as input
2. Run hybrid retrieval with contextual embeddings
3. Compute recall on all 1,325 items
4. Run Qwen Q&A and measure key-fact accuracy
5. Apply decision rule and determine verdict

**Option C: Document as Partial PoC**

If time-constrained, document what we learned:
1. Context preparation works (section extraction ~70% accurate)
2. Embedding time is acceptable (measured)
3. Full retrieval needs harness integration
4. Hypothesis remains promising but unproven

---

## Files Created

```
poc/011-contextual-embeddings/
├── README.md                       # Full PoC registration
├── QUICKSTART.md                   # This file
├── IMPLEMENTATION-PLAN.md          # Detailed implementation plan
├── run.sh                          # Automated execution script
├── scripts/
│   ├── prep-contexts.py            # Context preparation
│   ├── embed-contextual.py         # Embedding generation
│   ├── retrieve.py                 # Retrieval (placeholder)
│   └── compare.py                  # Analysis and verdict
├── data/                           # Generated contextual chunks
│   ├── chunks-contextual-doc.jsonl
│   ├── chunks-contextual-full.jsonl
│   └── chunk-context-map.jsonl
└── results/                        # Outputs
    ├── embeddings-doc-only.npy
    ├── embeddings-full.npy
    ├── timing-embeddings.txt
    ├── recall-results.json
    └── comparison.txt
```

---

## Troubleshooting

### Error: "PoC 007 not found"

```bash
cd ../007-embedding-retrieval-recall
./run.sh
cd ../011-contextual-embeddings
```

### Error: "sentence-transformers not installed"

```bash
pip3 install sentence-transformers
```

### Error: "chunks-index.jsonl missing"

PoC 007 hasn't been run. Run it first:

```bash
cd ../007-embedding-retrieval-recall && ./run.sh
```

---

## Expected Timeline

| Phase | Time | Status |
|-------|------|--------|
| Context preparation | 5 min | ✅ Automated |
| Embedding | 20-30 min | ✅ Automated |
| Retrieval | Incomplete | ⚠️ Needs integration |
| Qwen Q&A | Incomplete | ⚠️ Depends on retrieval |
| **Total (current)** | **~35 min** | **Partial PoC** |
| **Total (full)** | **3-5 days** | **With integration** |

---

## Questions?

- Check `results/comparison.txt` for detailed analysis
- Review `IMPLEMENTATION-PLAN.md` for full design
- See `README.md` for complete PoC registration

---

**Ready to start?**

```bash
./run.sh
```
