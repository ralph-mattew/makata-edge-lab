# PoC 014: Clause-aware chunking vs page-based chunking

| | |
|---|---|
| Status | Planned (registration draft) |
| Verdict | TBD |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet |
| Source idea | The lab's own results: [PoC 013](../013-weight-tuning) (hard categories invariant to retrieval weight) and [PoC 009](../009-retrieval-depth-qwen) (more chunks don't help) point at chunk *boundaries*, not scoring, as the recall bottleneck. Structure/clause-aware chunking is standard RAG practice for structured documents. |
| Registered | 2026-10-20 (this draft, before the first run) |

## Question

Does splitting CUAD contracts on **clause/section boundaries** (instead of fixed
~500-word pages) raise recall@3 — and does the gain land on the **weight-invariant
hard categories** (Exclusivity ~11%, Non-Compete, Change Of Control) that
[PoC 013](../013-weight-tuning) showed retrieval scoring cannot move?

## Why it matters here

PoC 007 set the hybrid recall@3 baseline at **61.4%**. Two later results say the
remaining errors are *not* a scoring problem:

- **PoC 013:** sweeping the semantic/BM25 weight 0.1→0.9 moved overall recall, but
  **Exclusivity stayed at ~11% at every weight**, and Non-Compete / Change Of
  Control barely moved. The write-up itself noted the bottleneck "is chunking or
  question formulation, not retrieval scoring."
- **PoC 009:** retrieving 5 chunks instead of 3 did not help (EmbeddingGemma),
  so it isn't a depth problem either.

The most likely common cause: for these categories the **answer span is split
across page boundaries**, so no single ~500-word page chunk covers ≥50% of it, and
no amount of reweighting or extra depth can retrieve a chunk that doesn't cleanly
exist. CUAD contracts are numbered, sectioned legal text — chunking on those
boundaries should keep a clause intact in one retrievable chunk. This is the first
PoC to test the boundary hypothesis directly, rather than another scoring tweak.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items. Baseline is
the page-based hybrid recall@3 of 61.4% (PoC 007) at the 0.9/0.1 weight adopted in
PoC 013.

1. **H1 (overall).** Clause-aware chunking raises overall recall@3 by **≥3 points**
   over page-based chunking.

2. **H2 (the hard categories — the real test).** The gain concentrates on the
   weight-invariant categories: **Exclusivity, Non-Compete, Change Of Control each
   improve ≥5 points**, while already-easy categories (Insurance, Governing Law)
   move <2 points.

3. **H3 (mechanism — span integrity).** A larger fraction of gold answer spans are
   **fully contained in a single chunk** under clause-aware chunking than under
   page-based. This is the *why*: if H1 holds but H3 does not, the gain is not from
   better boundaries and the result is suspect.

4. **H4 (cost/feasibility on-device).** Clause-aware chunking does not materially
   increase chunk count / index size (≤1.3× page-based) or on-device chunking time;
   it is deterministic string processing, no model.

Descriptive: per-category recall deltas, chunk-size distribution (page vs clause),
examples of answers that move from split-across-pages to contained-in-one-clause.

## Method

**Host.** MacBook Pro (Mac16,8), M4 Pro, 24 GB, macOS 26.5.1, AC power (as PoC 009).

**Embedding / retrieval.** EmbeddingGemma-300M (mean pool, L2, ctx 2048), hybrid
0.9 semantic + 0.1 BM25, top-3 — identical to PoC 007/011 so only chunking changes.
Reuse the [PoC 011 pipeline](../011-contextual-embeddings/pipeline) embedding +
recall-scoring code (EmbeddingGemma via `llama-embedding`, bootstrap CIs).

**Items.** PoC 007's 1,325 answerable items from 397 CUAD v1 contracts (CC BY 4.0).

**Conditions** (same items; only the chunker differs):

| Condition | Chunker |
|---|---|
| `page` (baseline) | PoC 007's ~500-word page chunks (reuse `chunks.jsonl`) |
| `clause` (treatment) | split on clause/section boundaries (see below) |

**Clause-aware chunker (deterministic).**
- Split a contract at lines/markers that begin a clause: numbered headings
  (`^\d+(\.\d+)*[.)]`, e.g. "5.", "12.3"), lettered sub-items (`^\(([a-z]|[ivx]+)\)`),
  and ALL-CAPS section headings. Each clause (heading + body up to the next marker)
  is one chunk.
- **Size guards:** split a clause longer than a word cap (keep the cap near the page
  chunker's size so embedding context is comparable); merge a clause shorter than a
  floor into the next, so tiny headings aren't standalone chunks.
- Preserve the previous-chunk-tail `overlap` convention PoC 007 uses.
- No model, no network; byte-identical from the same zip (seeded, like PoC 007).

**Measurements.**
1. **Recall@3** (primary): top-3 cover ≥50% of the gold span (PoC 007's definition),
   overall and per category.
2. **Span integrity** (H3): fraction of gold spans fully contained in one chunk,
   page vs clause.
3. **Chunk stats** (H4): chunk count, size distribution, index size; chunking wall time.
4. Descriptive: per-category deltas; qualitative sample of answers that become
   single-chunk-contained under clause chunking.

**Intervals.** 95% CIs via contract-level bootstrap (10,000 resamples, seed 0), as PoC 009.

## Decision rule

Written before the first run.

- **Adopt** if **H1 holds (overall +≥3 points) AND H3 holds** (span integrity
  improves) — the gain must be explained by better boundaries, not noise — AND H4
  holds (no blow-up in chunk count/time).
- **Reject** if overall recall improves <1 point, or improves but H3 does not (gain
  not attributable to boundaries).
- **Inconclusive** otherwise (1–3 points, or mixed).
- **Report H2 prominently either way:** whether clause chunking fixes the specific
  weight-invariant categories is the headline, even if the overall number is modest.

## Results

To be filled after run. Raw files in `results/raw/`:
`chunks-page.jsonl`, `chunks-clause.jsonl`, `recall-page.jsonl`, `recall-clause.jsonl`,
`span-integrity.json`, `comparison.txt`. All numbers tagged MEASURED / OBSERVED / INFERRED.

## Verdict

To be determined after run, against the decision rule.

## Deviations

None yet. Dated changes recorded here after registration.

## Limits

1. **Heuristic boundaries.** CUAD formatting is inconsistent; the clause detector
   will mis-split some contracts. A learned/layout-aware splitter is out of scope.
2. **Answerable items only** — absence behaviour (PoC 008) not measured.
3. **CUAD contracts only** — may not transfer to other document types.
4. **EmbeddingGemma only**; **top-3 only**; **English only** — held fixed to isolate chunking.
5. **Retrieval recall, not end-to-end** — key-fact accuracy with Qwen is a follow-up;
   this PoC asks whether the right text is retrievable at all.
6. Interacts with PoC 011 (contextual retrieval) and PoC 012 (reranking); this PoC
   changes only the chunker, so the three can later be combined.

## Reproduce

Requirements: Apple-silicon Mac (macOS 26.4+, Swift 6.3+), llama.cpp; PoC 006/007 run
once (chunk index, items, EmbeddingGemma config).

```bash
cd poc/014-clause-aware-chunking
python3 chunk-clause.py        # build clause chunks from CUAD (deterministic)
./run.sh                       # embed page + clause chunks, score recall@3, span integrity
python3 compare.py             # overall + per-category deltas, CIs
```

## Replications

| Date | Device | Authors | Outcome |
|---|---|---|---|
| TBD | Mac16,8 M4 Pro | Ralph Mattew Palomaria | TBD |
