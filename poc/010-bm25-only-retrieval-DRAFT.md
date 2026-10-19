# PoC 010: BM25-only retrieval on keyword-rich contracts

| | |
|---|---|
| Status | Planned (registration draft) |
| Verdict | TBD |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet |
| Source idea | BM25 hybrid retrieval best practices (2026); MobileRAG paper (arXiv:2507.01079, Jul 2025) showing BM25 requires no embedding model for edge deployment |
| Registered | 2026-10-19 (this draft, before the first run) |

## Question

Can BM25-only retrieval on CUAD contracts match EmbeddingGemma hybrid recall while eliminating embedding compute entirely?

## Why it matters here

Xylo's retrieval pipeline uses hybrid scoring: 0.7 semantic (EmbeddingGemma-300M embeddings) and 0.3 keyword (BM25). EmbeddingGemma consumes approximately 600 MB RAM and requires embedding compute for all chunks at indexing time.

CUAD contracts have structured, keyword-rich queries: specific dates (Agreement Date, Expiration Date), jurisdictions (Governing Law), durations (Notice Period, Renewal Term, Warranty Duration), and party names. These queries may benefit more from exact keyword matching than semantic similarity.

[PoC 007](../007-embedding-retrieval-recall) measured hybrid retrieval recall at 61.4% with EmbeddingGemma and 35.2% with NLEmbedding on 1,325 CUAD items. The 26.2-point gap shows embedding quality matters. But the 0.3 BM25 component was never tested alone.

BM25-only retrieval would:
1. **Eliminate embedding model dependency**: save ~600 MB RAM (EmbeddingGemma-300M)
2. **Remove embedding compute**: zero embedding time at indexing and query time
3. **Simplify the stack**: no embedding runtime, no vector index, pure keyword search
4. **Enable offline operation**: BM25 requires no model weights, runs from document content alone

The tradeoff: loss of semantic understanding (synonyms, paraphrases, conceptual matches). For keyword-heavy categories, this may not matter. For others, it may be fatal.

This PoC measures whether CUAD's keyword-rich structure makes pure BM25 viable, and for which question categories.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items.

1. **H1** (Overall recall). BM25-only recall is within 5 points of EmbeddingGemma hybrid (baseline: 61.4%). If true, the semantic component adds little value for this dataset.

2. **H2** (Keyword-heavy categories). For keyword-heavy categories (Agreement Date, Expiration Date, Governing Law), BM25-only recall matches or exceeds hybrid recall. These queries contain exact phrases from the document.

3. **H3** (Compute elimination). BM25-only eliminates all embedding compute: 0 seconds embedding time at indexing and query, versus EmbeddingGemma's measured time from PoC 007.

4. **H4** (Key-fact accuracy). When BM25 retrieves the answer (recall is correct), Qwen2.5-1.5B's key-fact accuracy is within 2 points of hybrid retrieval. This tests whether BM25's chunks are sufficient context for the LLM.

Descriptive: per-category recall and key-fact rates, chunk rank distribution (do answers appear in top-1 vs top-3?), and qualitative error analysis on BM25's top failures.

## Method

**Host.** MacBook Pro (Mac16,8), Apple M4 Pro, 24 GB, macOS 26.5.1, on AC power. Same as PoC 009.

**Model (for key-fact measurement).** Qwen2.5-1.5B-Instruct, Q4_K_M, `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`, SHA-256 `1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370`, Apache-2.0. Same file as PoCs 003-009.

**Tooling.** llama.swift 2.8901.0 (llama.cpp b8901, Metal), Swift 6.3.3. Reuse PoC 006's `GGUFQA` harness.

**BM25 implementation.** Use PoC 007's existing BM25 scorer (same implementation as hybrid's keyword component). Parameters: k1 = 1.5, b = 0.75 (Okapi BM25 defaults). No reranking, no proximity boost, no page-diversity penalty (those were applied post-hybrid in PoC 007).

**Items.** PoC 007's 1,325 answerable items from 397 CUAD v1 contracts (CC BY 4.0). Same questions, same answer spans, same chunks.

**Conditions.** Two conditions, same items:

| Condition | Retrieval | Chunks in prompt |
|---|---|---|
| `eg-hybrid` (baseline) | EmbeddingGemma hybrid (0.7 semantic, 0.3 BM25) | Top-3 |
| `bm25-only` (test) | BM25 only (keyword scoring) | Top-3 |

Both conditions use PoC 007's committed chunk index and PoC 006's Qwen prompt format (ChatML, 3 chunks, document order, 2048 context).

**Measurements.**

1. **Recall** (primary): Share of items where the top-3 chunks cover at least half of CUAD's answer span. PoC 007's definition. This measures retrieval quality independent of the LLM.

2. **Key fact right**: On the 464 items in six parsable categories (Agreement Date, Expiration Date, Governing Law, Notice Period, Renewal Term, Warranty Duration), whether Qwen's answer contains the key fact from CUAD's span. PoC 006's scorer. This measures end-to-end Q&A accuracy.

3. **Embedding time**: Total CPU time spent embedding queries and chunks. Expected: 0 for BM25-only, non-zero for hybrid baseline (from PoC 007 logs).

4. **Per-category recall and key-fact rates**: Break down H2's hypothesis per category.

5. **Chunk rank distribution**: For items where BM25 retrieves the answer, at what rank (1, 2, or 3) does it appear? If answers are always rank-1, top-1 retrieval may suffice.

6. **Descriptive**: Answer-or-absent call (PoC 008's detector), unsupported numbers, per-contract statistics.

**Intervals.** 95% confidence intervals via contract-level bootstrap (10,000 resamples, seed 0), same as PoC 009.

## Decision rule

Written before the first run. The idea under test: replacing Xylo's hybrid retrieval with BM25-only for keyword-rich document types (contracts, legal, structured forms).

**Step 1 (viability).** If BM25-only recall is less than 5 points below hybrid recall (H1 fails by >5 points): **reject**, semantic component is necessary. Stop here.

**Step 2 (keyword categories).** If H1 holds, check H2: for at least 3 of the 6 keyword-heavy categories (Agreement Date, Expiration Date, Governing Law, Notice Period, Renewal Term, Warranty Duration), BM25-only recall is within 2 points of hybrid or exceeds it.

- If H2 holds for ≥3 categories: **adopt (conditional)**, recommend BM25-only for keyword-heavy document types. Hybrid remains default.
- If H2 holds for <3 categories: **inconclusive**, BM25 works for some categories but not others. May be useful for category-specific retrieval strategies.

**Step 3 (end-to-end quality).** If steps 1-2 pass, check H4: key-fact accuracy with BM25 is within 2 points of hybrid.

- If H4 holds: **adopt (conditional)**, BM25-only is viable for contracts.
- If H4 fails: **reject (trade-off)**, retrieval recall is acceptable but LLM answer quality degrades.

**Note on H3**: Embedding time elimination is assumed (BM25 has no embeddings). If BM25 implementation is slower than expected (e.g., >100ms per query), note as deviation but does not affect adopt/reject.

## Results

To be filled after run. Link raw files in `results/`.

Expected files:
- `bm25-only-recall.jsonl`: per-item recall (chunk coverage)
- `bm25-only-answers.jsonl`: Qwen outputs and key-fact scores
- `eg-hybrid-baseline.jsonl`: baseline recall from PoC 007 (or rerun)
- `comparison.txt`: recall differences, CIs, per-category breakdowns
- `timings.txt`: embedding time (should be 0 for BM25)

All numbers tagged MEASURED, OBSERVED, or INFERRED.

## Verdict

To be determined after run, against decision rule above.

## Deviations

None yet. Any post-registration changes will be dated and justified here.

## Limits

What this does not show:

1. **Answerable items only.** The PoC says how well BM25 retrieves when there is an answer, not what it does when the clause is absent. PoC 008's absence detection was only tested with hybrid retrieval.

2. **CUAD only, contracts only.** Results may not generalize to other document types (technical docs, emails, reports) where semantic matching is critical. CUAD contracts are unusually keyword-rich.

3. **Top-3 chunks only.** Does not test whether BM25 needs more chunks (top-5, top-10) to match hybrid recall. PoC 009 found 5 chunks distract Qwen, so top-3 is kept.

4. **No reranking.** The BM25 scoring is raw; no cross-encoder reranking is applied. Hybrid retrieval in PoC 007 also had no reranking, so this is a fair comparison.

5. **No proximity boost or page-diversity penalty.** PoC 007's hybrid retrieval applied these after combining semantic and keyword scores. For BM25-only, it's unclear whether these heuristics help or hurt. This PoC tests raw BM25.

6. **English only, legal domain.** CUAD is English-language US commercial contracts. BM25 performance on multilingual documents or other domains (scientific, creative, conversational) is not tested.

7. **Qwen2.5-1.5B only.** Key-fact accuracy is measured with Qwen. Other models (Gemma, FoundationModels) may behave differently with BM25-retrieved chunks.

8. **Host stage only.** This is a Mac benchmark. iPhone performance (indexing speed, query latency, thermal impact) is not measured. BM25's lack of embedding compute should make it faster and cooler on mobile, but this is not verified.

9. **Median chunk size is small.** PoC 007: median chunk is 25 words. BM25 on very small chunks may degrade (less keyword context). Results may differ with larger chunk sizes.

10. **No query expansion or stemming.** BM25 is run with exact query terms. Techniques like synonym expansion or stemming (which can improve BM25) are not tested.

## Reproduce

Requirements: Apple silicon Mac with macOS 26.4+, Xcode 26, Swift 6.3+, about 4 GB free memory.

Prerequisites: PoC 006, 007 folders (for harness, chunk index, baseline scores).

Commands from a clean checkout:

```bash
cd poc/010-bm25-only-retrieval
./prepare.sh    # extracts PoC 007 chunk index, prepares BM25 scorer
./run.sh        # runs BM25 retrieval, then Qwen Q&A
python3 compare.py  # compares BM25 vs hybrid baseline, outputs statistics
```

Expected runtime: ~30 minutes (retrieval is fast, Qwen inference on 1,325 items takes ~20-25 min per PoC 009).

## Replications

Hardware needed: Apple silicon Mac (for llama.swift Metal acceleration) or CUDA GPU with llama.cpp.

To replicate:
1. Clone the repo, check out the commit referenced in the registration.
2. Run commands above.
3. Submit `results/` folder via pull request to `replications/YYYY-MM-DD-device-name/`.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| TBD | Mac16,8 M4 Pro | Ralph Mattew Palomaria | TBD |

---

## Implementation Notes (for run)

**BM25 scoring details:**
- Use Okapi BM25: `score = IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (dl / avgdl)))`
- k1 = 1.5, b = 0.75 (standard)
- Term frequency (tf) counted in chunk text
- Document length (dl) is chunk word count, avgdl is mean chunk length across corpus
- IDF = log((N - df + 0.5) / (df + 0.5)) where N = total chunks, df = chunks containing term

**Retrieval flow:**
1. Tokenize query (lowercase, split on whitespace/punct)
2. For each chunk, compute BM25 score (sum over query terms)
3. Rank chunks by score (descending)
4. Return top-3

**Key-fact measurement:**
- Reuse PoC 006's `KeyFactScorer` exactly
- Parse CUAD answer spans for: dates (YYYY-MM-DD, month names), jurisdictions (state names, "State of X"), durations (N days/months/years)
- Check if Qwen's output contains the parsed fact (case-insensitive substring match)

**Baseline comparison:**
- PoC 007's `eg-hybrid` recall: 61.4% (MEASURED)
- Rerun hybrid retrieval to ensure fair comparison (same chunk index, same top-3 selection)
- Or: use PoC 007's committed recall scores if chunk index and top-k logic are identical

**Per-category breakdown:**
CUAD categories with parsable key facts (464 items total, from PoC 006):
- Agreement Date: 84 items
- Expiration Date: 61 items
- Governing Law: 93 items
- Notice Period To Terminate Renewal: 95 items
- Renewal Term: 91 items
- Warranty Duration: 40 items

Expected outcome for H2: Governing Law (state names) and dates should favor BM25 (exact keyword match). Notice Period and Renewal Term may favor hybrid (paraphrases like "30-day notice" vs "one month notice").

**Error analysis (if time permits):**
- Sample 20-30 items where BM25 fails recall but hybrid succeeds
- Categorize failures: (a) synonyms (BM25 misses paraphrase), (b) multi-word expressions, (c) context-dependent terms, (d) other
- Sample 10-20 items where BM25 succeeds but hybrid fails (if any)
- Categorize: (a) exact keyword present, (b) hybrid distracted by semantically similar but wrong chunk, (c) other

---

## Expected Outcome Prediction (pre-run)

Based on 2026 research (7.4% hybrid lift over either method alone, 24% semantic chunking improvement) and PoC 007's findings:

**Most likely outcome:** H1 fails (BM25 recall is 8-15 points below hybrid), verdict: **reject**. CUAD questions contain paraphrases and multi-word expressions that BM25 misses without semantic understanding.

**Optimistic outcome:** H1 holds (within 5 points), H2 holds for 4-5 categories, H4 holds. Verdict: **adopt (conditional)** for contracts and keyword-rich documents. Enables a simpler, faster, RAM-efficient retrieval path.

**Pessimistic outcome:** H1 fails badly (>15 points gap), H2 holds only for 1-2 categories. Verdict: **reject**, semantic component is critical even for structured documents.

**Surprise outcome:** BM25 exceeds hybrid on some categories (dates, jurisdictions). Would suggest hybrid's semantic component was over-weighted (0.7 vs 0.3) for this dataset. Follow-up: test weight tuning (0.5/0.5 or 0.3/0.7 BM25-heavy).

Post-run analysis will report which outcome occurred and why.
