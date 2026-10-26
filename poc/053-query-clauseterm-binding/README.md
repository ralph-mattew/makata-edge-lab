# PoC 053: Pre-retrieval clause-term binding (query prefix) (OP-1)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox `2026-10-27-adding-a-preretrieval-admissiondisambiguation-step` (engine `synth-idea-2`, problem×method, OP-1). |
| Registered | 2026-10-27 (before the first run). |

## Question

Does prepending a **static canonical clause-term prefix** (synonym set per hard category) to the query
before embedding lift hard-category recall@3 — and does this lightweight single-query binding match the
full **PoC-046 legal taxonomy** (multi-sub-query, +10.3) or fall short of it?

## Why it matters here

- Hard-category questions ("Does this contract contain an exclusivity clause?") are underspecified; the
  word rarely appears verbatim. Injecting canonical clause terminology before embedding is the **single-query
  analogue** of PoC-046's multi-sub-query taxonomy.
- This also sharpens the interpretation of the adopted PoC-046: is the taxonomy's win from *decomposition*
  (multiple pooled sub-queries) or merely from *injecting clause vocabulary* (which a single prefix also
  does)? PoC-053 isolates the vocabulary half.

## Hypothesis

A canonical clause-term prefix supplies the vocabulary the raw question lacks; but a single augmented query
cannot pool facet-specific retrievals the way 046's sub-queries do, so it should help but underperform 046.

- **H1:** hard-mean recall@3 ≥ **+5 pp** over the single-query baseline (34.7).
- **H2:** it does **not** beat PoC-046's taxonomy (45.0) — i.e. decomposition/pooling, not just vocabulary,
  drives 046 (if 053 ≈ 046, the simpler prefix is preferable).
- **H3 (ablation):** concatenation (question + prefix) ≥ prefix-only ≥ question-only.

## Method

Build a static canonical clause-term table for the 3 hard categories (synonyms: Exclusivity → exclusive
rights / sole provider / exclusive dealing / …; Non-Compete → covenant not to compete / …; Change-of-Control
→ merger / acquisition / assignment on change / successor-in-interest / …). For each hard-category question,
prepend the category's canonical terms as a query prefix, embed via EmbeddingGemma, run hybrid 0.9/0.1,
recall@3 overall + per hard category. **Ablate:** question-only (baseline) vs prefix-only vs concatenation.
Reference arm: PoC-046 taxonomy (committed result / re-run).

- **Varies:** the query (question / prefix / concat). **Held fixed:** EmbeddingGemma, PoC-014 chunk index,
  eval items, K=3. **Measurements:** overall + per-hard-cat recall@3; contract-level bootstrap CI.
  **Repetitions:** deterministic.

## Decision rule

Adopt (as a cheaper alternative to 046) if **H1 (+≥5 over single) ∧ H2-tie (within 2 pp of 046)**. Reject if
hard-mean gain **< +3** over single-query. Inconclusive between. Report vs 046 prominently.

## Expected outcome (engine estimate)

inconclusive · confidence ~0.42 · est. effort 2-3 days

## Harness (to be written at run time)

`clauseterm-binding.py` forks `046/query-expand.py`: builds the canonical-term table, embeds the
prefix/concat queries (EmbeddingGemma :8090), scores recall@3 for question-only / prefix-only / concat, and
compares to the 046 taxonomy arm. Reads committed vectors via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/053-query-clauseterm-binding && python3 clauseterm-binding.py
```

---

### Engine provenance
- `synth-idea-2` · problem×method · OP-1 · UNSCREENED. Promoted per the user's directive to run; isolates the
  *vocabulary* half of PoC-046's query-formulation win (vs decomposition/pooling). Verdict feeds back to the ledger.
