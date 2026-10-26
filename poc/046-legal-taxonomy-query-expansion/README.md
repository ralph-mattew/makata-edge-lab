# PoC 046: Legal-taxonomy query expansion for hard categories (OP-1)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending._ |
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

## Harness (to be written at run time)

`query-expand.py` forks `030/subquery-pool.py`: loads `taxonomy.json`, embeds sub-queries (EmbeddingGemma
:8090), pools top-N per sub-query → union → re-rank K=3, scores recall@3. Reads committed vectors via
`LAB_POC_ROOT`.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/046-legal-taxonomy-query-expansion && python3 query-expand.py
```

---

### Engine provenance
- `evo-g2-5` · novelty-push · OP-1 · UNSCREENED (NOT_VALIDATABLE). Promoted per the user's directive; extends
  the confirmed query-formulation lever (016/030) with a legal clause taxonomy. Verdict feeds back to the ledger.
