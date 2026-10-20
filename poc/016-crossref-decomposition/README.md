# PoC 016: Cross-reference resolution + question decomposition for the hard categories

| | |
|---|---|
| Status | Concluded — full corpus (397 contracts, 1,325 items) |
| Verdict | **Mixed — xref rejected, decomposition is a partial win.** Cross-reference resolution slightly hurt (−0.7). Template question decomposition lifted overall +1.4 and **Exclusivity 7%→24% (+17)** — the first mechanism in the whole PoC series to move a hard category — but its hard-category *mean* gain (+6) fell short of the pre-registered +10, so strictly inconclusive-with-signal. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet |
| Source idea | Synthesized by the lab's own ideation pipeline (2026-10-20 scan, Stage 3b cross-pollination), then consolidated by hand. Combines two papers neither of which proposed the combination — *StrucChunk* (clause/cross-reference-aware legal RAG) and *RESIN* (multi-chain question decomposition) — aimed at the bottleneck PoC 013/014 isolated. |
| Registered | 2026-10-20 (this draft, before the first run) |

## Question

For the **weight-invariant hard categories** (Exclusivity ~9%, Non-Compete, Change Of
Control), does **(a) resolving cross-references before embedding** and/or **(b)
decomposing the category question into focused sub-queries** lift per-category recall@3
by **≥10 points** on CUAD/EmbeddingGemma — where neither retrieval scoring (PoC 013),
retrieval depth (PoC 009), nor clause boundaries (PoC 014) moved the needle?

## Why it matters here

Three of our own PoCs have now ruled out the obvious causes for the hard categories:

- **PoC 013:** Exclusivity stayed ~11% at *every* semantic/BM25 weight — not a scoring problem.
- **PoC 009:** extra retrieval depth didn't help — not a depth problem.
- **PoC 014:** clause-boundary chunking gave +4/+2/0 on the hard categories and *reduced*
  span-integrity; page chunking already contained the gold span in one chunk 95.8% of the
  time — **not a boundary problem, and not a span-splitting problem.**

So the right chunk usually *exists and is retrievable* — it just isn't being retrieved
for these categories. Two mechanisms left standing, both about **what text is matched
against the query**, not how chunks are cut or scored:

1. **Cross-reference resolution (from StrucChunk).** Hard-category clauses are often *thin
   pointers*: "the Exclusivity restriction in Section 3.2 shall not apply to…". The
   operative scope lives in a *referenced* clause. If the chunk embedded for Section-X
   doesn't contain the referenced definition/scope text, the query can't match it. StrucChunk
   resolves cross-references **before** embedding and attributes 73–88% of its reported gain
   to the chunking/resolution mechanism (not the scorer) across legal corpora — but never on
   CUAD, never with EmbeddingGemma, and at recall@5 not @3.
2. **Question decomposition (from RESIN).** The CUAD hard-category questions are compound —
   Exclusivity implicitly asks about *scope*, *exceptions*, and *parties*, which are dispersed
   across clauses. A single query vector averages those facets. RESIN decomposes a question
   into one-hop sub-questions and unions the per-sub-question retrievals — but it used an
   **LLM to generate** the sub-questions, and **PoC 011 showed on-device generation hurts our
   retrieval**, so we must decompose **without** on-device generation.

**The lab-specific, novel-for-us bet:** neither paper ran CUAD/recall@3/hard-categories, and
**neither combined the two**. This PoC tests each mechanism *and their combination*, under the
6GB constraint that forces a **template-based (non-generative) decomposition** — a design
choice no source suggests, grounded in PoC 011. The mechanisms are borrowed prior art; the
*targeting* (the specific hard-category failure mode) and the *on-device-feasible instantiation*
are ours.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items. Baseline is the PoC
014 `page` condition (per-category recall@3 at hybrid 0.9/0.1, top-3) — the measured hard-
category numbers: Exclusivity 7%, Non-Compete 25%, Change Of Control 67%, overall 61.8%.

1. **H1 (cross-reference resolution).** Resolving cross-references before embedding lifts the
   mean hard-category recall@3 by **≥10 points** vs the page baseline.

2. **H2 (template decomposition).** Template-based sub-query decomposition (union of top-3 per
   sub-query, no generation) lifts the mean hard-category recall@3 by **≥10 points** vs baseline.

3. **H3 (combination).** Applying both together beats the better single mechanism by **≥3
   further points** on the hard categories (they attack different failure modes — thin-pointer
   clauses vs multi-facet queries — so they should be complementary, not redundant).

4. **H4 (no collateral damage).** Overall recall@3 (all 14 categories) does **not regress** by
   >1 point, and the already-easy categories (Governing Law, Insurance) move <2 points.

5. **H5 (on-device feasibility).** Cross-reference resolution is deterministic string work
   (no model); template decomposition issues K≤3 extra embedding lookups per hard-category
   query (no generation). Index-build and per-query cost stay within the 6GB/on-device budget.

Descriptive: per-category recall deltas for each arm; examples of hard-category items that flip
miss→hit under each mechanism; count of cross-references resolved per contract.

## Method

**Host.** MacBook Pro (Mac16,8), M4 Pro, 24 GB, macOS 26.5.1, AC power (as PoC 009/014).

**Held fixed (so only the mechanism changes):** EmbeddingGemma-300M (mean pool, L2, ctx 2048),
hybrid 0.9 semantic + 0.1 BM25, top-3, PoC 007's 1,325 items / 397 contracts. Reuse the PoC
014 embed/score/compare harness (per-category recall@3 + contract-level bootstrap CIs).

**Conditions.**

| Condition | What changes |
|---|---|
| `page` (baseline) | PoC 014 page chunks, raw CUAD question (the current system) |
| `xref` | page chunks, but each chunk with an internal reference ("Section N", "Exhibit X", a defined term) has the **referenced clause's text appended before embedding** (deterministic resolution) |
| `decomp` | raw chunks, but each hard-category query is expanded to a fixed **template** set of 2–3 sub-queries (per category, authored once — NOT generated); retrieve top-3 per sub-query, union, re-rank by max hybrid score, take top-3 |
| `xref+decomp` | both together |

**Cross-reference resolver (deterministic, no model).** Detect reference tokens in a chunk
("Section 3.2", "Article V", "Exhibit A", capitalized defined terms in quotes); locate the
referenced clause by its heading/number in the same contract; append its text (capped) to the
referencing chunk before embedding. No network, no LLM. (This is the StrucChunk *mechanism*
without its DAG/RRF/BGE-M3 apparatus — reimplemented for our stack.)

**Template decomposition (deterministic, no generation).** For each of the ~14 CUAD categories,
author a small fixed set of sub-query templates once (e.g. Exclusivity → {"exclusive dealing
restriction", "exceptions to exclusivity", "parties bound by exclusivity"}). These are static
strings per category, reused across all contracts — **41×-style amortization, zero per-item
generation** (the PoC-011-safe design). Only hard categories need decomposition; easy ones can
use the raw question.

**Measurements.** (1) per-category recall@3 for each condition (primary); (2) overall recall@3
(H4); (3) span/resolution stats — cross-references resolved per contract, sub-queries per
category; (4) cost — index-build delta for `xref`, extra lookups per query for `decomp`.
95% CIs via contract-level bootstrap (10,000 resamples, seed 0).

## Decision rule

Written before the first run.

- **Adopt `xref`** if H1 (hard categories mean +≥10) **and** H4 (no overall regression >1 pt).
- **Adopt `decomp`** if H2 **and** H4.
- **Adopt the combination** if H3 holds (combination beats the better single by ≥3) and H4 holds.
- **Reject** a mechanism whose hard-category mean moves <3 points.
- **Inconclusive** for 3–10 points.
- **Report per-category deltas prominently** — a mechanism that fixes *Exclusivity specifically*
  (our worst category) is notable even if the category mean is modest.

## Results

Full corpus: 397 contracts, 1,325 items, hybrid 0.9/0.1, top-3. Raw in `results/`
(`recall-{page,xref}-{raw,decomp}.json`, `comparison.txt`). xref augmented 6,774 / 79,037
chunks (8.6%); decomposition used 3 templates each for the 3 hard categories (9 sub-queries,
non-generative). Baseline reuses PoC 014 page chunks/embeddings; `page/raw` reproduces PoC
014's 61.8% exactly (harness validated).

**Recall@3 (MEASURED, 1,325 items).**

| Condition | overall | 95% CI | Δ overall | hard-cat mean | Δ hard |
|---|---|---|---|---|---|
| `page/raw` (baseline) | 61.8% | 59.3–64.4 | — | 33.0% | — |
| `xref/raw` | 61.1% | 58.6–63.7 | −0.7 | 32.0% | −1.0 |
| **`page/decomp`** | **63.2%** | 60.7–65.6 | **+1.4** | **39.0%** | **+6.0** |
| `xref/decomp` | 62.3% | 59.7–64.8 | +0.5 | 37.0% | +4.0 |

**Hard categories, per condition (MEASURED, 100 items each).**

| Category | page/raw | xref | decomp | both |
|---|---|---|---|---|
| **Exclusivity** | 7% | 7% | **24%** | 18% |
| Non-Compete | 25% | 24% | 28% | 27% |
| Change Of Control | 67% | 65% | 65% | 66% |

**Observations.**
- **OBSERVED (xref refuted, H1 no):** cross-reference resolution did **not** help and slightly
  hurt (−0.7 overall, −1.0 hard). Appending the referenced clause's text dilutes the chunk's
  embedding more than the extra context helps matching — the same dilution effect PoC 011 saw
  with generated context. The "thin-pointer" theory does not hold on CUAD/EmbeddingGemma.
- **OBSERVED (decomposition — the signal, H2 partial):** template question decomposition lifted
  overall recall +1.4 and the hard-category mean +6.0. The headline is **Exclusivity 7% → 24%
  (+17 points)** — the first mechanism across PoC 009/011/013/014 to move a hard category at
  all. Non-Compete +3; Change Of Control −2 (its single-query form was already adequate at 67%).
  The pre-registered bar was +≥10 on the hard *mean*; actual +6.0, so H2 is **not** met as a mean
  — but the decision rule explicitly flagged a per-category fix as notable, and Exclusivity is it.
- **OBSERVED (no synergy, H3 no):** combining xref+decomp (37.0%) was *worse* than decomp alone
  (39.0%) — xref's dilution drags decomposition down. Drop the combination.
- **OBSERVED (H4 pass):** no condition regressed overall by >1 pt (worst −0.7); easy categories
  were not measured to move materially.
- **INFERRED:** the hard categories are a **query** problem, not a chunk problem. Exclusivity
  questions are multi-facet (restriction + exceptions + parties); a single averaged query vector
  misses dispersed evidence that 2–3 focused sub-queries recover — and this works with **zero
  on-device generation** (static templates), so it is 6GB-deployable.

## Verdict

**Mixed, against the pre-registered decision rule:**

- **`xref` (cross-reference resolution): REJECT.** H1 fails (−1.0 hard mean, −0.7 overall). Does
  not transfer to CUAD/EmbeddingGemma; appended reference text dilutes the embedding.
- **`decomp` (template question decomposition): ADOPT-worthy signal, strictly inconclusive.**
  H2's +10 hard-mean bar was not met (+6.0), so by the letter of the rule it is **inconclusive**.
  But it produced the series' only real hard-category movement — **Exclusivity +17 (7%→24%)** —
  lifts overall +1.4 with no regression (H4 pass), and needs **no on-device generation**. Per the
  registered "report per-category prominently" clause, this is the result worth carrying forward.
- **Combination: REJECT.** H3 fails (combo < best single); xref drags decomp down.

**Recommendation.** Reject xref and the combination. Pursue **decomposition** as the live lead on
the hard categories — a focused follow-up: tune the Exclusivity/Non-Compete templates, extend to
other weak categories, and measure key-fact accuracy end-to-end (not just recall@3). This is the
first evidence that the hard-category bottleneck is a **query-formulation** problem (consistent
with [PoC 015](../015-query-formulation)), not a chunking/scoring/depth one (PoC 013/014/009).

## Deviations

- **2026-10-20 (the run):** Cross-reference resolution restricted to **reliably-resolvable**
  targets — distinctive dotted section numbers ("Section 3.2") and UPPERCASE heading phrases
  ("EXHIBIT A", "ARTICLE V") — after an initial version mis-resolved bare single-letter labels
  ("A") against the ubiquitous token "A". Embedding reused PoC 014's `emb-page` as the base and
  embedded only the 6,774 changed chunks (overlaid at score time) to avoid re-embedding 79k
  chunks and a 1.3 GB in-memory copy.

## Provenance (how this idea was generated)

Surfaced by the lab's own automated ideation pipeline on 2026-10-20: the Stage 3b
cross-pollination step combined **StrucChunk** (problem×method against OP-1) and **RESIN**
(method×method against OP-1) into the two mechanisms above, explicitly choosing template-based
decomposition over generation *because* [PoC 011](../011-contextual-embeddings) found on-device
generation hurts retrieval. Both survived the (recalibrated) quality gates; this PoC consolidates
them and drops two weaker survivors from the same batch (a SpecMRL embedding-compression idea
with an admitted on-device retraining gap, and a clause-boundary-only idea already settled by
PoC 014). See `poc/_automation/SYNTHESIS-AND-GATE-CALIBRATION.md`.

## Limits

1. **Borrowed mechanisms.** Cross-reference resolution and question decomposition are published
   prior art (StrucChunk, RESIN, HyDE-lineage). The contribution is the CUAD/6GB/hard-category
   *application* and the non-generative instantiation, not a new algorithm.
2. **Heuristic cross-reference resolution.** Reference detection is heuristic; CUAD formatting is
   inconsistent and some references will be missed or mis-resolved (cf. PoC 014's boundary heuristics).
3. **Hand-authored templates** risk overfitting to CUAD's category phrasing; they may not
   generalize to free-form user questions (conservative — free-form is likely worse).
4. **Answerable items only** — absence behaviour (PoC 008) not measured; `decomp` could raise
   false retrieval on category-absent contracts (a flagged risk, OP-4).
5. **CUAD / EmbeddingGemma / top-3 / English only** — held fixed to isolate the two mechanisms.
6. **Retrieval recall, not end-to-end** — key-fact accuracy with Qwen is a follow-up.
7. Composes with [PoC 015](../015-query-formulation) (query side) and supersedes the
   cross-reference follow-up logged in [PoC 014](../014-clause-aware-chunking).

## Reproduce

Requirements: Apple-silicon Mac (macOS 26.4+, Swift 6.3+), llama.cpp; PoC 006/007/014 run once.

```bash
cd poc/016-crossref-decomposition
python3 build-conditions.py                  # xref chunks (reusing PoC 014 page chunks) + templates
llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
python3 embed.py --xref --subqueries         # embed only changed chunks + sub-queries (reuse emb-page)
for cc in page xref; do for qc in raw decomp; do python3 score.py --chunk-cond $cc --query-cond $qc; done; done
python3 compare.py                           # per-category deltas + CIs, H1-H4 read-out
```

## Replications

| Date | Device | Authors | Outcome |
|---|---|---|---|
| 2026-10-20 | Mac16,8 M4 Pro | Ralph Mattew Palomaria | xref reject; decomposition lifts Exclusivity +17 (7%→24%), hard-mean +6 (<+10 bar) |
