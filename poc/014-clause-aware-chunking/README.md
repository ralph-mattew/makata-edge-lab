# PoC 014: Clause-aware chunking vs page-based chunking

| | |
|---|---|
| Status | Concluded — full corpus (397 contracts, 1,325 items) |
| Verdict | **Inconclusive, leaning reject.** Clause chunking gave +2.5 pts overall (below the +3 adopt bar, CIs overlap), did **not** move the hard categories (H2 refuted), and **reduced** span-integrity (H3 refuted) — so the small gain is not from the registered mechanism. See Verdict. |
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

Full corpus: 397 contracts, 1,325 items, hybrid 0.9/0.1, top-3. Raw in `results/`
(`recall-page.json`, `recall-clause.json`, `comparison.txt`); embeddings git-ignored.

**Recall@3 (MEASURED, 1,325 items).**

| Condition | chunks | recall@3 | 95% CI | span-integrity |
|---|---|---|---|---|
| `page` (baseline) | 79,037 | **61.8%** | 59.3–64.4 | 95.8% |
| `clause` (treatment) | 46,848 (0.59×) | **64.3%** | 61.5–67.1 | 83.5% |
| Δ | — | **+2.5** | (CIs overlap) | **−12.4** |

**Harness validation (MEASURED):** `page` = 61.8%, with PoC 007's 61.4% inside the CI →
pipeline reproduces the baseline; deltas are trustworthy as deltas.

**Per-category recall Δ (MEASURED):** the hard, weight-invariant targets barely moved.

| Category | page | clause | Δ | class |
|---|---|---|---|---|
| Agreement Date | 29% | 40% | +11 | |
| Termination For Convenience | 67% | 76% | +9 | |
| Notice Period To Terminate Renewal | 84% | 91% | +7 | |
| Warranty Duration | 47.9% | 54.9% | +7 | |
| Governing Law | 91% | 94% | +3 | easy |
| **Non-Compete** | 25% | 29% | **+4** | HARD |
| **Exclusivity** | 7% | 9% | **+2** | HARD |
| **Change Of Control** | 67% | 67% | **+0** | HARD |
| Insurance | 84% | 82% | −2 | easy |
| Cap On Liability | 51% | 45% | −6 | |

**Observations.**
- **OBSERVED:** overall +2.5 pts, but the 95% CIs overlap (59.3–64.4 vs 61.5–67.1) —
  not a decisive overall gain.
- **OBSERVED (H2 refuted):** the three weight-invariant hard categories moved +4 / +2 / 0.
  None reached the pre-registered +5. **Exclusivity is still 9%.** Clause boundaries are
  *not* the primary limiter for these categories.
- **OBSERVED (H3 refuted):** page chunks already contained the gold span in a single chunk
  **95.8%** of the time — there was almost no headroom. Clause chunking *reduced* span-
  integrity to 83.5% (merging/splitting occasionally splits a gold span across clause
  boundaries), yet overall recall still rose slightly. **INFERRED:** the small gain comes
  from more coherent retrieval *units* embedding better, **not** from the registered
  span-containment mechanism — so even the +2.5 is not attributable to H3.
- **OBSERVED:** clause produces **fewer** chunks (46,848 vs 79,037, 0.59×) — smaller
  index, satisfying H4's cost guard, but that is moot given H1/H2/H3.

## Verdict

**Inconclusive, leaning reject** — against the pre-registered decision rule.

- **H1 (overall +≥3):** NO (+2.5, CIs overlap).
- **H2 (hard categories +≥5 each):** NO (+4 / +2 / 0). This is the headline: **the hard-
  category bottleneck is not chunk boundaries.**
- **H3 (span-integrity improves):** NO — it *fell* 12.4 pts; page was already at 95.8%.
- Decision rule: **adopt requires H1 AND H3** → both fail → **do not adopt.** Overall
  improves >1 pt, so not a clean reject → **inconclusive**, but the mechanism is refuted.

**What this buys the lab.** PoC 013 said the hard categories are invariant to retrieval
*scoring*; PoC 014 now shows they're largely invariant to chunk *boundaries* too (and that
page chunking already has 95.8% span-integrity, so splitting was never the real problem).
That sharpens the remaining suspect to the **query side** — [PoC 015](../015-query-formulation)
(the raw CUAD category question retrieving the wrong clause) — and to **cross-reference
resolution** (see Deviations / related work). Clause chunking is retained as a cheaper
index (0.59× chunks) but not adopted as a recall win.

**Related work (found via the lab's own scan, 2026-10-20):** *StrucChunk: Structure-Aware
Retrieval for Legal Document RAG* (arXiv; github.com/SinghSuryaDeep/legal-rag-strucchunk-1)
treats a contract as a DAG of provisions, preserves clause boundaries, **and resolves
cross-references before embedding**, combining BM25 + BGE-M3 via Reciprocal Rank Fusion.
It reports gains on CrPC/CPC/GDPR/NitiBench/LegalBench-RAG (**not** CUAD, **not**
EmbeddingGemma, Recall@**5** not @3). Our result suggests the *boundary-preservation* half
(what PoC 014 tested) is not the lever on CUAD; its *cross-reference-resolution* half is the
untested, more promising follow-up (see Deviations).

## Deviations

- **2026-10-20 (the run):** Clause boundaries detected as the **union of line-start
  heuristics and inline token markers** (numbered/lettered/ALL-CAPS/"Section N"), because
  CUAD's extracted text often lacks newlines (some contracts <1% newline density) and
  line-only detection collapsed to the size cap. Size guards: merge clauses <15 words,
  split >200 words. Embedding server raised to `-b 16384` and inputs truncated to ~1200
  words (EmbeddingGemma's 2048-tok ctx) after over-length inputs caused `llama-server` 500s.
- **Follow-up logged (not run):** *cross-reference resolution* — append the text of a
  referenced clause ("as described in Section 3.2") to a chunk before embedding. This is
  the StrucChunk half PoC 014 did **not** test, and it targets a distinct failure mode
  (small chunks that reference content elsewhere) rather than boundary placement. Candidate
  for a future PoC; composes with PoC 015.

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
python3 chunk-clause.py                       # build page + clause chunk sets (deterministic)
# embedding server (note -b 16384: batch token-sum headroom; inputs capped ~1200 words):
llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
python3 embed.py --queries                   --out results/raw/emb-queries.jsonl
python3 embed.py --chunks results/raw/chunks-page.jsonl   --out results/raw/emb-page.jsonl
python3 embed.py --chunks results/raw/chunks-clause.jsonl --out results/raw/emb-clause.jsonl
python3 score.py --cond page                 # validate ~61.4% first
python3 score.py --cond clause
python3 compare.py                            # overall + per-category deltas, CIs, span-integrity
```

## Replications

| Date | Device | Authors | Outcome |
|---|---|---|---|
| 2026-10-20 | Mac16,8 M4 Pro | Ralph Mattew Palomaria | Inconclusive/reject — +2.5 overall (CIs overlap), H2 & H3 refuted |
