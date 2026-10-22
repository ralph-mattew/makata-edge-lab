# PoC (proposed): Does validation-gated PTQ calibration of EmbeddingGemma-300M to 8-bit …

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

> ⚠️ **UNSCREENED — lower confidence.** This idea was not micro-lab-validated (it doesn't map to a runnable screening substrate), so it carries only the gate signal (which has weak predictive power). Weigh accordingly.


| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | arxiv-2610.27397v1 |
| Registered | not yet — proposed 2026-10-22 |

## Question

Does validation-gated PTQ calibration of EmbeddingGemma-300M to 8-bit (int8) weights — a strictly less aggressive quantization than 4-bit — preserve recall@3 within 0.5 points of the fp16 baseline while freeing ≥150MB RAM on the 6GB iPhone 15 Pro budget, and does it pass the validation gate reliably across calibration doses?

## Why it matters here

- 4-bit PTQ on embedding models is high-risk: the parent paper showed calibration dose can cause catastrophic collapse even with a validation gate. Relaxing to 8-bit weight quantization is the hardest constraint to invert — it sacrifices some RAM savings but dramatically reduces the collapse risk, making the experiment feasible on-stack without a large safety net.
- Even a conservative 150MB saving from int8 EmbeddingGemma frees enough headroom to upgrade from Qwen2.5-1.5B to Qwen2.5-3B (or extend context window), directly addressing OP-3's RAM bottleneck without the 4-bit catastrophic-degradation risk that makes 4-bit an infeasible first step.

## Hypothesis

The paper tested 4-bit PTQ specifically; we hypothesize that relaxing to 8-bit weight quantization (less information loss) will (a) yield a much narrower distribution of calibration-dose outcomes — fewer or no catastrophic-collapse runs — and (b) consistently pass the validation gate across a range of calibration doses on a CUAD-derived calibration set, preserving our 61.4% recall@3 baseline within 0.5 points while freeing ≥150MB RAM. This combined outcome (reliable passage + ≥150MB saving + <0.5pt recall loss) is NOT established by any source for our specific stack or CUAD domain.

- H1: int8 PTQ EmbeddingGemma-300M recall@3 on CUAD ≥60.9% (within 0.5 points of 61.4% fp16 baseline)
- H2: int8 model frees ≥150MB RAM vs fp16 EmbeddingGemma-300M on-device (target: fp16=600MB → int8≤450MB)
- H3: validation gate passes for ≥4 of 5 calibration dose levels tested (collapse rate <20%), demonstrating reliable int8 quantization for our stack
- H4: Hard-category recall@3 (Exclusivity, Non-Compete, Change-of-Control) does not regress by >2 points absolute vs the fp16 baseline

## Method

Reuse the PoC-007/PoC-013 experiment harness and CUAD evaluation set. Apply int8 weight-only PTQ to EmbeddingGemma-300M using a CUAD-derived calibration set (sample 128–512 passages, sweep 3–5 calibration doses). Implement the validation-gated abstention criterion from arxiv-2610.27397v1 (D_func threshold) adapted for int8. Measure recall@3 overall and per hard-category vs fp16 baseline. Profile RAM consumption on-device (or Apple Silicon simulator). Compare collapse rate across doses vs the 4-bit parent's reported rate.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

Adopt if H1 (recall@3 ≥60.9%) AND H2 (≥150MB freed) AND H3 (gate passes ≥4/5 doses). Reject if recall@3 drops >1 point below baseline or RAM saving <100MB. Inconclusive if H1 passes but H2 or H3 fail — warrants a calibration dose tuning follow-up.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.55  ·  est. effort 1-2 weeks

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

- Engine idea id: `evo-g2-2` · technique: constraint-relax · attacks: OP-3
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.6 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **NOT_VALIDATABLE** · sub-labs confirmed - [-] · compose-retest - · slice-faithfulness-risk -
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
