# PoC (proposed): Does applying a calibrated abstention signal — analogous to DeclineCra…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | DeclineCraft: A RAG Abstention Benchmark for Jointly Measuring Combined Retrieval and Parametric Knowledge (http://arxiv.org/abs/2610.28340v1) |
| Registered | not yet — proposed 2026-10-21 |

## Question

Does applying a calibrated abstention signal — analogous to DeclineCraft's Correct Abstention Rate — to our hybrid retrieval stack reduce false-positive clause surfacing rate on category-absent CUAD items by ≥30% without degrading recall@3 on answerable items by more than 2 points?

## Why it matters here

- OP-4 (absent-clause false retrieval) is entirely unmeasured in our stack; the first measurement alone is high-value for Xylo's production use case where falsely surfacing a non-existent exclusivity clause is a legal liability
- DeclineCraft provides both a benchmark design pattern (unanswerable questions with audited parametric exposure) and a single-shot retrieval-confidence signal that our harness can implement without generation — directly applicable to our extractive pipeline

## Hypothesis

DeclineCraft tested abstention in a generative LLM setting; we transfer the abstention signal to the retrieval layer by using a retrieval-confidence threshold (max cosine similarity of top-1 chunk to query) as a surrogate for 'no relevant clause found'. If max-sim < threshold T, we predict 'clause absent' rather than returning chunks. We test whether calibrating T on a held-out CUAD absent-clause set reduces false-positive surfacing without hurting recall@3 on answerable items. No generation required.

- H1: False-positive retrieval rate on CUAD category-absent items is measurably high (>20%) at current settings — establishing the baseline OP-4 measurement
- H2: A calibrated max-sim threshold T reduces false-positive rate by ≥30% on absent items
- H3: Recall@3 on answerable items degrades by ≤2 points at the chosen T
- H4: Hard-category absent items (Exclusivity, Non-Compete) show especially high false-positive rates, explaining part of the OP-1 difficulty

## Method

Reuse PoC-007 harness. Step 1: identify CUAD items where the gold answer is 'not present / not applicable' — these form the absent-clause test set. Step 2: measure current false-positive retrieval rate (top-1 chunk returned with sim > 0.5 for an absent clause). Step 3: sweep threshold T over [0.4, 0.5, 0.6, 0.7]; for each T, measure false-positive rate on absent items and recall@3 on answerable items. Step 4: select T that maximizes F1(abstention accuracy, recall@3 preservation). Report per-category breakdown including hard categories.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

If H1 confirmed AND H2 + H3 hold at some T: adopt threshold gating as a production safety feature; if false-positive baseline <10% (OP-4 not a real problem): deprioritize; if recall@3 drops >3 points at any T achieving H2: reject threshold approach

## Expected outcome (engine estimate, not a result)

likely to confirm H1 (high baseline false-positive) and partially meet H2/H3 — adopt with calibration  ·  confidence 0.6  ·  est. effort 1 week

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

- Engine idea id: `synth-idea-3` · technique: problem×method · attacks: OP-4
- Gates (0–10): G1 6.25 · G2 7.0 · G3 7.25 · null-control Δ6.75 (real 7.0 vs null 0.25)
- Tournament: rank 2, elo 1016.0 · priority 📊 MEDIUM (8.121185372005046)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
