# PoC 046: Legal-taxonomy query expansion for hard categories (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, 1,325 items; recall@3). |
| Verdict | **Adopt — the first mechanism in the series to clear the +10 hard-mean bar at retrieval.** A 7-element legal clause taxonomy per hard category lifts hard-mean recall@3 **34.7 → 45.0 (+10.3)** over the single-query baseline and **+6.3 over the PoC-016/030 generic templates** (38.7), with overall **+2.3** (62.6 → 64.9, no regression). Exclusivity — the series' worst category — jumps **6 → 34**, Non-Compete 33 → 41; Change-of-Control dips 65 → 60 (decomposition's known CoC side-effect, cf. 016/030). H1 (+≥10) PASS, H2 (+≥3 over generic) PASS, H3 (overall ≥ −2) PASS → **ADOPT.** The query-formulation lever was right all along (016/030); it just needed legally-grounded sub-queries. Caveat (PoC-040): this is a retrieval gain — answer-step conversion is a follow-up; and it composes with PoC-045's GreenLeaf embedder (query-side × embedder-side). See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox `2026-10-26-a-legaldomainaware-query-expansion-strategy` (engine `evo-g2-5`, novelty-push, OP-1). |
| Registered | 2026-10-26 (before the first run). |

## Question

Does expanding each hard-category query into **human-authored, legal-clause-element sub-queries** (grounded
in a clause taxonomy — e.g. Non-Compete → {restricted activity, geographic scope, duration, exceptions,
parties bound}) and pooling their retrievals lift hard-category recall@3 by **≥ +10 pp** over the
single-query hybrid baseline — clearing the bar PoC-016/030 stalled at (39.3 hard-mean)?

## Why it matters here

- Query formulation is the **only confirmed mover** of hard-category recall (PoC-016 decomposition:
  Exclusivity 7→24; PoC-030 pool N=2: hard-mean 39.3) — but both used small generic templates (2–3
  sub-queries). PoC-030 stalled +6.3 short of +10, suggesting the *mechanism is right but the sub-queries
  are too coarse*. A richer, legal-structure-grounded taxonomy per category is the untested refinement.
- It stays in the open lever (query side), avoiding the exhausted scoring (013), depth (009), pool-size
  (030), and entailment-gate (029/031/034/041/043) avenues. Pairs naturally with PoC-045's GreenLeaf
  embedder (better queries × better embedder) — tested here on EmbeddingGemma first for a clean delta.

## Hypothesis

Hard-category clauses are multi-faceted; a single vector (or 2–3 generic sub-queries) misses dispersed
facets. A 5–7-element legal taxonomy per category, each embedded and pooled (top-N per sub-query, union,
re-rank to K=3), recovers facet-specific evidence. Untested on our stack.

- **H1:** hard-mean recall@3 ≥ **+10 pp** over the single-query baseline (33.0).
- **H2:** beats PoC-030 (39.3 hard-mean) by **≥ +3 pp** (the taxonomy adds over generic templates).
- **H3:** overall recall@3 does not regress > 2 pp.

## Method

Fork the PoC-030 harness (committed PoC-014 chunks + `emb-page`, hybrid 0.9/0.1, per-sub-query pool N=2,
union + re-rank to K=3). **Author a legal clause-element taxonomy** (5–7 sub-queries per hard category,
committed as `taxonomy.json`), embed the sub-queries via EmbeddingGemma (`--embd-gemma-default`), and
evaluate recall@3 (top-3 covers ≥50% of gold span) overall + per hard category. Arms: (a) single-query
baseline, (b) PoC-016/030 generic templates (reference), (c) legal-taxonomy expansion (headline). Sweep
per-sub-query pool N ∈ {1,2}.

- **Varies:** the sub-query set (taxonomy vs generic vs single). **Held fixed:** EmbeddingGemma hybrid
  retrieval, PoC-014 chunk index, eval items + gold spans, K=3. **Measurements:** overall + per-hard-cat
  recall@3; contract-level bootstrap CI. **Repetitions:** deterministic → single pass.

## Decision rule

Adopt if **H1 (+≥10 over single-query) ∧ H3 (overall regression ≤2)**. Reject if hard-mean gain **< +3 over
PoC-030** (taxonomy adds nothing). Inconclusive between. Report per-category deltas.

## Expected outcome (engine estimate)

inconclusive · confidence ~0.45 · est. effort 3-4 days

## Harness

`query-expand.py` forks `030/subquery-pool.py`: loads `taxonomy.json` (7 legal clause-element sub-queries
per hard category), embeds them via EmbeddingGemma (query prefix), pools top-N=2 per sub-query → union →
re-rank to K=3, scores recall@3 (top-3 covers ≥50% of gold span). Three arms: single-query baseline, the
PoC-016/030 generic templates (3/cat, from committed `emb-subqueries`), and the legal taxonomy (headline).
Reads committed vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default`), full CUAD 1,325 items, hybrid 0.9/0.1, per-
sub-query pool N=2, recall@3. Hard categories use expansion; non-hard items keep the single-query path.

| Arm | overall | hard-mean | Exclusivity | Non-Compete | Change-of-Control |
|---|---|---|---|---|---|
| single-query baseline | 62.6 | 34.7 | 6 | 33 | 65 |
| generic templates (PoC-016/030, 3/cat) | 63.5 | 38.7 | 26 | 30 | 60 |
| **legal taxonomy (7/cat)** | **64.9** | **45.0** | **34** | **41** | 60 |

- **H1 (taxonomy hard-mean ≥ +10 over single):** PASS — **+10.3 pp** (34.7 → 45.0). The first time any
  mechanism in the series clears the pre-registered +10 hard-mean bar. MEASURED.
- **H2 (taxonomy ≥ +3 over generic templates):** PASS — **+6.3 pp** (38.7 → 45.0); richer legal sub-queries
  add substantially over the 3 generic ones. MEASURED.
- **H3 (overall regression ≤ 2):** PASS — overall *improves* +2.3 (62.6 → 64.9). MEASURED.
- **Per category:** Exclusivity 6 → **34** (the headline — the worst category finally moves hard),
  Non-Compete 33 → **41**; Change-of-Control 65 → 60 (the same decomposition side-effect PoC-016/030 saw —
  CoC's single-query form was already adequate). MEASURED.

Summary in `results/query-expand.json`; taxonomy in `taxonomy.json`.

## Verdict

**Adopt.** The query-formulation lever — the only lever that ever moved the hard categories (PoC-016/030) —
was right all along; it was starved of good sub-queries. Replacing 2–3 generic templates with a 7-element
legal clause taxonomy (restricted activity, geographic scope, duration, exceptions, parties bound, …) per
category lifts hard-mean recall@3 +10.3 pp over single-query and +6.3 over the generic templates, clearing
the +10 bar the series chased since PoC-009. The win concentrates exactly where it was needed: Exclusivity
6 → 34. This is zero-cost at inference (static per-category sub-query strings, no generation — PoC-011-safe)
and 6 GB-deployable.

Two caveats keep the scope honest: (1) **retrieval, not answer quality** — per PoC-040 the conversion to
span-F1 is not guaranteed and must be re-validated at the answer step (as for PoC-045); (2) **Change-of-
Control regresses** under expansion, so a production router should apply the taxonomy to Exclusivity /
Non-Compete and keep CoC on the single query. Natural next step: **compose with PoC-045** (legal taxonomy ×
GreenLeaf legal embedder) — both attack the hard categories from complementary sides (query vs embedding).

## Limits

- **recall@3 only** (answer-step conversion deferred, cf. PoC-040/049).
- **Hand-authored taxonomy** — risks overfitting CUAD's phrasing; generalisation to free-form user questions
  untested (likely weaker).
- **CoC side-effect** — expansion hurts Change-of-Control; adopt per-category, not blanket.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/046-legal-taxonomy-query-expansion
python3 query-expand.py            # or: LAB_POC_ROOT=/path/to/lab-clone/poc python3 query-expand.py
```

---

### Engine provenance
- `evo-g2-5` · novelty-push · OP-1 · UNSCREENED (NOT_VALIDATABLE). Promoted per the user's directive; extends
  the confirmed query-formulation lever (016/030) with a legal clause taxonomy. Verdict **ADOPT** (hard-mean +10.3, first to clear the +10 bar) feeds back to the ledger.
