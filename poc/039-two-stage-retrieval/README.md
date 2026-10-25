# PoC (proposed): Does a two-stage retrieval pipeline — (1) per-hard-category determinis…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

> ⚠️ **UNSCREENED (non-faithful screen) — routed to reality.** The micro-lab could not fairly test this idea: the available substrate was at ceiling (baselines [0.4639]) or high slice-faithfulness risk, so its 'null' is a FALSE null, not evidence the idea fails. It targets a harder slice than the screen can measure (e.g. hard-category recall) — the lab's real experiment is the judge. Carries only the gate signal.


| | |
|---|---|
| Status | host run (2026-10-25) |
| Verdict | reject |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | (synthesized) |
| Registered | not yet — proposed 2026-10-25 |

## Question

Does a two-stage retrieval pipeline — (1) per-hard-category deterministic sub-query templates each retrieving a larger candidate pool (N=10–20), followed by (2) a pool-size-aware union capped at K=3 final chunks — lift per-category recall@3 on Exclusivity, Non-Compete, and Change-of-Control by ≥10pp over the PoC-030 best (hard-mean 39.3), without regressing overall recall@3?

## Why it matters here

- PoC-030 showed that expanding the per-sub-query pool from N=1 to N=2 before union already recovered Change-of-Control regressions and set the highest hard-mean on record (39.3) — the headroom question is whether further pool expansion (N=5, N=10, N=20) combined with category-specific sub-query templates compounds these gains rather than diluting them.
- Parent 1 establishes that pool size relative to document length is a key determinant of evidence coverage: if hard-category gold chunks are sitting at rank 4–10 (as PoC-025 shows for Non-Compete), a larger per-sub-query candidate pool before union could capture them while the template diversification ensures at least one sub-query frames the clause correctly — attacking both the vocabulary-mismatch and the coverage-loss bottlenecks simultaneously.

## Hypothesis

Combining category-specific deterministic sub-query templates (2–3 templates per hard category, as in Parent 2) with a larger per-sub-query candidate pool (N=10–20, as motivated by Parent 1's pool-size analysis) before the union-capped-at-K=3 step will compound gains: the templates address vocabulary/framing mismatch, while the larger pool prevents evidence at ranks 4–10 from being discarded before the union. This specific combination — template expansion × pool-size sweep × union-cap-at-K=3 — has not been tested on our stack and is NOT established by any single parent.

- H1: Hard-mean recall@3 across Exclusivity, Non-Compete, Change-of-Control reaches ≥49.3 (current best: 39.3, target: +10pp).
- H2: Each individual hard category gains ≥10pp over the PoC-030 per-category figures (Exclusivity ≥17%, Non-Compete ≥X+10, Change-of-Control ≥63+10 raw).
- H3: Overall recall@3 does not regress by more than 1pp vs PoC-030 baseline.
- H4: A pool-size ablation (N=1, 2, 5, 10, 20) reveals the threshold at which hard-category gains plateau or reverse, providing diagnostic value independent of H1.

## Method

Reuse the existing CUAD experiment harness. Implement 2–3 deterministic clause-specific sub-query templates per hard category (e.g., for Exclusivity: 'exclusive rights granted to party', 'sole and exclusive license', 'exclusivity obligation of licensee'). For each sub-query, retrieve the top-N candidates (sweep N ∈ {2, 5, 10, 20}) using the existing 0.9/0.1 hybrid scorer. Take the union of all per-sub-query top-N candidate sets, deduplicate, re-rank by hybrid score, and select the final top-3. Measure recall@3 per category and overall. Run the pool-size sweep as an ablation within the same experiment. Compare against PoC-030 (N=2, no templates) and PoC-016 (templates, N=1) to isolate the contribution of each facet.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

Adopt if H1 (hard-mean ≥49.3) AND H3 (overall regression ≤1pp). Reject if hard-mean gain <5pp over PoC-030. Inconclusive if gain is 5–9pp — report the pool-size ablation curve as diagnostic for OP-1.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.35  ·  est. effort 1–2 weeks

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

- Engine idea id: `evo-g2-6` · technique: facet-recombination · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.52 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **null** · sub-labs confirmed 0 [cuad_hard:POINT_WINS_ONLY] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
