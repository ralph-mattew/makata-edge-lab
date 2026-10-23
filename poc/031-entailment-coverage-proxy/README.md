# PoC 031: Zero-parameter entailment proxy (weakest-link sub-phrase coverage) for absent clauses (OP-7)

| | |
|---|---|
| Status | Concluded — host stage (separability of two abstention signals) |
| Verdict | **Inconclusive — effectively negative.** The weakest-link sub-phrase coverage signal does **not** beat PoC-029's plain top-1 cosine: separability AUC is essentially identical (Exclusivity 0.60→0.60, Non-Compete 0.73→0.73, Change-of-Control 0.73→0.75), and the CAR-at-≤3pp-recall deltas are a wash (−3.0 / +3.0 / +0.0; best +3.0, below the +8 H1 bar). Decomposing the question into sub-phrases adds no separating power. With PoC-026's 86.3% Qwen baseline capping real value anyway, this closes the retrieval-side absent-clause angle. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Joint Constraint Aggregation for Qualifier-Sensitive Retrieval-Augmented QA + The Fusion Tax: A Diagnostic Analysis of When Hybrid Retrieval Hurts (http://arxiv.org/abs/2610.27114v1); 2026-10-23 ideation-engine DIVERGENT scan. Actions the PoC-026/029 forward-pointer. |
| Registered | 2026-10-23 (this draft, before the first run) |

## Question

Does a zero-parameter entailment proxy — re-scoring the top-1 retrieved chunk against the CUAD question using joint constraint decomposition (JCA-style sub-phrase cosine coverage) rather than a top-level cosine gate — improve Correct Abstention Rate on the ~14% residual absent-clause misses by ≥+8pp at ≤3pp answerable-recall loss?

## Why it matters here

- OP-7 identifies that the remaining ~14% of absent-clause misses are a generation/verification problem — the generator retrieves something similar but the clause is actually absent, and Qwen hallucinates a positive. PoC-029 showed per-category top-1 cosine separates absent vs answerable (AUC 0.73) but the ceiling gain is only +8.8pp
- JCA's insight — that a passage satisfying only some sub-constraints of a multi-part question should score lower than one satisfying all — provides a strictly stronger absent-clause signal than raw top-1 cosine: an absent clause will satisfy fewer sub-constraints of the question, giving a lower joint coverage score that could push more absent items below the abstention threshold without harming answerable items

## Hypothesis

Neither paper tested absent-clause abstention on CUAD, and neither combined JCA sub-phrase scoring with an abstention gate. We hypothesize that decomposing the CUAD question into sub-phrases (split on AND/OR/comma), scoring the top-1 chunk against each sub-phrase with EmbeddingGemma cosine, and using the minimum sub-phrase cosine (the weakest-link score) as the abstention signal provides a strictly better CAR improvement on the ~14% residual misses than the raw top-1 cosine used in PoC-029 — unverified.

- H1: Minimum sub-phrase cosine (weakest-link JCA score) raises CAR on the ~14% residual absent misses by ≥+8pp over the PoC-029 top-1 cosine gate baseline
- H2: Answerable-recall loss is ≤3pp (the OP-7 constraint)
- H3: Sub-phrase decomposition and re-scoring requires only EmbeddingGemma (already loaded) — no additional model, latency ≤1.5× baseline per query

## Method

Reuse PoC-029 harness. For each query: decompose into sub-phrases by splitting on 'AND'/'OR'/','/', embed each sub-phrase with EmbeddingGemma, score top-1 retrieved chunk against each sub-phrase, take the minimum cosine as the abstention signal. Sweep thresholds on the absent-clause validation split. Measure CAR gain and answerable-recall loss vs PoC-029 top-1 cosine baseline. Confirm no new model is loaded.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the absent-clause abstention *signal* only — PoC-029's `cosine(query, top-1 chunk)` vs the weakest-link `min_k cosine(sub-phrase_k, top-1 chunk)`. Both score the **same** top-1 retrieved chunk. **Held fixed:** EmbeddingGemma, the PoC-014 chunk index, the PoC-008 absent + PoC-007 answerable hard-cat sets, retrieval. **Measurements:** per-category absent-vs-answerable separability AUC and CAR at ≤3pp answerable-recall loss, for each signal. **Repetitions:** deterministic → single pass.

## Decision rule

If H1 (CAR gain ≥+8pp) AND H2 (answerable-recall loss ≤3pp): adopt as the OP-7 abstention signal. If CAR gain <+3pp over PoC-029: reject as not improving on the cosine baseline. Otherwise: inconclusive.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.38  ·  est. effort 5-7 days

## Harness

`entailment-proxy.py` (EmbeddingGemma server for the query + sub-phrases; committed chunk vectors):
for each hard-category item, take the top-1 retrieved chunk, then compute two signals against it —
`cosine(full query, top-1)` (PoC-029 baseline) and `min_k cosine(sub-phrase_k, top-1)` where
sub-phrases split the question on AND / OR / commas. Reports per-category absent-vs-answerable AUC and
CAR at ≤3pp answerable-recall loss for each signal. 101 absent + 300 answerable hard-cat items.

## Results

MEASURED on the host (EmbeddingGemma).

| Category | AUC (top-1 cos) | AUC (min-subphrase) | CAR@≤3pp (top-1 cos) | CAR@≤3pp (min-subphrase) | Δ CAR |
|---|---|---|---|---|---|
| Exclusivity | 0.60 | 0.60 | 63.6% | 60.6% | −3.0 |
| Non-Compete | 0.73 | 0.73 | 33.3% | 36.4% | +3.0 |
| Change Of Control | 0.73 | 0.75 | 11.4% | 11.4% | +0.0 |

- **H1 (min-subphrase CAR ≥ +8pp over top-1 cosine):** FAIL — best Δ +3.0 (Non-Compete), offset by
  −3.0 (Exclusivity); net ~0. MEASURED.
- **Separability unchanged** — AUC is within ±0.02 of the top-1 cosine baseline everywhere; the
  weakest-link decomposition does not add a stronger absent signal. MEASURED.
- **H3 (zero-parameter / EmbeddingGemma-only):** holds — no new model. OBSERVED.

Per-signal figures in `results/entailment-proxy.json`.

## Verdict

**Inconclusive by the rule, effectively negative.** The entailment proxy's premise — that an absent
clause satisfies fewer of the question's sub-constraints, so the weakest-link sub-phrase cosine is a
sharper absent signal than the top-level cosine — does **not** hold on our stack: AUC is unchanged
(0.60 / 0.73 / 0.75 vs 0.60 / 0.73 / 0.73) and the CAR deltas net to ~zero (−3 / +3 / 0). The most
likely reason: EmbeddingGemma sentence embeddings already pool the whole question, so splitting it and
taking the min just re-expresses the same similarity with more variance, not a new discriminative axis.

Combined with the standing **PoC-026 ceiling** (Qwen already abstains on 86.3% of absent clauses with
context), this **closes the retrieval-side absent-clause programme**: a plain cosine gate (021),
per-category thresholds (029), and now sub-phrase coverage (031) all fail to beat the generator. The
remaining viable direction for the residual ~14% is a genuine **entailment/NLI check with a model that
reasons over the (clause, question) pair** — not a cosine-derived proxy — weighed against simply
accepting Qwen's 86% as good enough for the product.

## Limits

- **Sub-phrase split is lexical** (AND/OR/comma). A parser-based clause split could differ, but the
  signal is bottlenecked by the embedding geometry (AUC flat), not the split quality.
- **Signal compared against top-1 chunk only** (per the proposal). Scoring sub-phrases against the full
  top-3 is untested, but would dilute, not sharpen, the absent signal.
- **CAR here is signal-vs-signal** (routable fraction), not end-to-end; the PoC-026 86.3% baseline caps
  the real-world gain regardless.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

cd poc/031-entailment-coverage-proxy
python3 entailment-proxy.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `synth-idea-4` · technique: constraint-driven inversion · attacks: OP-7
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.45 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [cuad_hard:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-23. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
