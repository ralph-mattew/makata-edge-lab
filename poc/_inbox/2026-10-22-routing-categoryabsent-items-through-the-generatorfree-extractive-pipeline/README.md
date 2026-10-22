# PoC (proposed): Does routing category-absent items through the generator-free extracti…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | OnQ (on-policy QAT distillation for Qwen3) + DeclineCraft (retrieval vs. abstention on unanswerable queries) |
| Registered | not yet — proposed 2026-10-22 |

## Question

Does routing category-absent items through the generator-free extractive pipeline (PoC-018 adopted mechanism) instead of Qwen2.5-1.5B generation — combined with a cosine-score abstention threshold — yield a Correct Abstention Rate (CAR) ≥10 percentage points higher than the current hybrid-retrieval + Qwen generation stack on CUAD absent-clause items?

## Why it matters here

- PoC-018 showed the tiny Qwen2.5-1.5B generator actively hurts answer quality — the same mechanism (over-confident generation on weak evidence) is the most plausible driver of false positives on absent-clause items; replacing generation with an extractive step plus a confidence gate could suppress false positives without adding RAM
- OP-4 is entirely unmeasured in the extractive-answer regime: we know generator-free extraction wins for answerable hard categories, but whether it also reduces over-retrieval false claims on category-absent items is unknown and directly actionable

## Hypothesis

The unverified leap: for CUAD items where the target clause category is absent from the contract, the PoC-018 extractive pipeline (no Qwen generation) will produce lower-confidence cosine scores for top-retrieved chunks than for answerable items, and a simple cosine-score threshold gate (e.g., max chunk cosine < τ → abstain) applied atop the extractive pipeline will yield CAR ≥10pp higher than the current Qwen-generation stack — because the generator is the false-confidence source, not the retrieval itself. No source establishes this threshold mechanism or its transfer to legal absent-clause detection.

- H1: Extractive pipeline (PoC-018) + cosine-threshold abstention gate achieves CAR ≥10pp higher than Qwen-generation baseline on CUAD absent-clause items (current CAR: unmeasured, estimated ~40–55% based on OP-4 gap)
- H2: The optimal threshold τ (determined by sweep on a held-out calibration split) generalises across hard categories (Exclusivity, Non-Compete, Change-of-Control absent items) without per-category tuning
- H3: The abstention gate does NOT regress recall@3 on answerable items by more than 2pp (false-abstention constraint)

## Method

Reuse existing experiment harness and CUAD dataset. (1) Identify all category-absent items for Exclusivity, Non-Compete, Change-of-Control (~150–200 items from full CUAD). (2) Run PoC-018 extractive pipeline on these items; record max cosine score of top-3 retrieved chunks per query. (3) Sweep threshold τ ∈ {0.30, 0.35, 0.40, 0.45, 0.50} on a 50% calibration split; select τ maximising CAR while keeping false-abstention on answerable items ≤2pp regression. (4) Evaluate on held-out 50% split: measure CAR (primary) and false-abstention rate on answerable hard-category items (constraint). (5) Compare to current Qwen-generation baseline CAR on same absent-clause items as the control arm. No new model training required — pure inference + threshold search on adopted stack.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

Adopt if H1 (CAR +≥10pp vs. Qwen baseline) AND H3 (answerable recall regression ≤2pp). Reject if H1 <+5pp. Inconclusive if +5pp ≤ H1 < +10pp or H3 violated.

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

- Engine idea id: `evo-g2-3` · technique: facet-recombination · attacks: OP-4
- Gates (0–10): G1 6.5 · G2 6.0 · G3 6.25 · null-control Δ5.75 (real 6.0 vs null 0.25)
- Tournament: rank 6, elo 981.1 · priority 📊 MEDIUM (7.57)
- Provenance: idea-evolution-engine (private) scan 2026-10-22. Gate-approved + null-control-screened, NOT yet empirically validated.
