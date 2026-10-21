# PoC (proposed): Does adding a simple abstention/confidence-gating step — where the LLM…

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

Does adding a simple abstention/confidence-gating step — where the LLM is prompted to decline to answer when retrieved chunks score below a similarity threshold — reduce false-positive clause surfacing on CUAD absent-clause items by ≥10 percentage points without reducing recall@3 on answerable items by more than 2 points?

## Why it matters here

- DeclineCraft demonstrates that retrieval itself is the primary lever for CAR improvement (single-shot retrieval raised CAR in 38/40 model configurations), suggesting a lightweight retrieval-confidence gate is more reliable than relying on generator-level uncertainty.
- If the gating step works, it directly addresses the unmeasured over-retrieval problem (OP-4) and could prevent the LLM from hallucinating clause text for absent categories, improving key-fact accuracy on the full CUAD set.
- The mechanism requires no new models or RAM — only a similarity threshold check on already-computed cosine scores — making it trivially compatible with our 6GB budget.

## Hypothesis

DeclineCraft's finding that retrieval context drives abstention was demonstrated on Minecraft text with large LLMs; we test whether a similarity-threshold gate on EmbeddingGemma cosine scores (e.g., if max(top-3 cosine) < τ, instruct Qwen to decline) replicates the abstention-improvement finding on CUAD absent-clause items with a 1.5B generator — an unverified transfer across domain, model scale, and retrieval architecture.

- H1: A cosine similarity gate (threshold τ swept over {0.3, 0.4, 0.5, 0.6}) reduces false-positive clause surfacing on absent-clause CUAD items by ≥10 percentage points at the optimal τ relative to no gate.
- H2: At the optimal τ, recall@3 on answerable CUAD items degrades by ≤2 percentage points vs. the current 61.4% baseline (i.e., remains ≥59.4%).
- H3: Qwen2.5-1.5B correctly abstains (outputs a non-answer) on ≥60% of gated (below-threshold) queries, confirming that the gate instruction is followed at 1.5B scale.

## Method

Reuse PoC 007/013 harness. (1) Identify absent-clause items in CUAD (gold = 'Not present'). (2) For each query, compute max cosine similarity across top-3 retrieved chunks from EmbeddingGemma. (3) If max cosine < τ, prepend system prompt: 'The retrieved context does not contain relevant information. Decline to answer and state the clause is not found.' (4) Sweep τ ∈ {0.3, 0.4, 0.5, 0.6}. (5) Measure false-positive retrieval rate and Qwen abstention rate on absent items; measure recall@3 and key-fact accuracy on answerable items. Compare to no-gate baseline. All on-device; no new models.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT if H1 and H2 both hold at the same τ (false-positive rate down ≥10 pp AND recall@3 ≥59.4%); REJECT if H2 fails (recall@3 drops >2 pp) or H1 improvement is <5 pp at all τ; INCONCLUSIVE if H3 fails (abstention rate <40%), indicating the generator ignores the gate and the mechanism is not testable with 1.5B.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 2-4 days

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

- Engine idea id: `arxiv-2610.28340v1-idea-3` · technique: extraction · attacks: OP-4
- Gates (0–10): G1 6.25 · G2 6.5 · G3 6.75 · null-control Δ6.25 (real 6.5 vs null 0.25)
- Tournament: rank 5, elo 984.0 · priority 📊 MEDIUM (6.907061790668348)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
