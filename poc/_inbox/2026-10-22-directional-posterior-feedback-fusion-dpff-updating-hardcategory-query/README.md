# PoC (proposed): Does directional posterior feedback fusion (DPFF) — updating hard-cate…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.


| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | Directional Posterior Feedback Fusion for Query Reformulation in Dense Retrieval (http://arxiv.org/abs/2610.29464v1) |
| Registered | not yet — proposed 2026-10-22 |

## Question

Does directional posterior feedback fusion (DPFF) — updating hard-category query embeddings in the direction of top-retrieved chunk embeddings iteratively — improve per-category recall@3 for Exclusivity/Non-Compete/Change-of-Control by ≥+10 points over the PoC-016 decomposition baseline?

## Why it matters here

- PoC-016 showed the hard-category bottleneck is query-formulation: Exclusivity jumped 7%→24% with static template decomposition. DPFF refines the query embedding in embedding-space using retrieved evidence, attacking the same formulation bottleneck without requiring any on-device generation.
- DPFF is purely vector arithmetic at inference time — no LLM call needed — making it feasible within the 6GB RAM budget alongside EmbeddingGemma-300M.

## Hypothesis

Neither DPFF nor PoC-016 tested DPFF on clause-typed legal queries (Exclusivity, Non-Compete, Change-of-Control). We hypothesize that initializing each hard-category query embedding then iteratively pulling it toward the top-3 retrieved chunk embeddings (1-2 feedback rounds, direction-only) will move the query representation closer to the embedding centroid of relevant clauses, recovering the 11%→24%+ Exclusivity recall already hinted at by PoC-016 template decomposition. This is entirely unverified on CUAD or EmbeddingGemma. The two mechanisms (directional PRF + category-typed queries) have never been composed.

- H1: DPFF with 1-2 feedback rounds raises hard-category mean recall@3 by ≥+10 points over PoC-016 decomposition baseline (current hard mean: ~+6 over raw baseline, so target is hard mean ≥ 35% with DPFF+decomp vs ~28% with decomp alone).
- H2: Overall recall@3 does not regress by more than 1 point vs PoC-016.
- H3: Per-query embedding update (direction computation) adds ≤200ms latency on iPhone 15 Pro (acceptable for contract review use case).

## Method

Reuse PoC-016 harness and template-decomposed sub-queries for hard categories. After initial retrieval, compute the mean embedding of top-3 returned chunks, subtract the query embedding to get a feedback direction, then update the query embedding by adding a step-size-scaled projection of that direction (alpha ∈ {0.1, 0.3, 0.5}). Re-retrieve with updated embedding. Measure per-category recall@3 and overall recall@3 vs (a) raw baseline and (b) PoC-016 decomposition. Run full 1,325-item CUAD set, report hard categories separately.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

If H1 (+≥10 hard-mean points over decomp) and H3 (latency ≤200ms) hold: adopt DPFF as retrieval refinement layer for hard categories. If H1 < +5 points: reject (decomp-only is simpler and already approved). Otherwise (H1 in +5..+10): inconclusive, run ablation over alpha values.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.42  ·  est. effort 1 week

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

- Engine idea id: `synth-idea-1` · technique: problem×method · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.35 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [semantic:NULL; conjunctive:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
