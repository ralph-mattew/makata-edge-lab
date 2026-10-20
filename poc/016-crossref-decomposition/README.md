# PoC 016: Cross-reference resolution + question decomposition for the hard categories

| | |
|---|---|
| Status | Planned (registration draft) |
| Verdict | TBD |
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

To be filled after run. Raw in `results/`: `recall-<condition>.json`, `comparison.txt`,
`xref-stats.json`, `decomp-templates.json`. Numbers tagged MEASURED / OBSERVED / INFERRED.

## Verdict

To be determined after run, against the decision rule.

## Deviations

None yet. Dated changes recorded here after registration.

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
python3 build-conditions.py    # resolve cross-references; author/load decomposition templates
./run.sh                       # embed each condition, score per-category recall@3, compare
python3 compare.py             # per-category deltas + CIs for xref / decomp / combination
```

## Replications

| Date | Device | Authors | Outcome |
|---|---|---|---|
| TBD | Mac16,8 M4 Pro | Ralph Mattew Palomaria | TBD |
