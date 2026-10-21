# PoC (proposed): Does validation-gated PTQ calibration of EmbeddingGemma-300M to 4-bit …

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | When PTQ Calibration Helps or Hurts: Dose-Driven Collapse and Validation-Gated Abstention in Quantized Text Embedders (http://arxiv.org/abs/2610.27397v1) |
| Registered | not yet — proposed 2026-10-21 |

## Question

Does validation-gated PTQ calibration of EmbeddingGemma-300M to 4-bit weights preserve recall@3 within 1 point of the fp16 baseline while freeing ≥200MB RAM on the 6GB iPhone 15 Pro budget?

## Why it matters here

- OP-3 identifies EmbeddingGemma's 600MB as the single largest fixed RAM cost; freeing 200-300MB would allow loading a larger LLM (e.g. Qwen2.5-3B) or longer context window without exceeding 6GB
- The PTQ paper's key finding — that calibration dose drives the outcome from gain to catastrophic collapse, and that a validation-gated abstention can detect collapse before deployment — directly solves our fear of 'does 4-bit quantization hurt recall@3 on CUAD?'

## Hypothesis

The paper tested EmbeddingGemma-300M directly — its findings on calibration dose and validation gating transfer most directly to our stack. We test whether a low-dose 4-bit PTQ calibration run on a CUAD-derived calibration set (retrieval relevance supervision) passes the validation gate and preserves our 61.4% recall@3 baseline, yielding a quantized embedder with ≤1 point recall loss and ≥200MB RAM savings.

- H1: 4-bit PTQ of EmbeddingGemma-300M with low-dose calibration on CUAD retrieval pairs passes the validation gate (D_func below collapse threshold)
- H2: Quantized embedder recall@3 is within 1 point of fp16 baseline (≥60.4%)
- H3: Quantized embedder occupies ≤400MB RAM (vs 600MB fp16), freeing ≥200MB
- H4: Key-fact accuracy does not degrade by more than 2 points (≥65.9%)

## Method

Reuse PoC-007/008 harness. Step 1: prepare a CUAD retrieval calibration set (200-400 query-chunk relevance pairs from training split). Step 2: apply 4-bit weight PTQ to EmbeddingGemma-300M at three calibration doses (low/medium/high, varying number of calibration steps). Step 3: compute D_func (functional displacement) for each run and apply validation gate from the paper. Step 4: for runs that pass the gate, measure recall@3 on the full CUAD 1,325-item eval set. Step 5: profile RAM on iPhone 15 Pro (CoreML). Compare to fp16 baseline on both recall@3 and key-fact accuracy.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

If H1 + H2 + H3 hold: adopt quantized embedder and reallocate freed RAM to larger LLM; if any dose fails the validation gate: use the gate to select the passing dose; if no dose passes the gate or recall@3 < 60.4%: reject quantization for EmbeddingGemma and close OP-3 as infeasible at 4-bit

## Expected outcome (engine estimate, not a result)

likely inconclusive — calibration may pass gate but CoreML 4-bit inference support is the unknown variable  ·  confidence 0.5  ·  est. effort 1-2 weeks

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

- Engine idea id: `synth-idea-4` · technique: constraint-driven inversion · attacks: OP-3
- Gates (0–10): G1 8.5 · G2 8.25 · G3 6.75 · null-control Δ8.0 (real 8.25 vs null 0.25)
- Tournament: rank 1, elo 1047.3 · priority 📊 MEDIUM (9.5)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
