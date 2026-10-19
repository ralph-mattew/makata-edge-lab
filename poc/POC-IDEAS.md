# PoC Idea Bank

**Purpose**: Tracking potential experiments for the Makata AI Edge Lab. Ideas are organized by theme and marked with feasibility estimates. This is a working document—ideas may be merged, split, or dropped as research progresses.

**Quality Gate**: All PoCs must pass the 3-gate review process (see [POC-QUALITY-GATE.md](POC-QUALITY-GATE.md)) before registration.

**Status Legend**:
- 🟢 **Feasible** (not vetted) - Initial entry, needs quality gate review
- ✅ **Approved** (passed quality gate) - Ready for registration and execution
- 🟡 **Under Review** (in quality gate) - Currently being vetted by reviewers
- ⏸️ **Paused** (needs more research) - Failed Gate 2, need better understanding
- ❌ **Rejected** (fundamentally flawed) - Failed Gate 1 or 3, documented reason below
- 🟠 **Low Priority** (feasible but low ROI) - Passed gates but deferred for higher-impact work
- ⚫ **Completed** (experiment done) - Results published in lab repository

**Last updated**: 2026-10-19

---

## Theme 1: Ultra-Low-Bit Quantization Models

### PoC-Q1: Bonsai 2B vs Qwen2.5-1.5B Q4 on CUAD
**Status**: 🟢 High feasibility
**Estimated effort**: 1-2 weeks

**Question**: Does Bonsai 2 2B (0.43 GB, ternary 1.58-bit) match or exceed Qwen2.5-1.5B Q4_K_M (1.0 GB) on document Q&A key-fact accuracy?

**Why it matters**:
- 2.3× smaller footprint (0.43 GB vs 1.0 GB)
- 2.67× more parameters (2B vs 0.75B effective)
- Tests whether ternary quantization can replace traditional Q4 for on-device document Q&A
- Bonsai retains 96-97% of base Qwen3.5 2B performance on benchmarks

**Hypotheses**:
- H1: Bonsai 2B key-fact rate is at least 3 points above Qwen Q4 (current: 67.9%)
- H2: Bonsai 2B prefill time is at most 1.5× Qwen Q4 (current median: 583 ms)
- H3: Bonsai 2B runs on iPhone without thermal throttling over 100 items

**Setup**:
- Reuse PoC 006-009 harness (CUAD dataset, 1,325 answerable items, 464 key-fact items)
- Model: Ternary-Bonsai-2-2B via llama.cpp/MLX
- Control: Qwen2.5-1.5B-Instruct Q4_K_M (current Xylo baseline)
- Same prompt, sampler settings, retrieval (EmbeddingGemma 3 chunks)

**Decision rule**:
- If H1 and H2 hold: adopt (host stage), recommend Bonsai for Xylo
- If H1 holds but H2 fails: reject (trade-off), latency cost too high
- Otherwise: inconclusive

**Prerequisites**:
- Verify Bonsai 2B GGUF availability and llama.swift compatibility
- Test MLX vs llama.cpp performance on Mac first

**References**:
- PrismML Bonsai 2 announcement: https://prismml.com/news/bonsai-2-family
- HuggingFace: prism-ml/Ternary-Bonsai-2-2B-mlx-2bit
- License: Apache 2.0

---

### PoC-Q2: Bonsai 2 4B vs Qwen2.5-1.5B Q4 (Memory-Matched)
**Status**: 🟢 High feasibility
**Estimated effort**: 1-2 weeks (can run in parallel with PoC-Q1)

**Question**: At similar memory footprint (~1 GB), does Bonsai 2 4B (ternary) outperform Qwen2.5-1.5B Q4 on CUAD document Q&A?

**Why it matters**:
- Fair memory comparison (0.95 GB vs 1.0 GB)
- Tests if ternary + more parameters beats Q4 + fewer parameters
- Directly answers: "should Xylo switch to ternary models?"
- Bonsai 2 4B retains 96-99% of base Qwen3.5 4B performance

**Hypotheses**:
- H1: Bonsai 4B key-fact rate is at least 5 points above Qwen Q4
- H2: Bonsai 4B prefill time is at most 2.0× Qwen Q4
- H3: Memory usage delta is within ±100 MB

**Setup**: Same as PoC-Q1, model swap only

**Decision rule**:
- If H1 and H2 hold: adopt (host stage)
- If H1 holds but H2 fails and ratio >2.5×: reject (latency)
- Otherwise: inconclusive

---

### PoC-Q3: Maple-Preview (20B MoE) for Contract Reasoning
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2-3 weeks

**Question**: Does Maple-Preview 20B-A1B (5.3 GB, ternary MoE, 1B active per token) improve reasoning on complex multi-clause contract questions vs Qwen models?

**Why it matters**:
- Fits in 6GB iPhone budget (5.3 GB model)
- Only 1B parameters active per token (fast inference: 218 tok/s on Mac mini M4)
- SOTA reasoning in weight class, solves IMO-level problems
- Tests if MoE architecture helps document understanding beyond simple fact extraction

**Hypotheses**:
- H1: Maple-Preview improves on multi-hop questions (e.g., "does X apply if Y?")
- H2: Single-hop key-fact rate is within 3 points of Qwen2.5-1.5B Q4
- H3: Prefill time is at most 1.2× despite 20B total parameters

**Setup**:
- Need to create multi-hop question subset from CUAD or new dataset
- Model: deepgrove/maple-preview GGUF
- Compare against: Qwen2.5-1.5B Q4, possibly Qwen2.5-7B Q4

**Prerequisites**:
- Verify GGUF compatibility with llama.swift
- Design multi-hop reasoning metric (current key-fact is single-hop)
- Test on Mac first for memory profiling

**References**:
- DeepGrove announcement: Aug 4, 2026
- HuggingFace: deepgrove/maple-preview, stamsam/maple-preview-gguf
- License: MIT

---

### PoC-Q4: Ternary vs Q4 Retrieval Depth Interaction
**Status**: 🟢 High feasibility
**Estimated effort**: 1-2 weeks (extends PoC 009)

**Question**: Does retrieval depth (3 vs 5 chunks) interact differently with ternary models (Bonsai) vs Q4 models (Qwen)?

**Why it matters**:
- PoC 009 found 5 chunks distract Qwen2.5-1.5B when answer is in the 3 chunks
- Ternary models may handle context differently due to quantization
- Your note: "focused context beats maximal" for 1.5B—does this hold for ternary?

**Hypotheses**:
- H1: Bonsai 2B shows less distraction at 5 chunks than Qwen Q4 (H2 from PoC 009)
- H2: For items not covered by 3 chunks, Bonsai gains more from 5 chunks than Qwen
- H3: Optimal chunk count differs between ternary and Q4 quantization

**Setup**:
- Run Bonsai 2B with 1, 3, 5 chunks (same items as PoC 009)
- Compare distraction effect: key-fact rate drop when answer is already in 3 chunks
- Same CUAD items, retrieval, scoring

**Decision rule**: Descriptive study, no adopt/reject verdict

---

## Theme 2: Memory-Efficient RAG

### PoC-R1: BM25-Only vs Hybrid Retrieval
**Status**: ⚫ **Completed** (PoC 010 - reject)
**Estimated effort**: 1-2 days (actual: 30 minutes)

**Question**: Can BM25-only retrieval on CUAD contracts match EmbeddingGemma hybrid recall while eliminating embedding compute?

**Verdict**: **REJECT** - BM25-only recall 15 points below hybrid; semantic embeddings necessary

**Results**:
- BM25-only: 46.4% recall@3 (615/1,325 items)
- Hybrid baseline: 61.4% recall@3 (814/1,325 items)
- Difference: -15.0 points (-199 items)

**Key findings**:
- Even "keyword-rich" queries need semantic understanding
- Agreement Date (expected keyword-heavy) performed WORST: 12% vs 72%
- Paraphrase handling critical: "30 days" vs "one month", "Delaware" vs "State of Delaware"
- Validates EmbeddingGemma's 600 MB footprint is necessary

**Impact**: Definitively rules out BM25-only optimization; semantic embeddings cannot be eliminated

**Full write-up**: [PoC 010](https://github.com/ralph-mattew/makata-edge-lab/tree/main/poc/010-bm25-only-retrieval)
**Website**: [Makata AI Lab](https://makata.ai/lab/experiments/010-bm25-only-retrieval/)

---

### PoC-R2: MobileRAG Selective Content Reduction
**Status**: 🟢 High feasibility
**Estimated effort**: 3-5 days

**Question**: Does reducing retrieved chunk tokens by 20-40% (à la MobileRAG SCR) maintain key-fact accuracy while improving Qwen prefill time?

**Why it matters**:
- PoC 009 found 3 chunks better than 5 for Qwen2.5-1.5B ("focused context")
- MobileRAG reduces tokens per chunk, not chunk count
- Could achieve same "focus" more efficiently: 3 trimmed chunks vs 5 full chunks
- MobileRAG paper: 7-42% token reduction without accuracy loss

**Hypotheses**:
- H1: 40% token reduction per chunk maintains key-fact rate within 2 points (baseline: 67.9%)
- H2: Prefill time reduces by at least 25% (current median: 583 ms)
- H3: "Distraction" effect (PoC 009 H2) is eliminated or reduced

**Setup**:
- Implement token reduction: truncate chunks to 60% of original length
- Methods to test: (a) tail truncation, (b) middle truncation (keep start+end), (c) sentence-aware
- Run on same CUAD items, 3 chunks, EmbeddingGemma retrieval
- Measure: key-fact rate, prefill time, answer quality

**Decision rule**:
- If H1 and H2 hold: adopt, recommend token reduction for Xylo
- If H1 holds but H2 <15% gain: inconclusive (gain too small)
- If H1 fails: reject

**Prerequisites**: None (pure preprocessing)

**References**: MobileRAG paper (Jul 2025), arXiv:2507.01079

---

### PoC-R3: EdgeRAG On-Demand Embedding Generation
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2-3 weeks

**Question**: Does EdgeRAG's on-demand embedding generation reduce Xylo's RAM footprint while maintaining recall on CUAD contracts?

**Why it matters**:
- Xylo pre-computes all embeddings (memory intensive for large libraries)
- EdgeRAG generates embeddings on-demand at query time (CPU intensive, RAM light)
- Tradeoff: RAM vs CPU time vs battery
- EdgeRAG paper: 1.8-3.82× faster time-to-first-token, 4× better tail latency

**Hypotheses**:
- H1: EdgeRAG reduces peak RAM by at least 40% vs current approach (measure: RSS before/after indexing)
- H2: EdgeRAG recall on CUAD is within 3 points of current (baseline: 61.4%)
- H3: EdgeRAG time-to-first-answer is at most 1.5× current approach

**Setup**:
- Requires FAISS IVF index integration (different from current)
- Two-level index: centroids in RAM, second-level on-demand
- Adaptive caching for expensive clusters
- Host: Mac M4 Pro first, then iPhone

**Decision rule**:
- If H1, H2, H3 hold: adopt (host stage), recommend for large-library scenario
- If H1 holds but H3 >2×: reject (latency cost)
- Otherwise: inconclusive

**Prerequisites**:
- Integrate FAISS with Swift (or find alternative IVF implementation)
- Significant architecture change from current pipeline

**References**: EdgeRAG paper (Dec 2024), arXiv:2412.21023

---

### PoC-R4: Parent-Child Hierarchical Chunking
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does retrieving small child chunks but reading large parent chunks improve key-fact accuracy vs current flat chunking?

**Why it matters**:
- Your PoC 007: median chunk is 25 words (very small, may lose context)
- Parent-child gives precision retrieval + coherent context
- Industry standard for production RAG systems (2026)
- May reduce "distraction" from PoC 009 by giving model better context window

**Hypotheses**:
- H1: Parent-child improves key-fact rate by at least 3 points (baseline: 67.9%)
- H2: Retrieval precision improves (fewer false-positive chunks in top-3)
- H3: Prefill time increases by at most 1.3× (larger parent chunks)

**Setup**:
- Child chunks: current 25-word median chunks (for retrieval/embedding)
- Parent chunks: 200-300 word surrounding context (fed to LLM)
- Retrieve top-3 children via EmbeddingGemma, return their parents to Qwen
- Measure: key-fact rate, recall, prefill time

**Decision rule**:
- If H1 holds and H3 holds: adopt
- If H1 holds but H3 >1.5×: inconclusive (latency trade-off)
- Otherwise: reject, current chunking is sufficient

**Prerequisites**: Modify chunker to track parent-child relationships

---

### PoC-R5: Lightweight Embedding Model Swap
**Status**: 🟢 Very high feasibility
**Estimated effort**: 2-3 days

**Question**: Does all-MiniLM-L6-v2 (22M params, 384-dim) match EmbeddingGemma-300M (768-dim) on CUAD recall while using 50% less memory?

**Why it matters**:
- EmbeddingGemma: ~600 MB
- all-MiniLM-L6-v2: ~90 MB (6.7× smaller)
- Could free RAM for larger chat models, more chunks, or other features
- MiniLM is the most popular lightweight embedding model (2026)

**Hypotheses**:
- H1: all-MiniLM recall is within 3 points of EmbeddingGemma (baseline: 61.4%)
- H2: Embedding time is at least 2× faster (smaller model)
- H3: Lower dimensions reduce FAISS index size by ~40% (384 vs 768 dims)

**Setup**:
- Drop-in replacement: all-MiniLM-L6-v2 instead of EmbeddingGemma
- Same CUAD contracts, same chunking, same hybrid retrieval (0.7 semantic, 0.3 BM25)
- Measure: recall, key-fact rate (with Qwen), embedding time, index size

**Decision rule**:
- If H1 holds: adopt, recommend MiniLM for memory-constrained scenarios
- If H1 fails but within 5 points: inconclusive (acceptable for some use cases)
- If H1 fails >5 points: reject, EmbeddingGemma quality is necessary

**Prerequisites**: None (standard model, widely supported)

**References**:
- Model: sentence-transformers/all-MiniLM-L6-v2
- 22M parameters, 384 dimensions, ~90 MB

---

### PoC-R6: NLEmbedding vs EmbeddingGemma Fallback Analysis
**Status**: 🟢 High feasibility
**Estimated effort**: 3-5 days

**Question**: What causes the 22-point gap between EmbeddingGemma and NLEmbedding retrieval (PoC 007: 61.4% vs 35.2%), and can it be narrowed?

**Why it matters**:
- NLEmbedding is Xylo's fallback when EmbeddingGemma unavailable
- 22-point gap is huge (PoC 007)
- PoC 009 showed NLEmbedding gains more from 5 chunks (+4.5 points) than EmbeddingGemma (+0.4)
- Understanding failure modes could improve fallback quality

**Hypotheses**:
- H1: NLEmbedding fails on multilingual/non-English entity names
- H2: NLEmbedding degrades on longer chunks (>50 words)
- H3: Increasing NLEmbedding's semantic weight in hybrid (>0.7) improves recall

**Setup**:
- Analyze per-category differences (PoC 007 data)
- Analyze per-chunk-length differences
- Test hybrid weight variations: 0.5, 0.7, 0.9 semantic weight
- Qualitative: error analysis on top 50 failures

**Decision rule**: Descriptive study, no adopt/reject verdict

---

## Theme 3: Efficient Document Intelligence

### PoC-D1: Structured vs Unstructured Parsing for Contracts
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2-3 weeks

**Question**: Does structured parsing (headers, sections, lists) improve retrieval and Q&A accuracy vs treating contracts as plain text?

**Why it matters**:
- Field Note 004: "Structure-aware document reading"
- Contracts have clear structure: sections, subsections, numbered clauses
- Structure could improve: (a) chunking, (b) retrieval context, (c) answer grounding

**Hypotheses**:
- H1: Structure-aware chunking improves recall by at least 5 points
- H2: Including section headers in chunks improves key-fact rate by ≥3 points
- H3: Answer citation becomes more precise (section 3.2 vs page 5)

**Setup**:
- Parse CUAD contracts for structure (Markdown-like hierarchy)
- Chunk with section boundaries (don't split mid-section)
- Include section headers in chunk context
- Compare: plain text vs structure-aware

**Prerequisites**:
- PDF/text parsing that preserves structure
- CUAD contracts are already flattened—may need original PDFs

---

### PoC-D2: Multimodal Document Understanding (Tables, Images)
**Status**: 🟠 Low feasibility
**Estimated effort**: 4+ weeks

**Question**: Does including visual elements (tables, signature blocks, diagrams) improve contract Q&A vs text-only?

**Why it matters**:
- Contracts have tables (pricing, schedules), signature blocks (parties), diagrams
- Text extraction often loses table structure
- Multimodal models (ColPali, Qwen-VL) can read PDFs as images

**Hypotheses**:
- H1: Table-heavy questions (pricing, schedules) improve by ≥10 points with visual parsing
- H2: Model can correctly identify signature parties from visual signature blocks
- H3: Latency remains <5 seconds per page on iPhone

**Setup**:
- Need CUAD original PDFs (not just text)
- Need multimodal embedding model (ColPali, Qwen-VL)
- Need to design table-heavy question set
- Compare: text-only vs multimodal

**Prerequisites**:
- Significant infrastructure: PDF rendering, multimodal embeddings, vision LLM
- ColPali/Qwen-VL quantization for mobile

**Status rationale**: Blocked until multimodal models are small enough for 6GB iPhones

---

### PoC-D3: Streaming vs Batch Document Processing
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does streaming document processing (chunk-by-chunk embedding) improve perceived latency vs batch (embed all chunks, then respond)?

**Why it matters**:
- Large documents (1000+ pages) take minutes to embed
- Streaming could enable "answer now, refine later" UX
- Tradeoff: initial answer quality vs user wait time

**Hypotheses**:
- H1: Streaming enables <5 second time-to-first-answer for large docs
- H2: Initial answer (from first 10% of document) is correct ≥40% of the time
- H3: Streaming uses ≤10% more total CPU time than batch

**Setup**:
- Embed CUAD contracts in streaming mode: first N chunks → answer → refine
- Measure: time-to-first-answer, initial accuracy, refinement convergence
- Compare: N = 10%, 25%, 50% of document

---

## Theme 4: Model Efficiency & Optimization

### PoC-M1: KV Cache Quantization Revisited
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2 weeks

**Question**: Does KV cache quantization (PoC 001 tested Q8, Q4) enable longer context or faster inference on current models?

**Why it matters**:
- PoC 001 rejected KV cache quantization for Unawain (summary quality loss)
- New models (Qwen2.5, Bonsai) may be more robust to KV quantization
- Longer context = more chunks = better retrieval (PoC 009)

**Hypotheses**:
- H1: Q8 KV cache for Qwen2.5-1.5B maintains key-fact rate within 1 point
- H2: Q8 enables 2× context size (2048 → 4096) within same RAM budget
- H3: Prefill/decode time unchanged or faster

**Setup**:
- Rerun PoC 001 methodology on Qwen2.5-1.5B (not Unawain's model)
- Test: Q8, Q4 KV cache
- Measure: key-fact rate, memory, latency

**Prerequisites**: llama.cpp/llama.swift support for KV cache quantization

---

### PoC-M2: Prompt Caching for Repeated Retrieval
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does caching KV state of retrieved chunks reduce latency for follow-up questions on the same document?

**Why it matters**:
- Multi-turn conversations reuse same retrieved chunks
- Prefill is latency bottleneck (PoC 009: 583 ms median)
- Anthropic/OpenAI use prompt caching; can we do it on-device?

**Hypotheses**:
- H1: Cached chunks reduce prefill time by ≥60% on follow-up questions
- H2: Cache hit rate ≥50% for multi-turn conversations
- H3: Cache overhead ≤200 MB RAM

**Setup**:
- Implement KV cache storage for retrieved chunks (keyed by chunk hash)
- Test on multi-turn Q&A (need to create or find dataset)
- Measure: prefill time reduction, cache hit rate, memory overhead

**Prerequisites**:
- llama.cpp/llama.swift KV cache export/import API
- Multi-turn conversation dataset

---

### PoC-M3: Speculative Decoding for Mobile
**Status**: 🟠 Low feasibility
**Estimated effort**: 4+ weeks

**Question**: Does speculative decoding with a draft model (e.g., Qwen 0.5B) speed up Qwen 1.5B generation on iPhone?

**Why it matters**:
- Speculative decoding: draft model generates candidates, main model verifies
- Can achieve 2-3× speedup in cloud settings
- Unclear if it works on mobile (memory overhead, thermal, CPU/GPU coordination)

**Hypotheses**:
- H1: Speculative decoding achieves ≥1.5× tokens/second on iPhone
- H2: Memory overhead ≤500 MB (draft model + main model)
- H3: Quality unchanged (verification ensures correctness)

**Prerequisites**:
- llama.cpp speculative decoding support
- Draft model selection and quantization
- Significant engineering effort

**Status rationale**: Low priority until basic optimizations (quantization, RAG) exhausted

---

## Theme 5: Evaluation & Measurement

### PoC-E1: Human Evaluation of Contract Q&A
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2-3 weeks (includes human labeling)

**Question**: How well does automated key-fact scoring (PoC 006-009) correlate with human judgment of answer quality?

**Why it matters**:
- Current metric: key-fact matching (6 categories, 464 items)
- Doesn't capture: completeness, clarity, hallucination, over-confidence
- Human eval is gold standard but expensive

**Hypotheses**:
- H1: Key-fact score correlates ≥0.7 with human ratings (Spearman ρ)
- H2: Hallucination rate (human-judged) ≤5% when key-fact is correct
- H3: Human preference aligns with key-fact + absence detection (PoC 008)

**Setup**:
- Sample 100-200 outputs from PoC 006-009
- Human raters score: correctness, completeness, hallucination (Likert scale)
- Compare with automated metrics
- Calculate correlation, agreement, calibration

**Prerequisites**:
- Human raters (internal or crowdsourced)
- Annotation guidelines
- IRB/ethics if external raters

---

### PoC-E2: Energy & Thermal Profiling Across PoCs
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Which PoC configurations (model, quantization, retrieval) are most energy-efficient and thermally stable on iPhone?

**Why it matters**:
- Battery life is critical for mobile AI
- Thermal throttling degrades performance
- No systematic comparison across PoCs yet

**Hypotheses**:
- H1: Ternary models (Bonsai) use ≤50% energy vs Q4 per token
- H2: EdgeRAG's on-demand embedding reduces thermal load vs pre-computed
- H3: BM25-only retrieval uses ≤30% energy vs hybrid

**Setup**:
- Measure: mWh/token, mWh/query, thermal state over 100 queries
- Compare: Qwen Q4, Bonsai ternary, different retrieval methods
- Device: iPhone 15 Pro, consistent starting thermal state

**Prerequisites**:
- iOS instrumentation for energy (already have thermal in PoC 001)
- Controlled environment (room temp, airplane mode)

---

## Theme 6: Cross-Cutting & Infrastructure

### PoC-I1: SQLite vs FAISS for Mobile Vector Search
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does SQLite with sqlite-vec match FAISS performance for small-to-medium vector indexes (<10k documents) on mobile?

**Why it matters**:
- SQLite is ubiquitous on mobile (iOS, Android)
- sqlite-vec extension adds vector search (2024)
- FAISS may be overkill for small indexes; SQLite is simpler
- MobileRAG paper uses SQLite

**Hypotheses**:
- H1: SQLite-vec search latency is within 2× FAISS for <10k vectors
- H2: SQLite index size is ≤1.5× FAISS size
- H3: SQLite eliminates dependency on FAISS build/binary

**Setup**:
- Index CUAD contracts (397 docs, ~10k chunks) in SQLite-vec and FAISS
- Measure: search latency, index size, memory usage
- Test: exact search and approximate (HNSW/IVF)

**Decision rule**:
- If H1, H2 hold: adopt SQLite-vec for mobile, simpler stack
- Otherwise: keep FAISS

**Prerequisites**: Integrate sqlite-vec with Swift

---

### PoC-I2: Model Download & Verification Pipeline
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2 weeks

**Question**: What is the most reliable and user-friendly flow for downloading and verifying models on-device?

**Why it matters**:
- Models are large (1-5 GB for quantized, 10+ GB for ternary 27B)
- Download failures are common (network, storage)
- Verification ensures integrity (hash, signature)
- User consent & transparency (Field Note 006)

**Hypotheses**:
- H1: Resumable downloads reduce failure rate by ≥50% vs non-resumable
- H2: Hash verification catches ≥99% of corrupted downloads
- H3: User-facing progress UI increases perceived trust

**Setup**:
- Implement: resumable HTTP downloads, SHA256 verification, progress UI
- Test: simulate network failures, storage pressure
- Measure: success rate, retry behavior, user perception (survey?)

**Prerequisites**: None (infrastructure work, not research PoC)

---

## Theme 7: Advanced Document Processing

### PoC-A1: Vision-Language Models for Document Q&A
**Status**: 🟡 Medium feasibility
**Estimated effort**: 3-4 weeks

**Question**: Does Qwen2.5-VL-3B (vision-language model) improve contract Q&A accuracy vs text-only Qwen2.5-1.5B, especially on tables and visual elements?

**Why it matters**:
- Contracts contain tables (pricing, schedules), signature blocks, diagrams
- Text extraction often loses table structure
- Qwen2.5-VL-3B: 3B parameters, 33K context, excels at charts/tables/layouts
- 7B version matches GPT-4o on document understanding

**Hypotheses**:
- H1: VLM improves on table-heavy questions by ≥10 points
- H2: VLM correctly identifies signature parties from visual blocks (>80% accuracy)
- H3: Latency remains <5 seconds per page on iPhone with 4-bit quantization

**Setup**:
- Need CUAD original PDFs (currently have text only)
- Quantize Qwen2.5-VL-3B to 4-bit (estimate: 2-3 GB)
- Create table-heavy question subset
- Compare: text-only Qwen vs VLM on PDF pages

**Prerequisites**:
- PDF rendering on iOS
- Qwen2.5-VL quantization and mobile runtime
- Table-extraction ground truth for CUAD

**References**: Qwen2.5-VL Technical Report (Mar 2025), arXiv:2502.13923

---

### PoC-A2: Semantic vs Fixed Chunking
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does semantic chunking (embedding-based boundaries) improve retrieval recall vs fixed-size chunking (current approach)?

**Why it matters**:
- 2026 study: semantic chunking achieves 24% Precision@1 vs 2-3% for fixed
- Your current approach: roughly fixed-size chunks (median 25 words)
- Semantic boundaries preserve meaning, avoid mid-sentence splits

**Hypotheses**:
- H1: Semantic chunking improves recall by ≥5 points (baseline: 61.4%)
- H2: Key-fact accuracy improves by ≥3 points (better context preservation)
- H3: Chunk count reduces by 10-20% (larger, more coherent chunks)

**Setup**:
- Implement semantic chunking: split when sentence embedding similarity drops
- Use sentence-transformers (e.g., all-MiniLM-L6-v2) for boundaries
- Compare: current fixed vs semantic on CUAD
- Measure: recall, key-fact rate, chunk statistics

**Decision rule**:
- If H1 and H2 hold: adopt semantic chunking
- Otherwise: current approach is sufficient

**Prerequisites**: None (standard technique)

**References**: Best Chunking Strategies for RAG (2026), multiple sources

---

### PoC-A3: Contextual Embeddings (Anthropic-Style)
**Status**: ❌ **Rejected** (PoC 011 - naive approach failed)
**Estimated effort**: 1 week (actual: 5 hours spot-check)

**Question**: Does adding document context to chunks before embedding (à la Anthropic's contextual embeddings) improve retrieval recall?

**Why it was rejected**:
- **Tested as PoC 011** (2026-10-19): Spot-check on 10 items showed 80% degradation
- **Root cause**: Naive text prepending dilutes embedding signal by ~30%
- **Key finding**: Standard embedding models treat metadata and content equally
- **Result**: -10 to -15% similarity score decrease vs. baseline
- **Lesson**: Anthropic likely fine-tuned their model; prepending doesn't work with standard models

**Quality gate failures**:
- ❌ Gate 1: Problem not validated (assumed small chunks = bad without data)
- ❌ Gate 2: Didn't research Anthropic's actual implementation (likely fine-tuned)
- ⚠️ Gate 3: Negative ROI (better alternatives exist: PoC 012 cross-encoder)

**Alternative approaches** (if revisiting):
- Fine-tune embedding model on CUAD with contextual prefixes (2-4 weeks effort)
- Use cross-encoder reranking with context (PoC 012 - proven approach)
- Inject context at query time instead of chunk time

**References**:
- Anthropic contextual embeddings (2026)
- PoC 011 write-up: [011-contextual-embeddings/](011-contextual-embeddings/)
- Quality gate review: [011-contextual-embeddings/QUALITY-GATE-REVIEW.md](011-contextual-embeddings/QUALITY-GATE-REVIEW.md)

---

### PoC-A4: Late Chunking for Better Context
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2 weeks

**Question**: Does late chunking (embed full document, then split) preserve more context vs chunking-then-embedding?

**Why it matters**:
- Late chunking: transformer processes full document before splitting
- Each chunk embedding carries full-document context
- May improve cross-chunk references (e.g., "as mentioned in Section 3")

**Hypotheses**:
- H1: Late chunking improves recall by ≥5 points on multi-section questions
- H2: Works best for documents <4000 tokens (fits in embedding model context)
- H3: Embedding time increases proportionally to document length

**Setup**:
- Implement late chunking: embed full CUAD contracts, extract chunk embeddings
- Compare: early chunking (current) vs late chunking
- Analyze: per-document-length performance

**Prerequisites**:
- Embedding model with ≥8K context (e.g., nomic-embed-text)
- May need to filter CUAD to shorter contracts for initial test

---

## Theme 8: Inference Optimization

### PoC-O1: Sparse Attention for Long Context
**Status**: 🟠 Low feasibility
**Estimated effort**: 4+ weeks

**Question**: Does sparse attention (FlashAttention, FlexPrefill) enable longer context (4K-8K) on mobile while maintaining speed?

**Why it matters**:
- Attention is 70-80% of decoding latency at 64K context
- Sparse attention: 1.36-1.69× speedup vs full attention (2026 research)
- Longer context = more retrieved chunks, better Q&A

**Hypotheses**:
- H1: Sparse attention enables 2× context (2048 → 4096) at same latency
- H2: Key-fact accuracy maintained (within 1 point)
- H3: Memory overhead ≤500 MB

**Prerequisites**:
- llama.cpp sparse attention support (experimental)
- Significant runtime modification

**Status rationale**: Low priority, infrastructure-heavy

---

### PoC-O2: KV Cache Compression (ChunkKV)
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2-3 weeks

**Question**: Does ChunkKV (semantic chunk-level KV cache compression) reduce memory while maintaining quality?

**Why it matters**:
- ChunkKV: 26% throughput improvement over token-level methods (2026)
- Treats semantic chunks as compression units (preserves structure)
- Could enable more chunks or longer context in same RAM budget

**Hypotheses**:
- H1: ChunkKV reduces KV cache memory by ≥30%
- H2: Key-fact accuracy maintained (within 1 point)
- H3: Prefill time unchanged or faster

**Prerequisites**:
- llama.cpp KV compression API
- Integration with chunking strategy

---

### PoC-O3: Cross-Encoder Reranking on Mobile
**Status**: 🟢 High feasibility
**Estimated effort**: 1-2 weeks

**Question**: Does lightweight cross-encoder reranking (e.g., mxbai-rerank-base-v1, 184M params) improve key-fact accuracy over hybrid retrieval alone?

**Why it matters**:
- Cross-encoder reranking is RAG best practice (2026)
- Your current: hybrid (0.7 semantic, 0.3 BM25) → 3 chunks → LLM
- Reranking: hybrid → top-10 → rerank → top-3 → LLM
- mxbai-rerank: 184M params, designed for edge/low-latency

**Hypotheses**:
- H1: Reranking improves key-fact rate by ≥3 points (baseline: 67.9%)
- H2: Retrieval recall improves by ≥2 points (better top-3 selection)
- H3: Reranking adds ≤200 ms latency on iPhone

**Setup**:
- Retrieve top-10 chunks with current hybrid method
- Rerank with cross-encoder (mxbai-rerank-base-v1 or ms-marco-TinyBERT-L-2)
- Select top-3 post-reranking
- Compare: hybrid-only vs hybrid+rerank

**Decision rule**:
- If H1 and H3 hold: adopt reranking
- If H1 holds but H3 >500ms: inconclusive (latency trade-off)

**Prerequisites**: Integrate cross-encoder model (ONNX or Core ML)

**References**: Top Rerankers for RAG (2026), multiple sources

---

### PoC-O4: Prompt Caching for Multi-Turn Q&A
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does caching KV state of retrieved chunks reduce latency for follow-up questions on the same document?

**Why it matters**:
- Multi-turn conversations reuse same retrieved chunks
- Prefill is latency bottleneck (PoC 009: 583 ms median)
- Cache chunk KV state → skip prefill on cache hit

**Hypotheses**:
- H1: Cached chunks reduce prefill time by ≥60% on follow-up questions
- H2: Cache hit rate ≥50% for multi-turn conversations (3+ turns)
- H3: Cache overhead ≤200 MB RAM for 100 cached chunks

**Setup**:
- Implement KV cache storage for chunks (keyed by chunk hash)
- Test on multi-turn Q&A (need to create or find dataset)
- Measure: prefill time reduction, cache hit rate, memory overhead

**Prerequisites**:
- llama.cpp/llama.swift KV cache export/import API
- Multi-turn conversation dataset (or synthetic)

**References**: PerCache (Predictive Hierarchical Cache for RAG, 2026), arXiv:2601.11553

---

## Theme 9: Mobile-Specific Optimizations

### PoC-MO1: SQLite-vec vs FAISS for Vector Search
**Status**: 🟢 Very high feasibility
**Estimated effort**: 3-5 days

**Question**: Does SQLite with sqlite-vec extension match FAISS performance for CUAD-scale vector indexes (<10k documents) on mobile?

**Why it matters**:
- SQLite is native on iOS/Android, zero dependencies
- sqlite-vec: vector search extension (2024+)
- FAISS: external binary, build complexity
- MobileRAG paper uses SQLite-vec

**Hypotheses**:
- H1: SQLite-vec search latency is within 2× FAISS for <10k vectors
- H2: SQLite index size is ≤1.5× FAISS size
- H3: SQLite eliminates FAISS build dependency

**Setup**:
- Index CUAD contracts (~10k chunks) in both SQLite-vec and FAISS
- Measure: search latency (top-3, top-10), index size, memory usage
- Test: exact search and approximate (HNSW/IVF)

**Decision rule**:
- If H1, H2, H3 hold: adopt SQLite-vec for simpler stack
- Otherwise: keep FAISS

**Prerequisites**: Integrate sqlite-vec with Swift

---

### PoC-MO2: Document Deduplication for Library Management
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does chunk-level deduplication reduce storage and indexing time for large document libraries?

**Why it matters**:
- Users may upload duplicate/similar documents
- MobDedup (2026): 45.9% processing time reduction, 48.6% storage savings on Android
- Blake2b hashing: low overhead for mobile
- Dedup at chunk level (not just file level)

**Hypotheses**:
- H1: Chunk deduplication reduces storage by ≥30% for realistic libraries
- H2: Indexing time reduces by ≥20% (skip duplicate chunks)
- H3: Memory/CPU overhead ≤5% (hashing cost)

**Setup**:
- Implement Blake2b fingerprinting per chunk
- Test on CUAD corpus (397 contracts, expect duplication in boilerplate)
- Measure: dedup ratio, storage savings, indexing time

**Decision rule**: If H1 or H2 holds, adopt deduplication

**References**: MobDedup paper (Aug 2026), published in Journal of Forensic Sciences

---

### PoC-MO3: Incremental Indexing for Real-Time Updates
**Status**: 🟡 Medium feasibility
**Estimated effort**: 2-3 weeks

**Question**: Does incremental indexing (index only changed chunks) enable real-time document updates vs full reindex?

**Why it matters**:
- Current: upload document → chunk → embed all → index all (slow for large docs)
- Incremental: detect changed chunks → re-embed only changes → update index
- Enables "edit and ask" UX for live documents

**Hypotheses**:
- H1: Incremental indexing is ≥5× faster than full reindex for <10% document changes
- H2: Index quality maintained (retrieval recall within 1 point)
- H3: Overhead ≤10% storage (tracking change metadata)

**Setup**:
- Implement: track chunk hashes, detect changes, partial re-embed
- Test: simulate document edits (add/remove/modify sections)
- Measure: reindex time, recall accuracy, storage overhead

**Prerequisites**: Chunk versioning/tracking system

---

### PoC-MO4: Thermal-Aware Batch Processing
**Status**: 🟢 High feasibility
**Estimated effort**: 1 week

**Question**: Does thermal-aware batching (pause when hot, resume when cool) improve throughput vs fixed-rate processing?

**Why it matters**:
- iPhone throttles at high thermal state (PoC 001 cooldown policy)
- Large libraries (100+ documents) take time to index
- Smart batching could maintain peak performance longer

**Hypotheses**:
- H1: Thermal-aware batching completes 100-doc indexing ≥20% faster than naive batching
- H2: Peak thermal state is lower (nominal vs elevated)
- H3: Battery usage is ≤10% higher (overhead of monitoring)

**Setup**:
- Implement: batch size adaptation based on thermal state
- Test: index 100 CUAD documents on iPhone
- Compare: fixed batches vs adaptive batches
- Measure: total time, thermal state distribution, battery

**Decision rule**: If H1 holds, adopt thermal-aware batching

**Prerequisites**: Your existing thermal monitoring (PoC 001)

---

## Recently Discovered (2026-10-19) — Needs Further Research

### Idea: Intel BITCOS Format
**Status**: ⏸️ Blocked (waiting for runtime support)

**Concept**: Intel's BITCOS compresses ternary models below 1.58-bit (down to 1.485-bit) by exploiting zero-weight density.

**Why interesting**: 18% CPU, 27% GPU throughput improvement over standard ternary

**Blocker**: No confirmed llama.cpp/MLX support yet (Sept 2026 paper)

**Next step**: Monitor llama.cpp issues/PRs for BITCOS integration

---

### Idea: Samsung LittleBit Extreme Quantization
**Status**: ⏸️ Blocked (quality concerns)

**Concept**: 0.1 bits per weight (31× compression, Llama2-13B in 0.9 GB)

**Why interesting**: Extreme memory savings

**Blocker**: Likely unacceptable accuracy loss for production use

**Next step**: Wait for quality benchmarks; may be useful for low-priority features

---

### Idea: ColPali Multimodal PDF Retrieval
**Status**: ⏸️ Blocked (waiting for mobile-optimized models)

**Concept**: Late-interaction retrieval over PDF pages as images (tables, diagrams, signatures)

**Why interesting**: Contracts have visual structure; text extraction loses information

**Blocker**: ColPali models too large for 6GB iPhones currently

**Next step**: Monitor for quantized/distilled ColPali releases

---

### Idea: SmartRAG Graph-Based Multi-Hop
**Status**: ⏸️ Blocked (RAM requirements)

**Concept**: 3-layer knowledge graph for multi-hop reasoning on 1.7B model

**Why interesting**: Matches 18× larger models on multi-hop benchmarks

**Blocker**: Requires 4-5.5 GB RAM during operation (tight on 6GB iPhones)

**Next step**: Test on 8GB+ devices first; may work for future iPhone models

---

### Idea: SmolVLM2 for Document Understanding
**Status**: 🟡 Medium feasibility (needs research)

**Concept**: Compact VLM for document/receipt reading, edge deployment

**Why interesting**: Purpose-built for resource-constrained environments, document-focused

**Next step**: Research model size, quantization options, benchmark on CUAD

**References**: Best Open-Source Vision Language Models of 2026

---

### Idea: PaliGemma 3B for Document VQA
**Status**: 🟡 Medium feasibility (needs research)

**Concept**: 3B vision-language model, 85.6% VQA-v2, fine-tunable

**Why interesting**: Smaller than Qwen2.5-VL-7B, task-specific fine-tuning possible

**Next step**: Quantize to 4-bit, test on contract tables/diagrams

**References**: Best Vision-Language Models 2026

---

### Idea: Context Compression (MLLM-Guided)
**Status**: 🟠 Low feasibility (research stage)

**Concept**: MLLM generates semantic attention maps, compress context by importance

**Why interesting**: Reduce wireless/RAM bandwidth for edge AI, preserve task-relevant info

**Blocker**: Requires MLLM infrastructure, bandwidth modeling

**Next step**: Monitor research; may apply to chunk selection (vs retrieval)

**References**: Wireless Context Engineering for Efficient Mobile Agentic AI (2026), arXiv:2602.07321

---

### Idea: GLM-OCR for Efficient Document Parsing
**Status**: 🟡 Medium feasibility (needs research)

**Concept**: 0.9B parameter OCR model, 1.86 PDF pages/sec, enterprise-grade

**Why interesting**: Parameter-efficient, fast, could replace heavy OCR stacks

**Next step**: Test on scanned contracts (if CUAD has scanned PDFs)

**References**: Technical Analysis of Modern Non-LLM OCR Engines (2026)

---

### Idea: SCAN Semantic Layout Analysis
**Status**: 🟡 Medium feasibility (needs implementation)

**Concept**: Coarse-grained semantic chunking using layout, +10.4 points RAG improvement

**Why interesting**: Direct RAG improvement, layout-aware (contracts have structure)

**Next step**: Research SCAN implementation, compare with current chunking

**References**: SCAN: Semantic Document Layout Analysis for Textual and Visual Retrieval-Augmented Generation, arXiv:2505.14381

---

## Dropped / Deprioritized Ideas

### Dropped: PageIndex Vectorless RAG
**Reason**: Multiple sequential LLM calls per query = too slow for mobile
**Evidence**: No published latency benchmarks; slower than vector retrieval

---

### Deprioritized: Speculative Decoding
**Reason**: Significant engineering effort; basic optimizations not exhausted yet
**Revisit when**: Q4/ternary quantization, RAG optimizations complete

---

### Deprioritized: Training Custom Embedding Models
**Reason**: Out of scope for edge lab (focus: inference, not training)
**Alternative**: Evaluate existing lightweight models (PoC-R5)

---

## How to Use This Document

**When planning a PoC**:
1. Check if idea already exists here
2. Review hypotheses, setup, prerequisites
3. Update status and estimates as research progresses
4. Move to active PoC folder when starting (poc/0XX-name/)

**When discovering new ideas**:
1. Add to "Recently Discovered" section
2. Research feasibility, prerequisites
3. Promote to main section or drop with rationale

**When completing a PoC**:
1. Link this entry to the PoC folder
2. Update status to "✅ Completed (PoC-XXX)"
3. Archive or remove from active list

---

**Maintained by**: Makata AI Edge Lab
**Contact**: Via GitHub Discussions (makata-edge-lab repo)
**License**: CC BY 4.0 (write-ups), Apache 2.0 (code)
