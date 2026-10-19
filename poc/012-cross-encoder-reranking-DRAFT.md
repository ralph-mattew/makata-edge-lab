# PoC 012: Cross-encoder reranking for mobile RAG

| | |
|---|---|
| Status | Planned (registration draft) |
| Verdict | TBD |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet |
| Source idea | Cross-encoder reranking as RAG best practice (2026); mxbai-rerank-base-v1 (184M params, Mixedbread AI) for edge deployment; 2026 reranking guides showing 13× speedup and accuracy gains |
| Registered | 2026-10-19 (this draft, before the first run) |

## Question

Does lightweight cross-encoder reranking (mxbai-rerank-base-v1, 184M params) improve key-fact accuracy and retrieval quality over hybrid retrieval alone on CUAD contracts, while keeping latency acceptable for iPhone?

## Why it matters here

Xylo's current retrieval pipeline:
1. **Hybrid retrieval**: 0.7 semantic (EmbeddingGemma embeddings) + 0.3 BM25 keyword
2. **Select top-3 chunks** directly
3. **Feed to Qwen2.5-1.5B** for Q&A

[PoC 007](../007-embedding-retrieval-recall) found recall at 61.4% with EmbeddingGemma hybrid. [PoC 009](../009-retrieval-depth-qwen) found key-fact accuracy at 67.9% with 3 chunks. But the retrieval→LLM pipeline has a gap: hybrid retrieval ranks chunks by embedding+BM25 scores without seeing the query-chunk interaction.

**Cross-encoder reranking** is the 2026 RAG best practice: after hybrid retrieval, a small cross-encoder model scores each (query, chunk) pair directly, producing a more accurate ranking. The flow becomes:

1. Hybrid retrieval → **top-10** chunks (recall: more candidates)
2. Cross-encoder reranks → **select best 3** of the 10
3. Feed to Qwen2.5-1.5B for Q&A

Cross-encoders are more accurate than bi-encoders (embeddings) because they see both query and chunk together, but they're slower (can't pre-compute). The solution: lightweight cross-encoders designed for mobile:

- **mxbai-rerank-base-v1**: 184M params, designed for edge/minimal latency (Mixedbread AI)
- **ms-marco-TinyBERT-L-2**: 4M params, ultra-fast CPU scoring (Microsoft)
- **BGE-reranker-base**: 278M params, popular default (Beijing Academy of AI)

2026 research shows reranking can reduce search time from 12.57s to 0.96s (13× speedup) by improving precision, and improve retrieval accuracy by 5-15 points on domain-specific tasks.

For Xylo, reranking could:
1. **Improve top-3 selection**: retrieve 10 candidates (higher recall), rerank to best 3 (higher precision)
2. **Reduce false positives**: cross-encoder eliminates semantically similar but contextually wrong chunks
3. **Enable iPhone deployment**: mxbai-rerank-base-v1 (184M) is 3× smaller than EmbeddingGemma (300M), runs via ONNX or Core ML

The tradeoff: added latency (cross-encoder must score 10 chunks per query). If reranking adds >500ms on iPhone, it may not be worth it for interactive Q&A.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items.

1. **H1** (Key-fact accuracy improvement). Reranking improves key-fact rate by at least 3 points over hybrid-only (baseline: 67.9% with 3 chunks, PoC 009).

2. **H2** (Retrieval precision). Reranking improves retrieval recall by at least 2 points (baseline: 61.4%). By selecting the best 3 of 10 candidates, more items get the answer in their top-3.

3. **H3** (Latency on host). Reranking adds at most 200ms per query on Mac M4 Pro (acceptable for batched indexing and prototyping).

4. **H4** (Latency on iPhone). Reranking adds at most 500ms per query on iPhone 15 Pro (acceptable for interactive Q&A, given Qwen's median total time is ~1 second per PoC 009).

5. **H5** (Model size feasibility). mxbai-rerank-base-v1 (184M params) fits in <500 MB RAM when quantized to FP16 or INT8, leaving room for EmbeddingGemma (600 MB) and Qwen (1 GB) in Xylo's 6 GB budget.

Descriptive: per-category improvements, reranking score distribution (how different are cross-encoder scores from hybrid scores?), error analysis (which chunks get promoted/demoted).

## Method

**Host.** MacBook Pro (Mac16,8), Apple M4 Pro, 24 GB, macOS 26.5.1, on AC power. Same as PoC 009.

**Device (for H4).** iPhone 15 Pro, iOS 26.1, 8 GB RAM (or closest available), on Wi-Fi, airplane mode for runs.

**Chat model.** Qwen2.5-1.5B-Instruct Q4_K_M, same file as PoCs 003-009.

**Embedding model.** EmbeddingGemma-300M, same as PoC 007.

**Reranker models.** Three candidates to test:

| Model | Parameters | Size (FP32) | Est. size (FP16) | Target deployment |
|-------|-----------|-------------|------------------|-------------------|
| **mxbai-rerank-base-v1** | 184M | ~736 MB | ~368 MB | Primary, iPhone |
| **ms-marco-TinyBERT-L-2** | 4M | ~16 MB | ~8 MB | Fallback, ultra-fast |
| **BGE-reranker-base** | 278M | ~1.1 GB | ~550 MB | Comparison, accuracy |

All models Apache 2.0 or MIT license. Download from Hugging Face, convert to ONNX or Core ML for iOS.

**Tooling.** llama.swift 2.8901.0 for Qwen; ONNX Runtime Mobile or Core ML for rerankers; Swift 6.3.3.

**Items.** PoC 007's 1,325 answerable items from 397 CUAD v1 contracts (CC BY 4.0).

**Conditions.** Four conditions on same items:

| Condition | Retrieval | Reranking | Chunks to LLM |
|---|---|---|---|
| `hybrid-k3` (baseline) | Hybrid top-3 | None | Top-3 from hybrid |
| `rerank-mxbai` (primary) | Hybrid top-10 | mxbai-rerank-base-v1 → top-3 | Reranked top-3 |
| `rerank-tiny` (fallback) | Hybrid top-10 | TinyBERT → top-3 | Reranked top-3 |
| `rerank-bge` (accuracy) | Hybrid top-10 | BGE-reranker-base → top-3 | Reranked top-3 |

All conditions use PoC 007's hybrid retrieval (0.7 semantic, 0.3 BM25) and PoC 006's Qwen prompt (ChatML, 3 chunks, 2048 context).

**Reranking procedure:**
1. Hybrid retrieval produces top-10 chunks with their scores
2. For each (query, chunk) pair, cross-encoder outputs a relevance score (0-1 or logit)
3. Rank the 10 chunks by cross-encoder score (descending)
4. Select top-3 reranked chunks
5. Feed to Qwen in reranked order (highest-scoring chunk first)

**Measurements.**

1. **Key fact right** (primary): On 464 items with parsable facts, whether Qwen's answer contains the key fact. PoC 006's scorer. This is the end-to-end success metric.

2. **Recall** (secondary): Share of items where the final top-3 chunks cover ≥50% of CUAD's answer span. Expected to improve vs hybrid-only top-3, because reranking selects from 10 candidates.

3. **Reranking latency (host)**: Time to score 10 chunks per query on Mac M4 Pro. Measure: median, p95, max across 1,325 queries. Separate timing for each reranker model.

4. **Reranking latency (iPhone)**: Time to score 10 chunks per query on iPhone 15 Pro. Test on sample of 100 queries (full 1,325-item run on iPhone is too slow). Measure per-model.

5. **Model memory footprint**: RSS increase when loading reranker model (FP16 quantization). Verify ≤500 MB for mxbai, ≤50 MB for TinyBERT.

6. **Score distribution**: For items where reranking changes the top-3, how much do cross-encoder scores differ from hybrid scores? Correlation between hybrid rank and reranked rank.

7. **Descriptive**: Per-category key-fact rates, answer-or-absent detection, qualitative analysis of promoted/demoted chunks.

**Intervals.** 95% confidence intervals via contract-level bootstrap (10,000 resamples, seed 0), same as PoC 009.

## Decision rule

Written before the first run. The idea under test: adding cross-encoder reranking to Xylo's retrieval pipeline for iPhone deployment.

**Step 1 (host viability).** Compare `rerank-mxbai` vs `hybrid-k3` on Mac.

- If H1 holds (key-fact accuracy +≥3 points): proceed to step 2.
- If key-fact improves by 1-2.9 points: **inconclusive**, small gain. Check if H2 holds (recall +≥2) and H3 holds (latency ≤200ms) to justify.
- If key-fact improves by <1 point: **reject**, reranking adds no value on host.

**Step 2 (latency check, host).** If step 1 passes, check H3: reranking latency ≤200ms per query on Mac.

- If H3 holds: proceed to step 3.
- If latency 200-500ms: **inconclusive**, acceptable for batched use but not interactive.
- If latency >500ms: **reject**, too slow even on Mac.

**Step 3 (iPhone latency).** If steps 1-2 pass, test `rerank-mxbai` on iPhone (100-item sample).

- If H4 holds (latency ≤500ms): proceed to step 4.
- If latency 500-1000ms: **adopt (conditional)**, recommend for background indexing only, not interactive Q&A.
- If latency >1000ms: **reject**, too slow for iPhone.

**Step 4 (memory check).** If step 3 passes, verify H5: reranker model ≤500 MB RAM.

- If H5 holds: **adopt**, recommend mxbai-rerank-base-v1 for Xylo.
- If H5 fails (>500 MB): fall back to TinyBERT (4M params, ~50 MB). If TinyBERT also improves key-fact (check `rerank-tiny` results), **adopt TinyBERT**. Otherwise, **reject**, no viable lightweight reranker.

**Accuracy hierarchy:** If all three rerankers pass H1 (≥3 points improvement), choose based on latency:
- If mxbai ≤500ms on iPhone: adopt mxbai (best accuracy-latency balance)
- If TinyBERT ≤200ms and mxbai >500ms: adopt TinyBERT (ultra-fast, acceptable accuracy)
- If BGE has highest accuracy but >1s latency: reject for iPhone, but note for Mac-only use cases

## Results

To be filled after run. Link raw files in `results/`.

Expected files:
- `hybrid-k3-baseline.jsonl`: baseline key-fact scores (from PoC 009 or rerun)
- `rerank-mxbai-answers.jsonl`: Qwen outputs with mxbai reranking
- `rerank-tiny-answers.jsonl`: Qwen outputs with TinyBERT reranking
- `rerank-bge-answers.jsonl`: Qwen outputs with BGE reranking
- `rerank-latency-host.txt`: per-query latency on Mac M4 Pro
- `rerank-latency-iphone.txt`: per-query latency on iPhone 15 Pro (100-item sample)
- `memory-footprint.txt`: RSS before/after loading each reranker
- `score-distribution.jsonl`: hybrid scores vs cross-encoder scores per chunk
- `comparison.txt`: key-fact differences, CIs, per-category breakdowns

All numbers tagged MEASURED, OBSERVED, or INFERRED.

## Verdict

To be determined after run, against decision rule above.

## Deviations

None yet. Any post-registration changes will be dated and justified here.

## Limits

What this does not show:

1. **iPhone performance is sampled.** Only 100 of 1,325 queries are tested on iPhone due to time constraints. Full-scale iPhone run (1,325 items) would take hours. The 100-item sample may not capture p95/max latency accurately.

2. **Answerable items only.** The PoC tests reranking when there is an answer. Behavior on absent clauses (PoC 008) is not measured.

3. **CUAD contracts only.** Results may not generalize to other document types where query-chunk interaction patterns differ.

4. **Top-10 retrieval, top-3 selection.** The 10→3 ratio is chosen based on 2026 RAG best practices. Other ratios (20→5, 10→5) are not tested.

5. **Single reranking stage.** Multi-stage reranking (e.g., TinyBERT for fast filtering 100→10, then mxbai for final 10→3) is not tested.

6. **Reranker models are off-the-shelf.** No fine-tuning on CUAD or legal domain. Domain-specific rerankers could perform better but require training.

7. **Qwen2.5-1.5B only.** Key-fact accuracy is measured with Qwen. Other models (Gemma, FoundationModels) may benefit more or less from better top-3 selection.

8. **No query expansion.** The query is plain. Query expansion (e.g., adding synonyms, entity variants) could interact with reranking but is not tested.

9. **Reranked chunks in score order.** Chunks are fed to Qwen in reranked order (highest-scoring first). PoC 007 fed chunks in document order. The effect of chunk ordering on Qwen is not isolated.

10. **EmbeddingGemma retrieval only.** NLEmbedding fallback (PoC 007: 35.2% recall) is not tested with reranking. Reranking could narrow the gap, but this is unknown.

11. **Single seed.** Qwen runs use seed=1. Seed variance (PoC 009: ±2 points) is not explored.

12. **FP16 quantization assumed.** Reranker models are quantized to FP16 for iPhone. INT8 or INT4 quantization could reduce memory and latency further but may hurt accuracy. Not tested.

13. **Core ML vs ONNX not compared.** The PoC will use whichever runtime is easier to integrate (likely ONNX Runtime Mobile). Core ML may be faster on iPhone but requires conversion.

14. **No thermal/battery measurement.** Reranking adds compute per query. Impact on thermal state and battery life is not measured (focus is latency and accuracy only).

## Reproduce

Requirements:
- **Host**: Apple silicon Mac with macOS 26.4+, Xcode 26, Swift 6.3+, about 8 GB free memory.
- **Device (optional)**: iPhone 15 Pro or later with iOS 26+.

Prerequisites: PoC 006, 007 folders (for harness, chunk index, embedding model).

Commands from a clean checkout:

```bash
cd poc/012-cross-encoder-reranking

# Prepare reranker models
./download-models.sh  # downloads mxbai, TinyBERT, BGE from Hugging Face
./convert-onnx.sh     # converts to ONNX format for iOS deployment

# Host runs (Mac)
./run-baseline.sh     # hybrid-k3 baseline (or reuse PoC 009 results)
./run-rerank.sh mxbai # rerank with mxbai-rerank-base-v1
./run-rerank.sh tiny  # rerank with TinyBERT-L-2
./run-rerank.sh bge   # rerank with BGE-reranker-base

# iPhone runs (100-item sample)
./run-iphone.sh mxbai 100  # requires iPhone connected, Xcode
./run-iphone.sh tiny 100

# Analysis
python3 compare.py    # compares key-fact, recall, latency across conditions
python3 analyze-scores.py  # score distribution, correlation analysis
```

Expected runtime:
- Host: ~45-60 minutes (reranking adds ~10-15 min per condition)
- iPhone: ~30-40 minutes per model (100 items)

## Replications

Hardware needed:
- Apple silicon Mac (for llama.swift, ONNX Runtime)
- iPhone 15 Pro or later (for H4 measurement)

To replicate:
1. Clone the repo, check out the commit referenced in the registration.
2. Run commands above.
3. Submit `results/` folder via pull request to `replications/YYYY-MM-DD-device-name/`.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| TBD | Mac16,8 M4 Pro | Ralph Mattew Palomaria | TBD |
| TBD | iPhone 15 Pro | Ralph Mattew Palomaria | TBD |

---

## Implementation Notes (for run)

**ONNX conversion:**

```bash
# From Hugging Face Transformers to ONNX
python -m optimum.exporters.onnx \
  --model mixedbread-ai/mxbai-rerank-base-v1 \
  --task text-classification \
  mxbai-rerank-onnx/

# Quantize to FP16 for iOS
python -m onnxruntime.quantization.quantize \
  --input mxbai-rerank-onnx/model.onnx \
  --output mxbai-rerank-onnx/model-fp16.onnx \
  --fp16
```

**Swift integration (ONNX Runtime Mobile):**

```swift
import onnxruntime_objc

let model = try ORTSession(modelPath: "mxbai-rerank-fp16.onnx")
let tokenizer = /* BPE tokenizer for mxbai */

func rerank(query: String, chunks: [String]) -> [ScoredChunk] {
    var scored: [(chunk: String, score: Float)] = []

    for chunk in chunks {
        let input = "\(query) [SEP] \(chunk)"  // Cross-encoder format
        let tokens = tokenizer.encode(input)
        let inputTensor = ORTValue(tensorData: tokens, shape: [1, tokens.count])

        let outputs = try model.run(withInputs: ["input_ids": inputTensor])
        let logits = outputs["logits"]!.tensorData() as! [Float]
        let score = sigmoid(logits[0])  // or softmax if multi-class

        scored.append((chunk, score))
    }

    return scored.sorted { $0.score > $1.score }
}
```

**Latency measurement:**

```swift
let start = CFAbsoluteTimeGetCurrent()
let reranked = rerank(query: query, chunks: top10Chunks)
let elapsed = (CFAbsoluteTimeGetCurrent() - start) * 1000  // ms
```

Measure per-query, aggregate: median, p95, max.

**Memory footprint:**

```swift
let memBefore = os_proc_available_memory()
let model = try ORTSession(modelPath: "mxbai-rerank-fp16.onnx")
let memAfter = os_proc_available_memory()
let footprint = memBefore - memAfter  // bytes

print("Model footprint: \(footprint / 1024 / 1024) MB")
```

Expected: mxbai ~350-400 MB (FP16), TinyBERT ~10-20 MB, BGE ~500-600 MB.

**Score analysis:**

For each query where reranking changes top-3:
- Record hybrid rank of each chunk (1-10)
- Record cross-encoder score (0-1)
- Compute Spearman correlation between hybrid rank and cross-encoder score
- Expected: moderate correlation (0.4-0.6), not perfect (reranking adds new information)

Categorize changes:
- Promoted chunks: in top-10 but not top-3 hybrid → promoted to top-3 reranked
- Demoted chunks: in top-3 hybrid → dropped from top-3 reranked

Qualitative analysis (sample 20-30 changes):
- Why was chunk promoted? (query-chunk interaction, keyword matching, semantic coherence)
- Why was chunk demoted? (semantically similar but contextually wrong, out-of-context snippet)

**Per-category measurement:**

CUAD categories (464 items with key facts, from PoC 006):
- Agreement Date, Expiration Date, Governing Law, Notice Period, Renewal Term, Warranty Duration

Compute key-fact rate per category for each condition. Expected: date/jurisdiction categories benefit most (cross-encoder disambiguates date contexts).

**iPhone sample selection (100 items):**

Stratified sample to match full distribution:
- 6 categories × ~15-20 items each
- Mix of easy (answer in top-1 hybrid) and hard (answer in top-4 to top-10) items
- Ensures representative latency and accuracy measurement

---

## Expected Outcome Prediction (pre-run)

Based on 2026 reranking research and RAG best practices:

**Most likely outcome:** H1 holds (key-fact +3-5 points), H2 holds (recall +2-4 points), H3 holds (Mac latency ~100-150ms), H4 conditional (iPhone latency ~400-600ms). Verdict: **adopt mxbai-rerank-base-v1**, recommend for Xylo with latency caveat. Enable as user preference (rerank on/off).

**Optimistic outcome:** H1 exceeds expectation (key-fact +5-8 points), H4 holds strongly (iPhone <300ms), H5 holds. Verdict: **adopt strongly**, reranking is a major win for mobile RAG.

**Pessimistic outcome:** H1 fails (key-fact +1-2 points), or H1 holds but H4 fails (iPhone >1000ms). Verdict: **reject** for iPhone, **adopt (conditional)** for Mac-only use cases.

**Fallback outcome:** mxbai too slow on iPhone, but TinyBERT passes all steps with smaller gain (key-fact +2-3 points, latency <200ms). Verdict: **adopt TinyBERT**, prioritize speed over marginal accuracy.

Post-run analysis will report which outcome occurred. If adopted, reranking becomes part of the default pipeline; future PoCs test combinations (e.g., contextual embeddings + reranking).
