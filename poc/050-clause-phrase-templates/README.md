# PoC 050: Clause-phrase-template query transform (engine-discovered)

| | |
|---|---|
| Status | host run (2026-10-27) |
| Verdict | inconclusive |
| Source idea | ideation-engine `evolve_query_ops` mechanism search (not a paper) |
| Registered | 2026-10-27, decision.json committed before the run |

## Question
Does replacing the generic CUAD question with per-category **exemplar clause phrasings** (a
template-based HyDE-without-a-generator) lift hard-category recall@3 on the canonical full-corpus
harness without regressing overall recall@3?

## Why it matters
The mechanism was **invented and statistically confirmed by the engine's own mechanism search**
(`evolve_query_ops` on the powered cuad_hard substrate: +26pp hard-cat recall@3 out-of-sample,
per-query CI[0.177,0.343], frac+ 1.0). This PoC is the fidelity test: does that within-substrate lead
survive on the lab's canonical harness (emb-page chunks, covers≥50% recall@3, production 0.9/0.1
hybrid, full committed set) — the metric the lab actually reports?

## Hypothesis
- H1: hard-category mean recall@3 beats PoC-030's best (39.3) by ≥5pp.
- H2: overall recall@3 does not regress by more than 1pp.

## Method
`experiment.py`: for each query's category, emit a small set of exemplar clause phrasings, embed them
in-space (`ctx.embed_queries`, EmbeddingGemma), hybrid-score each (0.9 dense + 0.1 BM25) against the
contract's chunks, and rank by the union (max over sub-queries). No generator, no re-chunking — only the
query is reformulated. Verdict computed by `auto_experiment/harness.py` (deterministic) against the
pre-registered `decision.json`.

## Decision rule (pre-registered)
Adopt if hard_mean ≥ 44.3 AND overall recall@3 regression ≤ 1pp; reject if hard_mean < 39.3; else inconclusive.

## Results (MEASURED — auto_experiment harness, full committed set)
| metric | baseline | PoC-050 | Δ |
|---|---|---|---|
| hard-category mean recall@3 | 33.0 | **59.33** | **+26.3** |
| overall recall@3 | 61.8 | 59.55 | −2.25 |

- **H1 PASS** (hard_mean 59.33 ≫ 44.3) — the +26pp lift **transferred** from the within-substrate search
  to the canonical harness. The engine-invented mechanism is real and powerful on the hard categories.
- **H2 FAIL** (overall −2.25pp) — the templates **redistribute**: huge hard-category gains, small overall
  loss, because the generic exemplars/fallback misfire on EASY categories where the raw question already
  wins. Same redistribution pattern as PoC-022 (maxsim).

## Verdict
**Inconclusive** by the pre-registered rule: the hard-category target is smashed but overall recall@3
regresses beyond the 1pp tolerance. A real mechanism with a real cost, not a free win.

## Limits / next
- The win is a **redistribution**, not a Pareto improvement. The obvious follow-up (new PoC, new
  pre-registration — not a retro-edit of this rule): **apply the templates ONLY to the hard categories**
  (route by category), keeping the raw query where it already wins — which should capture most of the
  +26pp hard lift without the overall regression.
- This is also the first lab PoC whose mechanism was **invented + confirmed by the engine's mechanism
  search** rather than transferred from a paper — the open-lever loop working end to end.

## Reproduce
```
# engine side (the search that found it): engine/evolve_query_ops.py on dataset_cuad_hard_large.json
python3 auto_experiment/run_experiment.py poc/050-clause-phrase-templates   # needs the embed server up
```
