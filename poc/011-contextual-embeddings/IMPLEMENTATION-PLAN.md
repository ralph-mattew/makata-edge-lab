# PoC 011 Implementation Plan

## Overview
Test Anthropic-style contextual embeddings: prepending document/section context to chunks before embedding.

**Expected runtime**: 60-90 minutes
**Expected outcome**: +3-5 points recall improvement (Anthropic reported 35% failure reduction)

---

## Prerequisites Check

✅ CUAD data exists: `../006-doc-qa-fm-gemma-qwen/data/CUAD_v1.zip`
✅ PoC 007 chunk index and scores available
✅ PoC 006 harness (`GGUFQA`) available
✅ EmbeddingGemma model from PoC 007
✅ Qwen2.5-1.5B Q4_K_M from PoC 009

---

## Implementation Steps

### Phase 1: Section Extraction (30-45 min)

**Goal**: Extract section headers from CUAD contracts to build contextual chunk metadata.

**Script**: `extract-sections.sh`

**Process**:
1. Extract CUAD_v1.zip (397 contracts)
2. For each contract, identify section headers:
   - Pattern 1: Lines starting with digits + period (e.g., "5. ", "12.3 ")
   - Pattern 2: All-caps lines ≥4 chars (e.g., "TERMINATION")
3. Map each chunk (from PoC 007's index) to its nearest section header
4. Output: `chunk-context-map.jsonl` with fields:
   - `chunk_id`: from PoC 007
   - `contract`: file name
   - `doc_title`: cleaned contract name
   - `section_header`: extracted header or "Document body"
   - `context_text`: full contextual prefix

**Validation**:
- Sample 20 chunks manually, verify >70% have correct section headers
- If <70%, fall back to doc-title-only variant

---

### Phase 2: Contextual Embedding (20-30 min)

**Goal**: Re-embed all chunks with contextual prefixes.

**Script**: `embed-contextual.sh`

**Process**:
1. Load PoC 007's chunk index (chunk_id → chunk_text)
2. Load `chunk-context-map.jsonl`
3. For each chunk, create contextual text:
   ```
   "Document: {doc_title}. Section: {section_header}. Chunk: {chunk_text}"
   ```
4. Embed using EmbeddingGemma (same model as PoC 007)
5. Output: `chunk_embeddings_contextual.npy` (same format as PoC 007)

**Variants to test**:
- `contextual-full`: doc + section + chunk
- `contextual-doc`: doc + chunk only (no section)
- `standard`: baseline from PoC 007 (for comparison)

**Timing**:
- Measure embedding time per chunk
- Expected: 1.2-1.5× slower than standard (H3: ≤50% increase)

---

### Phase 3: Retrieval with Contextual Embeddings (10 min)

**Goal**: Run retrieval with contextual embeddings, measure recall.

**Script**: `retrieve-contextual.py`

**Process**:
1. Load PoC 007's questions (1,325 answerable items)
2. Load contextual chunk embeddings
3. Run hybrid retrieval:
   - Semantic: cosine similarity with contextual embeddings (0.7 weight)
   - Keyword: BM25 on original chunk text (0.3 weight)
4. Select top-3 chunks per question
5. Compute recall: % of items where top-3 cover ≥50% of CUAD answer span

**Output**:
- `contextual-full-recall.jsonl`: per-item recall scores
- `contextual-doc-recall.jsonl`: doc-only variant
- `standard-recall.jsonl`: baseline (reuse PoC 007 if available)

---

### Phase 4: Qwen Q&A with Contextual Chunks (20-25 min)

**Goal**: Measure end-to-end key-fact accuracy with contextually-retrieved chunks.

**Script**: `run-qwen.sh`

**Process**:
1. For each question, use contextual retrieval's top-3 chunks
2. Build PoC 006-style Qwen prompt (ChatML, 3 chunks, 2048 context)
3. Run Qwen2.5-1.5B Q4_K_M (same settings as PoC 009: seed 1, temp 0.7, etc.)
4. Score outputs for key-fact correctness (PoC 006's scorer)

**Output**:
- `contextual-full-answers.jsonl`: Qwen outputs, key-fact scores
- Timing: prefill time, total time per query

---

### Phase 5: Analysis & Comparison (5-10 min)

**Goal**: Compare contextual vs standard embeddings, determine verdict.

**Script**: `compare.py`

**Metrics**:
1. **Recall** (primary): contextual vs standard (H1: ≥+3 points)
2. **Key-fact accuracy**: contextual vs standard (H4: ≥+2 points)
3. **Embedding time**: contextual / standard ratio (H3: ≤1.5×)
4. **Per-chunk-size breakdown**: recall for chunks <25, 25-50, >50 words (H2)

**Statistical tests**:
- 95% confidence intervals (contract-level bootstrap, 10K resamples)
- Per-category breakdown (6 key-fact categories)

**Decision rule application**:
- Step 1: Does H1 hold? (recall +≥3 points)
- Step 2: Does H3 hold? (embedding time ≤1.5×)
- Step 3: Does H4 hold? (key-fact +≥2 points)
- Verdict: adopt / inconclusive / reject

**Output**:
- `comparison.txt`: recall differences, CIs, verdict
- `timings.txt`: embedding time ratios
- `per-chunk-size.txt`: H2 validation

---

## Simplified Execution Plan

Since this is the first run and we want results quickly, let's do a **two-phase simplified version**:

### Simplified Phase 1: Doc-Title-Only Variant (FASTEST, 45 min total)

Skip section extraction complexity. Test the simpler variant first:

**Context format**: `"Document: {doc_title}. Chunk: {chunk_text}"`

**Why**:
- No section header extraction needed (avoids parsing errors)
- Still tests Anthropic's core hypothesis (context helps)
- Faster to implement and validate
- If this works, full variant is easy to add

**Steps**:
1. `prep-doc-only.py`: Build contextual text with doc title only (5 min)
2. `embed-doc-only.sh`: Embed with EmbeddingGemma (15-20 min)
3. `retrieve-doc-only.py`: Run retrieval, measure recall (5 min)
4. `compare-baseline.py`: Compare vs PoC 007 baseline (5 min)

**Decision point**:
- If doc-only improves recall by ≥2 points: proceed to full variant (doc+section)
- If doc-only improves by <2 points: likely reject, context adds little value

### Simplified Phase 2: Full Variant (if Phase 1 succeeds)

Add section extraction and test `doc + section + chunk` format.

---

## File Structure

```
poc/011-contextual-embeddings/
├── README.md                          # Full PoC registration (from draft)
├── IMPLEMENTATION-PLAN.md             # This file
├── data/
│   └── cuad-contracts/                # Extracted from CUAD_v1.zip
├── scripts/
│   ├── prep-doc-only.py               # Phase 1: doc-title context
│   ├── embed-doc-only.sh              # Embedding with doc context
│   ├── extract-sections.py            # Phase 2: section header extraction
│   ├── embed-full.sh                  # Embedding with doc+section
│   ├── retrieve.py                    # Retrieval with contextual embeddings
│   ├── run-qwen.sh                    # Qwen Q&A
│   └── compare.py                     # Analysis & verdict
├── results/
│   ├── doc-only-recall.jsonl
│   ├── contextual-full-recall.jsonl
│   ├── contextual-full-answers.jsonl
│   ├── comparison.txt
│   └── timings.txt
└── chunk-context-map.jsonl            # Chunk → context mapping

```

---

## Next Immediate Steps

1. ✅ Create PoC 011 folder
2. ✅ Copy draft README
3. ✅ Write implementation plan (this file)
4. ⏳ **START HERE**: Write `prep-doc-only.py` (doc-title-only variant)
5. Test on 10 chunks manually
6. Run full embedding
7. Compare with PoC 007 baseline
8. Determine verdict

---

## Expected Outcomes & Timing

### Optimistic (60 min total):
- Doc-only improves recall +3 points → proceed to full variant
- Full variant improves +5 points → ADOPT
- Total time: 45 min doc-only + 15 min full = 60 min

### Realistic (90 min total):
- Doc-only improves +2 points → proceed to full variant
- Full variant improves +3-4 points → ADOPT
- Total time: 50 min doc-only + 40 min full = 90 min

### Pessimistic (45 min total):
- Doc-only improves +1 point or less → REJECT, stop here
- Total time: 45 min (don't run full variant)

---

**Ready to start?** Let's begin with `prep-doc-only.py`.
