# PoC 053: Pre-retrieval clause-term binding (query prefix) (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, 300 hard items; recall@3). |
| Verdict | **Adopt — and it is the new best hard-category retrieval lever, beating PoC-046.** Replacing the raw question entirely with a static canonical clause-term bag (**prefix-only**) lifts hard-mean recall@3 **34.7 → 54.0 (+19.3)** — far above the single-query baseline and **+9.0 over the adopted PoC-046 taxonomy** (45.0). Exclusivity jumps **6 → 54**, Non-Compete 33 → 44, Change-of-Control steady (65 → 64). The raw CUAD question is **actively harmful** as a retrieval query: prefix-only (54.0) > concat question+terms (50.7) > 046 taxonomy (45.0) ≫ question-only (34.7). H1 (+≥5 over single) PASS (+19.3); H2 is *inverted* — binding **beats** 046 by +9, so the simpler single canonical-term query is preferable to the multi-sub-query taxonomy. Control holds (question-only = 34.7). → **ADOPT.** Caveat (PoC-040): retrieval-only; answer-step conversion is the follow-up. Notably contrasts the other terminal's PoC-050 (exemplar-clause-phrasing, inconclusive) — a compact synonym bag works where full exemplar phrasings did not. See Verdict. |
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

## Harness

`clauseterm-binding.py` builds a static canonical clause-term table (synonym bag per hard category), embeds
the prefix-only and concat queries via EmbeddingGemma (:8090, query prefix), runs hybrid 0.9/0.1 single-query
retrieval, and scores recall@3 for question-only / prefix-only / concat, plus the PoC-046 taxonomy arm
(pooled, from the committed `taxonomy.json`) as reference. Reads committed vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default`), full CUAD, **300 hard items**, hybrid 0.9/0.1,
recall@3 (top-3 covers ≥50% of gold span).

| Arm | hard-mean | Exclusivity | Non-Compete | Change-of-Control |
|---|---|---|---|---|
| question-only (baseline) | 34.7 | 6 | 33 | 65 |
| **prefix-only (canonical terms)** | **54.0** | **54** | 44 | 64 |
| concat (terms + question) | 50.7 | 44 | 42 | 66 |
| PoC-046 taxonomy (pooled, ref) | 45.0 | 34 | 41 | 60 |

- **Control:** question-only 34.7 reproduces the known single-query baseline exactly. MEASURED.
- **H1 (binding ≥ +5 over single):** PASS — prefix-only **+19.3 pp**. MEASURED.
- **H2 (binding does not beat 046):** **inverted** — prefix-only **beats** the taxonomy by **+9.0 pp**.
  MEASURED.
- **Ablation:** prefix-only (54.0) > concat (50.7) > taxonomy (45.0) ≫ question-only (34.7) — the raw
  question *hurts* retrieval; adding it back to the canonical terms (concat) costs ~3 pp vs the terms alone.
  MEASURED.

Summary in `results/clauseterm-binding.json`.

## Verdict

**Adopt — the strongest and simplest hard-category retrieval lever found.** The result inverts the
pre-registered expectation: a single static canonical clause-term query (e.g. Exclusivity → "exclusive
rights sole provider exclusivity period exclusive territory exclusive dealing") doesn't merely approximate
PoC-046's taxonomy — it **beats** it by +9 pp and lifts hard-mean recall@3 to **54.0**, the highest the lab
has recorded. The mechanism is now clear: the CUAD question ("Does this contract contain an exclusivity
clause?") is a *meta*-question whose embedding sits far from the clause text; the hard-category deficit is
fundamentally a **query-vocabulary mismatch**, and the cleanest fix is to query with the clause's own
vocabulary and drop the question entirely (prefix-only > concat).

This refines the whole query-formulation thread: PoC-016/030/046 improved the query with *structured
decomposition + pooling*, but PoC-053 shows most of the gain is just **injecting canonical clause
vocabulary** — and a single flat synonym bag outperforms multi-sub-query pooling (simpler *and* better).
It also explains the contrast with the other terminal's PoC-050 (template *exemplar clause phrasings*,
inconclusive): full exemplar sentences are too specific/overfit, whereas a compact synonym bag generalises.

Practical recommendation: **adopt prefix-only canonical clause-term binding as the hard-category query** —
it is zero-cost (static per-category strings, no generation, no new model), deployable at 6 GB, and is the
new best EmbeddingGemma query. Open: (1) per PoC-040, re-validate at the answer step; (2) per PoC-051, it is
likely a *substitute* for the GreenLeaf embedder (both inject legal vocabulary) — the 053×GreenLeaf
composition should be checked but is expected redundant; (3) Change-of-Control is unmoved (already adequate).

## Limits

- **recall@3 only** (answer-step conversion deferred, cf. PoC-040/049).
- **Hand-authored synonym bags** for 3 categories; generalisation to all 41 CUAD categories / free-form user
  questions untested (though the mechanism is category-agnostic).
- **Per-category query is identical across items** — it ignores the specific question; fine for
  clause-presence retrieval, but a user asking a *specific* sub-question would lose that nuance (the question
  is dropped). A router could keep the question for fact categories and bind for hard categories.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/053-query-clauseterm-binding
python3 clauseterm-binding.py      # or: LAB_POC_ROOT=/path/to/lab-clone/poc python3 clauseterm-binding.py
```

---

### Engine provenance
- `synth-idea-2` · problem×method · OP-1 · UNSCREENED. Promoted per the user's directive to run; isolates the
  *vocabulary* half of PoC-046's query-formulation win (vs decomposition/pooling). Verdict **ADOPT** — prefix-only is the new best (54.0 recall@3, beats 046 by +9). Feeds back to the ledger.
