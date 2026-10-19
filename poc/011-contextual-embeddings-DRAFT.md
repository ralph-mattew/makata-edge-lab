# PoC 011: Contextual embeddings for small chunks

| | |
|---|---|
| Status | Planned (registration draft) |
| Verdict | TBD |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet |
| Source idea | Anthropic contextual embeddings (2026 reports), showing 35% reduction in retrieval failure rate (5.7% → 3.7%); multiple 2026 RAG best practices guides |
| Registered | 2026-10-19 (this draft, before the first run) |

## Question

Does adding document context to chunks before embedding (à la Anthropic's contextual embeddings) improve retrieval recall on CUAD contracts, especially for small chunks?

## Why it matters here

[PoC 007](../007-embedding-retrieval-recall) found median chunk size is 25 words across CUAD contracts. These small chunks often lack sufficient context for semantic matching:
- A chunk containing only "30 days" may be a notice period, payment term, or warranty duration
- "State of Delaware" without surrounding text may refer to governing law, venue, or party domicile
- Cross-references like "as described in Section 3.2" are meaningless without the section context

Anthropic reported that **contextual embeddings**—adding document/section context to each chunk before embedding—reduced top-20 retrieval failure rate by **35%** (from 5.7% to 3.7%). The method is simple:

**Standard embedding:**
```
Chunk text: "30 days"
Embedding: embed("30 days")
```

**Contextual embedding:**
```
Document: "Software License Agreement between Acme Corp and Client Inc."
Section: "5.2 Termination"
Chunk text: "30 days"
Contextual text: "Document: Software License Agreement. Section: 5.2 Termination. Chunk: 30 days"
Embedding: embed(contextual_text)
```

The embedding model sees the full context, producing a representation that captures "30-day termination notice" rather than generic "30 days." At query time, the query is also contextualized with the document name (if known) or left plain (for cross-document search).

Xylo's chunks are small (median 25 words, PoC 007) and lack headers. Adding context could:
1. Improve semantic matching for ambiguous chunks
2. Reduce false-positive retrievals (semantically similar but contextually wrong)
3. Enable more precise chunk splitting (smaller chunks with less context loss)

The cost: longer text to embed (roughly 2-3× tokens per chunk), increasing embedding time by 20-50%. But embedding is a one-time indexing cost, and Xylo's EmbeddingGemma is fast.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items.

1. **H1** (Overall recall improvement). Contextual embeddings improve recall by at least 3 points over standard embeddings (baseline: 61.4% with EmbeddingGemma hybrid, PoC 007).

2. **H2** (Small chunk benefit). The improvement is largest for small chunks (<50 words). Chunks ≥50 words already have sufficient context and gain little.

3. **H3** (Embedding time cost). Embedding time increases by at most 50% (e.g., if standard takes 10s, contextual takes ≤15s). This is acceptable for a one-time indexing cost.

4. **H4** (Key-fact accuracy). With better retrieval, Qwen2.5-1.5B's key-fact accuracy improves by at least 2 points (baseline: 67.9% with 3 chunks, PoC 009).

Descriptive: per-category improvements, retrieval precision (fewer false positives), and qualitative analysis of which types of chunks benefit most (cross-references, ambiguous terms, entity names).

## Method

**Host.** MacBook Pro (Mac16,8), Apple M4 Pro, 24 GB, macOS 26.5.1, on AC power. Same as PoC 009.

**Embedding model.** EmbeddingGemma-300M, same as PoC 007. Reuse PoC 007's embedding pipeline (llama.cpp, Metal, batch processing).

**Model (for key-fact measurement).** Qwen2.5-1.5B-Instruct Q4_K_M, same file as PoCs 003-009.

**Tooling.** llama.swift 2.8901.0, Swift 6.3.3. Reuse PoC 006's `GGUFQA` harness and PoC 007's retrieval code.

**Items.** PoC 007's 1,325 answerable items from 397 CUAD v1 contracts (CC BY 4.0).

**Context construction.** For each chunk, prepend context in this format:

```
Format: "Document: {contract_title}. Section: {section_header}. Chunk: {chunk_text}"
```

Where:
- `{contract_title}`: CUAD file name without extension (e.g., "ACMESTANDARD_03_14_2018" → "ACME STANDARD 03-14-2018")
- `{section_header}`: Extracted section header if available (e.g., "5. TERMINATION"), or "Document body" if chunk is not in a labeled section
- `{chunk_text}`: Original chunk text (25-word median, PoC 007)

**Section extraction:** CUAD contracts are plain text. Identify section headers via heuristics:
- Lines starting with digits followed by period (e.g., "5. ", "12.3 ")
- All-caps lines (e.g., "TERMINATION AND RENEWAL")
- If no header found within 500 words before chunk, use "Document body"

**Fallback for missing context:** If section header extraction fails, use simpler format: `"Document: {contract_title}. Chunk: {chunk_text}"`

**Conditions.** Three conditions, same 1,325 items:

| Condition | Embedding method | Retrieval |
|---|---|---|
| `standard` (baseline) | Standard (plain chunk text) | Hybrid (0.7 semantic, 0.3 BM25), top-3 |
| `contextual-doc` | Contextual (doc title only) | Hybrid, top-3 |
| `contextual-full` (primary) | Contextual (doc + section) | Hybrid, top-3 |

All three use the same BM25 scores (BM25 operates on plain chunk text, not contextual). Only the semantic embeddings differ.

**Measurements.**

1. **Recall** (primary): Share of items where top-3 chunks cover ≥50% of CUAD's answer span. PoC 007's definition.

2. **Key fact right**: On 464 items with parsable key facts, whether Qwen's answer contains the fact. PoC 006's scorer.

3. **Embedding time**: Total CPU time to embed all chunks. Expected: `contextual-full` > `contextual-doc` > `standard`.

4. **Per-chunk-size recall**: Break down H2: recall for chunks <25 words (Q1), 25-50 words (Q2-Q3), >50 words (Q4). Expected: largest gain for smallest chunks.

5. **Retrieval precision** (exploratory): Of the top-3 retrieved chunks, how many are relevant (cover any part of CUAD's answer, not just ≥50%)? Higher precision = fewer false positives.

6. **Descriptive**: Per-category recall and key-fact rates, answer-or-absent detection, timing breakdowns.

**Intervals.** 95% confidence intervals via contract-level bootstrap (10,000 resamples, seed 0), same as PoC 009.

## Decision rule

Written before the first run. The idea under test: prepending document and section context to chunks before embedding, as Anthropic recommends.

**Step 1 (viability).** Compare `contextual-full` vs `standard` recall.

- If H1 holds (recall improves by ≥3 points): proceed to step 2.
- If recall improves by 1-2.9 points: **inconclusive**, gain exists but is small. Check if H2 holds (benefit concentrated in small chunks) to justify adoption.
- If recall improves by <1 point or degrades: **reject**, contextual embeddings add no value for this dataset.

**Step 2 (cost check).** If step 1 passes, check H3: embedding time increase is ≤50%.

- If H3 holds: proceed to step 3.
- If embedding time >2× standard: **reject (trade-off)**, cost is too high for indexing-time performance.

**Step 3 (end-to-end quality).** If steps 1-2 pass, check H4: key-fact accuracy improves by ≥2 points.

- If H4 holds: **adopt**, recommend contextual embeddings for Xylo.
- If H4 fails (recall improves but key-fact doesn't): **adopt (conditional)**, recommend for retrieval-only scenarios (e.g., search/browse UI), but verify with longer Qwen runs.

**Fallback decision:** If `contextual-full` fails but `contextual-doc` (doc title only) passes step 1 with ≥2 points and step 2, adopt the simpler `contextual-doc` variant (faster, no section extraction needed).

**Note on H2:** If H1 holds and per-chunk-size analysis shows improvement only for chunks <50 words, adopt selectively: use contextual embeddings for small chunks, standard for large chunks.

## Results

To be filled after run. Link raw files in `results/`.

Expected files:
- `standard-recall.jsonl`: baseline recall (standard embeddings)
- `contextual-doc-recall.jsonl`: recall with doc title context
- `contextual-full-recall.jsonl`: recall with doc + section context
- `contextual-full-answers.jsonl`: Qwen outputs and key-fact scores
- `comparison.txt`: recall differences, CIs, per-chunk-size breakdowns
- `timings.txt`: embedding time for each condition
- `chunk-context-map.jsonl`: chunk ID → extracted section header (for reproducibility)

All numbers tagged MEASURED, OBSERVED, or INFERRED.

## Verdict

To be determined after run, against decision rule above.

## Deviations

None yet. Any post-registration changes will be dated and justified here.

## Limits

What this does not show:

1. **Section extraction heuristics.** CUAD contracts are plain text with inconsistent formatting. Section header extraction may miss headers or mislabel chunks. A more robust parser (e.g., PDF layout analysis, DocTR) could improve context quality but is out of scope.

2. **Answerable items only.** The PoC tests retrieval when there is an answer. Behavior on absent clauses (PoC 008) is not measured with contextual embeddings.

3. **CUAD contracts only.** Results may not generalize to other document types (emails, reports, technical docs) where section structure differs or is absent.

4. **Top-3 chunks only.** Does not test whether contextual embeddings change the optimal chunk count (PoC 009's finding that 3 beats 5 was with standard embeddings).

5. **EmbeddingGemma only.** Other embedding models (NLEmbedding, nomic-embed-text, all-MiniLM) may behave differently with context. NLEmbedding's 22-point gap (PoC 007) could narrow with context, but is not tested here.

6. **Query not contextualized.** The query is plain (e.g., "What is the governing law?"). Contextualizing the query (e.g., "Document: ACME STANDARD. Question: What is the governing law?") could further improve matching, but is not tested. This is deliberate: users don't know the document title at query time for multi-document search.

7. **English only.** CUAD is English. Contextual embeddings on multilingual documents (Xylo's use case with Filipino) are not tested.

8. **Qwen2.5-1.5B only.** Key-fact accuracy is measured with Qwen. Other models may benefit more or less from better retrieval.

9. **Host stage only.** Mac benchmark. iPhone performance (embedding time, memory impact, thermal) is not measured.

10. **Single seed.** Qwen runs use seed=1 (PoC 009 setting). Seed variance (PoC 009: ±2 points) is not explored.

11. **No reranking.** Contextual embeddings are tested in isolation. Combining with cross-encoder reranking (future PoC) may yield further gains.

12. **Static context.** The context is fixed at indexing time. Dynamic context (e.g., user-provided document tags, query history) is not tested.

## Reproduce

Requirements: Apple silicon Mac with macOS 26.4+, Xcode 26, Swift 6.3+, about 4 GB free memory.

Prerequisites: PoC 006, 007 folders (for harness, chunk index, embedding model).

Commands from a clean checkout:

```bash
cd poc/011-contextual-embeddings
./extract-sections.sh  # parses CUAD contracts, extracts section headers
./prepare.sh           # builds contextual chunk variants, verifies against PoC 007 baseline
./embed.sh             # re-embeds all chunks with contextual variants (takes ~10-20 min)
./run.sh               # runs retrieval + Qwen Q&A for all three conditions
python3 compare.py     # compares recall, key-fact, timing across conditions
```

Expected runtime: ~60-90 minutes (embedding is the bottleneck; Qwen runs are reused from standard condition if embeddings-only change).

## Replications

Hardware needed: Apple silicon Mac (for EmbeddingGemma Metal acceleration) or CUDA GPU.

To replicate:
1. Clone the repo, check out the commit referenced in the registration.
2. Run commands above.
3. Submit `results/` folder via pull request to `replications/YYYY-MM-DD-device-name/`.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| TBD | Mac16,8 M4 Pro | Ralph Mattew Palomaria | TBD |

---

## Implementation Notes (for run)

**Section header extraction logic:**

```
For each chunk in a contract:
  1. Look backwards from chunk start position, up to 500 words
  2. Find the nearest line matching:
     - Pattern 1: /^\d+\./ (e.g., "5. ", "12.3 ")
     - Pattern 2: /^[A-Z\s]{4,}$/ (all-caps, at least 4 chars, e.g., "TERMINATION")
  3. If found, extract as section header (clean whitespace, title-case if needed)
  4. If not found, use "Document body"

Edge cases:
  - If multiple headers found, use the closest one
  - If header is >50 chars, truncate to first 50 chars (e.g., "GOVERNING LAW, DISPUTE RESOLUTION AND VENUE")
  - Preserve section numbers (e.g., "5.2 Termination" not just "Termination")
```

**Context format examples:**

Standard chunk:
```
"This Agreement shall be governed by the laws of the State of Delaware."
```

Contextual (doc only):
```
"Document: ACME STANDARD 03-14-2018. Chunk: This Agreement shall be governed by the laws of the State of Delaware."
```

Contextual (doc + section):
```
"Document: ACME STANDARD 03-14-2018. Section: 12. GOVERNING LAW. Chunk: This Agreement shall be governed by the laws of the State of Delaware."
```

**Embedding batching:** EmbeddingGemma processes chunks in batches (PoC 007 used batch_size=32). Contextual text is longer (2-3× tokens), so batch size may need adjustment to fit in GPU memory (24 GB on M4 Pro should be fine).

**Query handling:** Queries remain plain (no context). This tests whether contextual chunk embeddings alone improve matching. Future work: contextualize queries when document is known (single-document Q&A).

**Fallback verification:** Before the run, verify section extraction on a sample of 10 contracts manually. If <70% of chunks get correct section headers, consider using `contextual-doc` only (doc title, no section).

**Retrieval code change:** Minimal. PoC 007's `retrieve.py` takes chunk embeddings as input. Replace `chunk_embeddings.npy` with `chunk_embeddings_contextual.npy`, rerun retrieval, compare top-3 chunk IDs.

**Key-fact measurement:** Reuse PoC 006's `KeyFactScorer` exactly. Only the retrieved chunks change; Qwen prompt format and scoring logic remain identical.

**Timing measurement:** Use PoC 007's instrumentation. Record:
- Embedding time per chunk (average over all chunks)
- Total embedding time (sum)
- Ratio: contextual / standard (expected: 1.2-1.5×)

**Per-chunk-size analysis:**
- Compute chunk word count distribution (PoC 007: median 25, IQR 18-36)
- Split into quartiles: Q1 (<18 words), Q2 (18-25), Q3 (25-36), Q4 (>36)
- Compute recall per quartile for each condition
- Expected: largest gain in Q1 (smallest chunks), minimal gain in Q4

**Error analysis (if time permits):**
- Sample 20-30 items where `contextual-full` succeeds but `standard` fails
- Categorize: (a) ambiguous chunk gained context (e.g., "30 days" → "Termination: 30 days"), (b) cross-reference resolved (e.g., "Section 5" → "Section 5: Payment Terms"), (c) entity disambiguation (e.g., "Delaware" → "Governing Law: Delaware"), (d) other
- Sample 10-20 items where `contextual-full` fails but `standard` succeeds (if any)
- Categorize failures: (a) over-contextualization (embedding model confused by long text), (b) section mislabeled, (c) other

---

## Expected Outcome Prediction (pre-run)

Based on Anthropic's 35% failure reduction and 2026 RAG best practices:

**Most likely outcome:** H1 holds (recall improves by 3-5 points), H2 holds (benefit concentrated in small chunks), H3 holds (embedding time 1.3-1.4×), H4 holds (key-fact +2-3 points). Verdict: **adopt**, recommend contextual embeddings as default for Xylo.

**Optimistic outcome:** H1 exceeds expectation (recall +5-8 points), especially for cross-references and ambiguous chunks. Verdict: **adopt strongly**, major retrieval improvement for minimal cost.

**Pessimistic outcome:** H1 fails (recall +1-2 points or no gain). CUAD chunks may already have sufficient context from surrounding text overlap (30-word overlap in PoC 007). Verdict: **inconclusive** or **reject**, context adds little value here.

**Surprise outcome:** `contextual-doc` (doc title only) performs nearly as well as `contextual-full` (doc + section). Would suggest section headers add little beyond document identity. Verdict: **adopt `contextual-doc`**, simpler and faster (no section extraction needed).

Post-run analysis will report which outcome occurred and why. If adopted, this becomes the new baseline for future retrieval PoCs.
