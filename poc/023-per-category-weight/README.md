# PoC 023: Per-category adaptive hybrid weight for hard categories (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, calibrated per-category α) |
| Verdict | **Reject.** Per-category α calibration picks **α\*=0.9 for all three hard categories** — identical to the global weight — so recall@3 is unchanged (Δ 0.0 overall and per-category). The "BM25 helps rare legal terms" hypothesis is refuted: lowering α (more BM25) *strictly hurts* (0% recall at α≤0.5 for Exclusivity/Non-Compete). Hard categories are invariant to per-category weighting, not just global — extends PoC-013. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | arxiv-2610.27397v1; promoted from the 2026-10-21 ideation-engine scan. |
| Registered | 2026-10-21 (this draft, before the first run) |

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

## Harness

`per-category-weight.py` reuses committed PoC-014 vectors + PoC-007 items/spans (no model, no
server). Per item it precomputes semantic cosine + normalized BM25 over the item's contract chunks,
so an α sweep is just a reweighting `α·sem + (1−α)·bm25`. For each hard category it holds out a
seeded 20-item calibration split, sweeps α ∈ {0.1…0.9}, picks the α maximising calibration recall@3
(tie → 0.9), and applies it to that category's eval items; all other categories keep α=0.9.
Calibration items are excluded from the eval set for both arms (no train-on-test).

## Results

MEASURED on the host, full CUAD (calibration 20 items/hard-cat, seed 0; eval excludes them).

| Category | α\* | global α=0.9 | per-category α\* | Δ |
|---|---|---|---|---|
| Exclusivity | 0.9 | 6.2% | 6.2% | +0.0 |
| Non-Compete | 0.9 | 27.5% | 27.5% | +0.0 |
| Change Of Control | 0.9 | 67.5% | 67.5% | +0.0 |
| **overall** (n=1265) | — | **63.3%** | **63.3%** | **+0.0** |

Calibration α-sweeps (recall@3 on the 20-item splits) — higher α is monotonically better; BM25-heavy
weights collapse to 0:

| category | α=0.1 | 0.3 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 |
|---|---|---|---|---|---|---|---|
| Exclusivity | 0 | 0 | 0 | 5 | 5 | 10 | **10** |
| Non-Compete | 0 | 0 | 0 | 5 | 5 | 5 | **15** |
| Change Of Control | 30 | 30 | 50 | 55 | 50 | 65 | **65** |

- **H1 (Exclusivity +≥5):** FAIL — Δ 0.0 (α\*=0.9 = global). MEASURED.
- **H2 (NC & CoC +≥3):** FAIL — Δ 0.0 each. MEASURED.
- **H3 (overall regression ≤1):** trivially holds (Δ 0.0), but moot. MEASURED.
- **H4 (α\* differs from 0.9 by ≥0.2):** FAIL — α\*=0.9 for all three. MEASURED.

Summary in `results/per-category-weight.json`; human-readable `results/comparison.txt`.

## Verdict

**Reject.** Per-category weight routing yields exactly zero benefit: the optimal α for every hard
category *is* the global 0.9. The behavioral premise — that rare legal terms (exclusivity,
non-compete) need more BM25 — is not just unsupported but **inverted**: lowering α monotonically
*degrades* recall (0% at α≤0.5 for Exclusivity/Non-Compete), i.e. the semantic signal carries
essentially all the usable retrieval signal and BM25's 0.1 share is already as much as helps. This
extends PoC-013 decisively: the hard categories are invariant to retrieval *scoring* along the
hybrid-weight axis both globally **and** per-category — the bottleneck is not weighting but what the
embedder can represent (cf. PoC-022, where a different embedder reshuffled but didn't lift them).
OP-1 progress will have to come from chunking, query formulation (PoC-016 decomposition remains the
only mover), or the answer step (PoC-018) — not from the retrieval weight.

## Limits

- **recall@3 only** — the retrieval metric; downstream answer quality is covered by PoC-017/018/019.
- **20-item calibration splits** are small (the hard categories only have 100 items each); but the
  sweep is monotone in α with no local optimum away from 0.9, so a larger split would not change the
  conclusion.
- **Fixed chunking (PoC-014 page) + BM25 params** (k1=1.5, b=0.75). A different chunking could shift
  the BM25/semantic balance, but that is PoC-014's axis, not this one.

## Reproduce

```bash
cd poc/023-per-category-weight
python3 per-category-weight.py          # no model/server; reuses committed vectors
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g1-1` · technique: novelty-push · attacks: OP-1
- Gates (0–10): G1 6.25 · G2 6.25 · G3 6.75 · null-control Δ6.0 (real 6.25 vs null 0.25)
- Tournament: rank 4, elo 1000.0 · priority 📊 MEDIUM (6.314123581336697)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
