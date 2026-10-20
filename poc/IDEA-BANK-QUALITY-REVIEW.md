# Idea Bank Quality Gate Review

**Purpose**: Systematically review all PoC ideas in POC-IDEAS.md against the 3-gate quality process to determine which are ready for execution.

**Date**: 2026-10-19
**Reviewer**: Initial quality assessment
**Total ideas**: 32 PoCs across 9 themes

---

## Review Summary

| Category | Count | Notes |
|----------|-------|-------|
| ✅ **Ready** (pass all 3 gates) | TBD | Can register immediately |
| 🟡 **Needs Work** (fails 1-2 gates) | TBD | Need additional research/validation |
| ❌ **Reject** (fails all gates) | TBD | Fundamentally flawed or out of scope |
| ⚫ **Already Done** | 4 | PoC 006-009 completed |

---

## Theme 1: Ultra-Low-Bit Quantization Models (5 ideas)

### PoC-Q1: Bonsai 2B vs Qwen2.5-1.5B Q4 on CUAD

**Gate 1: Problem Validation** - ✅ PASS
- Problem: Qwen 1.5B Q4 is 1.0 GB, too large for some devices
- Evidence: PoC 006-009 baseline established (67.9% key-fact accuracy)
- Root cause: Model size limits deployment on lower-end devices
- Solution fit: Bonsai 2B (0.43 GB) is 2.3× smaller, could enable broader deployment

**Gate 2: Solution Understanding** - ⚠️ PARTIAL
- Method: Ternary quantization (1.58-bit weights: {-1, 0, +1})
- Understood: Yes - PrismML published benchmarks (96-97% performance retention)
- Implementation: Need to verify GGUF availability and llama.swift compatibility
- Prediction: Expected to be slightly worse than Q4 but acceptable for 2.3× size reduction
- **Missing**: Need to verify Bonsai 2B is actually available and compatible

**Gate 3: Feasibility & ROI** - ✅ PASS
- Edge fit: 0.43 GB (well within limits)
- Effort: 1-2 weeks (reuse PoC 006-009 harness)
- Impact: 2.3× size reduction enables deployment on more devices
- ROI: High - if accuracy is close, huge deployment win
- Alternatives: BitNet, Maple (but Bonsai has best benchmarks)

**Verdict**: 🟡 **NEEDS WORK**
- **Action**: Verify Bonsai 2B GGUF availability before approval
- **If available**: ✅ APPROVED (high priority)
- **If not available**: ⏸️ PAUSED (wait for model release)

---

### PoC-Q2: Maple-MoE 20B in 5.3 GB

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes we need 20B parameter model
- Evidence: **None** - PoC 009 showed Qwen 1.5B (0.75B effective) works well (67.9%)
- Root cause: Not identified - do we actually need more parameters?
- Solution fit: **Mismatch** - solving a problem we don't have

**Gate 2: Solution Understanding** - ✅ PASS
- Method: MoE with ternary quantization
- Well understood from DeepGrove's paper

**Gate 3: Feasibility & ROI** - ❌ FAIL
- Edge fit: 5.3 GB is at the absolute limit (4 GB target)
- Impact: Unclear - we don't know if more parameters help
- ROI: Low - high complexity, uncertain benefit
- Alternative: Use Bonsai 2B or Qwen 3B first

**Verdict**: ❌ **REJECT**
- **Reason**: No validated need for 20B parameters on CUAD
- **Action**: Archive or revisit only if smaller models fail

---

### PoC-Q3: BitNet b1.58 1.5B on CUAD

**Gate 1: Problem Validation** - ✅ PASS
- Same as PoC-Q1 (size reduction need validated)

**Gate 2: Solution Understanding** - ⚠️ PARTIAL
- Method: BitNet ternary quantization
- **Missing**: Availability of BitNet 1.5B in GGUF format?
- Less proven than Bonsai (Bonsai shows 96-97% retention, BitNet unclear)

**Gate 3: Feasibility & ROI** - ⚠️ PARTIAL
- ROI: Lower than Bonsai (less proven, similar size)
- Priority: Test Bonsai first (better benchmarks)

**Verdict**: 🟠 **LOW PRIORITY**
- **Action**: Defer until after PoC-Q1 (Bonsai)
- Only run if Bonsai fails or unavailable

---

### PoC-Q4: Intel BITCOS & Samsung LittleBit

**Gate 1: Problem Validation** - ✅ PASS
- Same size reduction need

**Gate 2: Solution Understanding** - ❌ FAIL
- Method: Proprietary, research-stage
- **Not available** for deployment
- No GGUF or llama.cpp support

**Gate 3: Feasibility & ROI** - ❌ FAIL
- Not deployable on iPhone
- Research-only (2026-2027 papers)

**Verdict**: ⏸️ **PAUSED**
- **Reason**: Models not available for deployment
- **Action**: Monitor for release, revisit in 6-12 months

---

### PoC-Q5: Ultra-Low-Bit Comparison Study

**Gate 1: Problem Validation** - ⚠️ PARTIAL
- Good idea to compare methods
- But: Should run individual PoCs first
- Premature to compare before testing any

**Gate 3: Feasibility & ROI** - ❌ FAIL
- High effort (4-6 weeks)
- Low immediate value (comparison without baseline)

**Verdict**: 🟠 **LOW PRIORITY**
- **Action**: Run PoC-Q1 (Bonsai) first
- Only do comparison study if multiple models succeed

---

## Theme 2: Memory-Efficient RAG (7 ideas)

### PoC-R1: BM25-Only Retrieval (PoC 010 DRAFT)

**Gate 1: Problem Validation** - ✅ PASS
- Problem: 600 MB embedding model (EmbeddingGemma) is large
- Evidence: PoC 007 baseline (61.4% recall with hybrid)
- Question: Is semantic embedding necessary for keyword-rich CUAD?
- Root cause: Hybrid retrieval uses both BM25 + embeddings, but CUAD is keyword-heavy

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Pure BM25 keyword search (no embeddings)
- Well-understood, simple to implement
- Prediction: **Likely to fail** (semantic matching needed) but worth validating
- Reasoning: CUAD has some semantic queries ("governing law" matches "jurisdiction")

**Gate 3: Feasibility & ROI** - ✅ PASS
- Effort: 30 minutes (reuse PoC 007, disable embeddings)
- Impact if success: Eliminate 600 MB dependency (huge win)
- Impact if fail: Validates that embeddings are necessary (useful negative)
- ROI: **Very high** - low effort, high potential payoff

**Verdict**: ✅ **APPROVED** (HIGH PRIORITY)
- **Action**: Register as PoC 010, run immediately
- Expected outcome: Reject (but worth testing)

---

### PoC-R2: MobileRAG Power Optimization

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes RAG power consumption is too high
- Evidence: **None** - we haven't measured power consumption yet
- Root cause: Not identified - is power actually a problem on iPhone?

**Gate 2: Solution Understanding** - ✅ PASS
- Method: RAGCache, deduplication, early-exit
- Well documented in MobileRAG paper

**Gate 3: Feasibility & ROI** - ❌ FAIL
- Premature: Need to measure baseline power first
- High complexity for uncertain problem

**Verdict**: ⏸️ **PAUSED**
- **Action**: First measure PoC 007's power consumption on iPhone
- Only proceed if power is >X% of budget

---

### PoC-R3: EdgeRAG Prefetching

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes TTFT (time to first token) is too high
- Evidence: **None** - we haven't measured TTFT as a pain point
- Root cause: Not validated

**Gate 3: Feasibility & ROI** - ❌ FAIL
- High complexity (background prefetching, cache management)
- Uncertain benefit

**Verdict**: ⏸️ **PAUSED**
- **Action**: Measure TTFT baseline first
- Only if TTFT >X seconds AND users complain

---

### PoC-R4: SmartRAG Graph-Based

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes hierarchical/graph structure needed
- Evidence: **None** - CUAD contracts don't have clear graph structure
- Not validated that flat chunks are failing

**Gate 3: Feasibility & ROI** - ❌ FAIL
- High complexity (4-6 weeks)
- 4-5.5 GB RAM (at edge limit)
- Uncertain benefit for legal contracts

**Verdict**: ❌ **REJECT**
- **Reason**: CUAD contracts are flat documents, not knowledge graphs
- Better for Wikipedia/knowledge bases

---

### PoC-R5: BM25 + Embedding Hybrid Tuning

**Gate 1: Problem Validation** - ⚠️ PARTIAL
- Problem: PoC 007 uses 0.7 semantic + 0.3 BM25
- Question: Is this optimal?
- Evidence: Not validated that this is suboptimal

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Grid search over semantic weights [0.3, 0.5, 0.7, 0.9]
- Simple, well-understood

**Gate 3: Feasibility & ROI** - ✅ PASS
- Effort: 2-3 hours (rerun PoC 007 with different weights)
- Impact: +1-3 points recall (modest but easy)
- ROI: High for low effort

**Verdict**: ✅ **APPROVED** (MEDIUM PRIORITY)
- **Action**: Can run as quick experiment after PoC 010
- Note: PoC 007 README mentions this was "not registered" but tested

---

### PoC-R6: SQLite-vec for Embedding Storage

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes embedding storage/search is slow or inefficient
- Evidence: **None** - PoC 007 doesn't report storage as bottleneck
- Root cause: Not identified

**Gate 3: Feasibility & ROI** - ❌ FAIL
- Engineering complexity (integrate SQLite-vec)
- Uncertain benefit (is it actually faster than in-memory?)

**Verdict**: 🟠 **LOW PRIORITY**
- **Action**: Only if embedding search becomes a measured bottleneck

---

### PoC-R7: Model Download Optimization

**Gate 1: Problem Validation** - ⚠️ PARTIAL
- Problem: Large model downloads (600 MB EmbeddingGemma, 1 GB Qwen)
- Valid for production, but not a research problem

**Gate 3: Feasibility & ROI** - ❌ FAIL (for research lab)
- This is engineering/infrastructure, not research
- Out of scope for PoC experiments

**Verdict**: ❌ **REJECT** (not a research PoC)
- **Action**: Move to engineering backlog if needed for production

---

## Theme 3: Efficient Document Intelligence (4 ideas)

### PoC-D1: Qwen2.5-VL for Layout Analysis

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes we need vision model for CUAD contracts
- Evidence: **None** - CUAD is plain text, no complex layouts
- Root cause: Not applicable to current dataset

**Gate 3: Feasibility & ROI** - ❌ FAIL
- 4-5 GB model (too large)
- Wrong problem for CUAD (text-only)

**Verdict**: ❌ **REJECT**
- **Reason**: CUAD doesn't have layout complexity requiring VLM
- **Note**: Could be useful for different dataset (PDFs with tables/images)

---

### PoC-D2: Semantic Chunking vs Fixed-Size

**Gate 1: Problem Validation** - ⚠️ PARTIAL
- Problem: Fixed-size chunks (175 words) might cut sentences/sections
- Evidence: Weak - PoC 007 uses sentence-boundary chunking already
- Need to analyze if sentence-aware chunking is failing

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Chunk at paragraph/section boundaries
- Well-understood

**Gate 3: Feasibility & ROI** - ⚠️ PARTIAL
- Effort: 1-2 weeks (re-chunk, re-embed, re-run retrieval)
- Impact: Uncertain - PoC 007 already respects sentence boundaries
- ROI: Medium - potentially useful but unclear benefit

**Verdict**: 🟡 **NEEDS WORK**
- **Action**: First analyze PoC 007's chunking - does it cut mid-sentence?
- If yes (>10% of chunks): ✅ Approve
- If no: ❌ Reject (already doing semantic chunking)

---

### PoC-D3 & D4: VLM-based approaches

Similar to PoC-D1 - rejected for text-only CUAD dataset.

**Verdict**: ❌ **REJECT** (dataset mismatch)

---

## Theme 4: Advanced Document Processing (3 ideas)

### PoC-A1: Hierarchical Chunking with Parent Context

**Gate 1: Problem Validation** - ⚠️ PARTIAL
- Problem: Small chunks lack surrounding context
- Related to PoC 011, but different approach
- Evidence: Weak - need to validate small chunks are actually failing

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Retrieve child chunks, pass parent chunk to LLM
- Well-understood from RAG best practices

**Gate 3: Feasibility & ROI** - ⚠️ PARTIAL
- Effort: 1-2 weeks
- Impact: Unknown - is context actually the problem?
- Alternative: PoC 012 (cross-encoder) is more proven

**Verdict**: 🟡 **NEEDS WORK**
- **Action**: Validate problem first (analyze PoC 007 failures)
- Lower priority than PoC 012

---

### PoC-A2: Semantic Deduplication

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes many duplicate/near-duplicate chunks
- Evidence: **None** - CUAD contracts are unique legal docs
- Unlikely to have much duplication

**Verdict**: ❌ **REJECT**
- **Reason**: Legal contracts are diverse, not repetitive

---

### PoC-A3: Contextual Embeddings

**Verdict**: ❌ **REJECTED** (PoC 011 already tested and failed)

---

### PoC-A4: Late Chunking

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes chunk-then-embed loses context
- Evidence: None - theoretical concern without validation

**Gate 2: Solution Understanding** - ⚠️ PARTIAL
- Method: Embed full doc, then split embeddings
- Less common approach, unclear if better

**Gate 3: Feasibility & ROI** - ❌ FAIL
- High complexity
- Uncertain benefit over proven methods

**Verdict**: ⏸️ **PAUSED**
- **Action**: Research more on late chunking effectiveness first

---

## Theme 5: Inference Optimization (5 ideas)

### PoC-I1: Cross-Encoder Reranking (PoC 012 DRAFT)

**Gate 1: Problem Validation** - ✅ PASS
- Problem: Hybrid retrieval recall at 61.4%, room for improvement
- Evidence: PoC 007 baseline established
- Solution: Industry best practice (rerank top-K with cross-encoder)

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Retrieve top-10, rerank with cross-encoder to top-3
- Models: mxbai-rerank-base-v1 (184M), ms-marco-TinyBERT (4M)
- Prediction: +2-5 points recall (based on RAG literature)
- Well-understood, proven approach

**Gate 3: Feasibility & ROI** - ✅ PASS
- Edge fit: 184M or 4M model (acceptable)
- Effort: 1-2 weeks (integrate with PoC 007)
- Impact: High confidence based on industry adoption
- ROI: High - proven technique, moderate effort

**Verdict**: ✅ **APPROVED** (HIGH PRIORITY)
- **Action**: Register as PoC 012, prioritize after PoC 010
- Expected outcome: Adopt (industry standard)

---

### PoC-I2: KV Cache Quantization

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes KV cache is memory bottleneck
- Evidence: **None** - haven't measured KV cache size on CUAD
- Root cause: Not validated

**Gate 3: Feasibility & ROI** - ❌ FAIL
- Premature optimization
- Need to measure baseline first

**Verdict**: ⏸️ **PAUSED**
- **Action**: Profile memory usage first
- Only if KV cache >X% of memory budget

---

### PoC-I3: Speculative Decoding

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes generation latency is too high
- Evidence: **None** - PoC 009 median 583ms prefill is acceptable
- Root cause: Not validated as pain point

**Verdict**: ⏸️ **PAUSED**
- **Action**: Measure user-perceived latency first

---

### PoC-I4: Prompt Caching (Anthropic-style)

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes repeated prompts are common
- Evidence: **None** - CUAD is one-shot Q&A, not conversation
- Use case mismatch

**Verdict**: ❌ **REJECT**
- **Reason**: CUAD is single-turn Q&A, no prompt reuse

---

### PoC-I5: Sparse Attention Patterns

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes full attention is too expensive
- Evidence: None
- Model already small (1.5B)

**Gate 3: Feasibility & ROI** - ❌ FAIL
- High complexity (model architecture changes)
- Uncertain benefit for small models

**Verdict**: ❌ **REJECT**
- **Reason**: Premature optimization for 1.5B model

---

## Theme 6: Mobile-Specific Optimizations (4 ideas)

### PoC-M1: Incremental Index Updates

**Gate 1: Problem Validation** - ❌ FAIL
- Engineering optimization, not research problem
- No validated need for index updates in CUAD

**Verdict**: ❌ **REJECT** (engineering, not research)

---

### PoC-M2: Query Result Deduplication

**Gate 1: Problem Validation** - ❌ FAIL
- Problem: Assumes duplicate results are common
- Evidence: None

**Verdict**: ❌ **REJECT**

---

### PoC-M3: Thermal Throttling Measurement

**Gate 1: Problem Validation** - ⚠️ PARTIAL
- Valid concern for iPhone deployment
- But: Measurement, not experiment

**Gate 3: Feasibility & ROI** - ⚠️ PARTIAL
- Useful for production, but not a PoC
- This is validation/testing, not research

**Verdict**: 🟠 **LOW PRIORITY** (move to testing checklist)
- **Action**: Include thermal measurement in all PoCs that run on iPhone
- Not a standalone PoC

---

### PoC-M4: Adaptive Batch Sizing

**Gate 1: Problem Validation** - ❌ FAIL
- Premature optimization
- No evidence that batch size is a problem

**Verdict**: ⏸️ **PAUSED**

---

## Theme 7: Evaluation & Measurement (2 ideas)

### PoC-E1: Human Eval on CUAD Subset

**Gate 1: Problem Validation** - ⚠️ PARTIAL
- Valid: Key-fact accuracy might not match human perception
- But: Should validate key-fact metric first before adding human eval

**Gate 3: Feasibility & ROI** - ⚠️ PARTIAL
- High effort (10-20 hours human time)
- Better to validate key-fact correlation first

**Verdict**: 🟠 **LOW PRIORITY**
- **Action**: Run after several PoCs to validate metric

---

### PoC-E2: Energy Profiling Framework

Similar to thermal measurement - useful but not a research PoC.

**Verdict**: 🟠 **LOW PRIORITY** (testing infrastructure)

---

## FINAL SUMMARY

### ✅ **APPROVED - Ready for Execution** (3 PoCs)

| ID | Title | Priority | Effort | Expected ROI |
|----|-------|----------|--------|--------------|
| **PoC-R1** | BM25-Only Retrieval (PoC 010) | **HIGH** | 30 min | Very High |
| **PoC-I1** | Cross-Encoder Reranking (PoC 012) | **HIGH** | 1-2 weeks | High |
| **PoC-R5** | BM25/Semantic Weight Tuning | **MEDIUM** | 2-3 hours | Medium |

**Action**: Register and run these 3 immediately.

---

### 🟡 **NEEDS WORK - Requires Problem Validation** (5 PoCs)

| ID | Title | Missing | Action |
|----|-------|---------|--------|
| PoC-Q1 | Bonsai 2B | Verify model availability | Check GGUF release |
| PoC-D2 | Semantic Chunking | Analyze current chunking | Review PoC 007 chunks |
| PoC-A1 | Hierarchical Chunking | Validate context problem | Analyze PoC 007 failures |
| PoC-R2 | MobileRAG Power | Measure baseline power | Profile on iPhone |
| PoC-R3 | EdgeRAG Prefetching | Measure TTFT baseline | Time measurements |

**Action**: Complete validation work before approval.

---

### ⏸️ **PAUSED - Waiting on Research/Tools** (7 PoCs)

- PoC-Q4 (BITCOS/LittleBit) - Models not released
- PoC-I2 (KV Cache) - Need to measure first
- PoC-I3 (Speculative Decoding) - Need to measure latency
- PoC-A4 (Late Chunking) - Need more research
- PoC-M4 (Adaptive Batch) - Premature optimization
- PoC-E1 (Human Eval) - Run after validating key-fact metric
- PoC-E2 (Energy Profiling) - Infrastructure work

**Action**: Monitor research, revisit in 3-6 months.

---

### ❌ **REJECTED - Fundamentally Flawed** (14 PoCs)

**Reasons**:
- Dataset mismatch (VLMs on text-only CUAD): 4 PoCs
- Premature optimization (no validated problem): 5 PoCs
- Engineering/infrastructure (not research): 3 PoCs
- Out of scope (too large, wrong use case): 2 PoCs

**Action**: Archive, revisit only if dataset/requirements change.

---

### ⚫ **COMPLETED** (4 PoCs)

- PoC 006: Doc Q&A (Foundation Models, Gemma, Qwen)
- PoC 007: Embedding Retrieval Recall
- PoC 008: Absence Instruction for Doc Q&A
- PoC 009: Retrieval Depth for Qwen

---

## Recommendations

### Immediate Action (Next 2 Weeks)

1. **PoC 010 (BM25-Only)** - Run first (30 min, high value)
2. **PoC 012 (Cross-Encoder)** - Register and execute (high confidence)
3. **BM25 Weight Tuning** - Quick experiment (2-3 hours)

### Short-term (Next Month)

1. **PoC-Q1 (Bonsai)** - IF model is available
2. **PoC-D2 (Semantic Chunking)** - After analyzing PoC 007

### Quality Gate Impact

**Before quality gate**:
- 32 PoC ideas, most not validated
- Would waste time on 14 rejected + 7 paused = 21 dead ends
- Estimated wasted effort: 200-400 hours

**After quality gate**:
- 3 approved (ready to run)
- 5 need validation work (clear path forward)
- 21 rejected/paused (saved 200-400 hours)
- **Focus on high-ROI experiments**

---

*This review demonstrates the value of the quality gate process: filtering 32 ideas down to 3 ready-to-execute experiments.*
