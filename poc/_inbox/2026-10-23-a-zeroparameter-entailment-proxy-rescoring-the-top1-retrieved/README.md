# PoC (proposed): Does a zero-parameter entailment proxy — re-scoring the top-1 retrieve…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.


| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | Joint Constraint Aggregation for Qualifier-Sensitive Retrieval-Augmented QA + The Fusion Tax: A Diagnostic Analysis of When Hybrid Retrieval Hurts (http://arxiv.org/abs/2610.27114v1) |
| Registered | not yet — proposed 2026-10-23 |

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
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

If H1 (CAR gain ≥+8pp) AND H2 (answerable-recall loss ≤3pp): adopt as the OP-7 abstention signal. If CAR gain <+3pp over PoC-029: reject as not improving on the cosine baseline. Otherwise: inconclusive.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.38  ·  est. effort 5-7 days

## Results

Link raw files in `results/` once run. Tag every number MEASURED / OBSERVED / INFERRED.

## Verdict

Adopt / reject / inconclusive, against the decision rule.

## Limits

What this does not show.

## Reproduce

Commands from a clean checkout.

---

### Engine provenance (how this idea was generated)

- Engine idea id: `synth-idea-4` · technique: constraint-driven inversion · attacks: OP-7
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.45 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [cuad_hard:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-23. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
