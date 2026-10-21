# PoC (proposed): Does per-category adaptive semantic weight selection — choosing a dist…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | arxiv-2610.27397v1 |
| Registered | not yet — proposed 2026-10-21 |

## Question

Does per-category adaptive semantic weight selection — choosing a distinct hybrid retrieval weight for Exclusivity, Non-Compete, and Change-of-Control queries based on a small held-out calibration set — lift hard-category recall@3 by ≥5 points over the globally-tuned 0.9 weight, without degrading overall recall@3 by more than 1 point?

## Why it matters here

- OP-1 is the lab's single highest-value open problem: Exclusivity recall@3 has been stuck at ~11% across every global retrieval-scoring sweep (PoC-013), and no mechanism so far has moved it at the retrieval stage — per-category weighting is an unexplored axis that global sweeps cannot surface
- PoC-013 confirmed that a global α=0.9 is optimal overall but leaves hard categories completely unaddressed; if hard categories need a different semantic/BM25 balance (e.g. BM25 term-matching matters more for 'exclusivity' as a rare legal term), a per-category weight can exploit this without touching chunking or query decomposition

## Hypothesis

The unverified leap: hard categories are weight-invariant to GLOBAL sweeps, but may respond to CATEGORY-SPECIFIC weights chosen via a small per-category calibration set (e.g. 20–30 labeled CUAD items per hard category). Specifically, we hypothesize that BM25 carries disproportionate signal for rare legal terms like 'exclusivity' and 'non-compete' (which appear verbatim in clause headings), so a lower semantic weight (e.g. α≈0.5–0.6) on hard-category queries — while keeping α=0.9 globally — could unlock term-matching recall that the high-semantic-weight regime suppresses. This has not been tested by any source or prior PoC.

- H1: Per-category α (swept 0.1–0.9 in steps of 0.1 for each hard category independently) lifts Exclusivity recall@3 by ≥5 points over the global-α=0.9 baseline (current: ~11%)
- H2: Non-Compete and Change-of-Control recall@3 each improve by ≥3 points over global-α=0.9 baseline
- H3: Overall recall@3 does not regress by more than 1 point from the 58.1% global-α=0.9 result (hard categories are a small fraction of total items)
- H4: The optimal per-category α for hard categories differs from 0.9 by ≥0.2, confirming the behavioral hypothesis that hard categories need a different weight regime

## Method

Reuse the existing hybrid retrieval harness (EmbeddingGemma + BM25, CUAD 300-item evaluation set). Implement a per-query-category routing layer that selects α based on the CUAD category label of the query. For each of the three hard categories, sweep α independently from 0.1 to 0.9 (step 0.1) on a 20-item held-out calibration split; select the α that maximizes recall@3 on that split. For all other categories, use α=0.9. Evaluate on the remaining items. Report per-category recall@3 and overall recall@3. No new models, no new chunking — only routing logic on top of existing retrieval.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

Adopt if H1 (Exclusivity +≥5 points) AND H3 (overall regression ≤1 point). Reject if Exclusivity gain <3 points or overall regression >2 points. Inconclusive if Exclusivity gain is 3–4 points (continue to OP-1 chunking/query-formulation work).

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.35  ·  est. effort 1 week

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

- Engine idea id: `evo-g1-1` · technique: novelty-push · attacks: OP-1
- Gates (0–10): G1 6.25 · G2 6.25 · G3 6.75 · null-control Δ6.0 (real 6.25 vs null 0.25)
- Tournament: rank 4, elo 1000.0 · priority 📊 MEDIUM (6.314123581336697)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
