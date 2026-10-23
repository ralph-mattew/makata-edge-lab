# PoC 030: Expanded per-sub-query candidate pool before union (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, pool-size sweep) |
| Verdict | **Inconclusive — best hard-category result in the series, but short of the +10 bar.** Widening the per-sub-query pool to **N=2** before union lifts hard-mean recall@3 to **39.3** — **+3.7 over PoC-016 decomposition** and +6.3 over the single-query baseline, with overall +0.8 — the highest hard-mean the lab has reached. But it misses H1 (+10 over raw) and H2 (Exclusivity 23% < 30). H4 confirmed: **N=2 is optimal** (N≥3 inflates distractors). Notably it recovers the Change-of-Control regression decomposition introduced (54→63). A free, positive refinement of the proven decomposition lever — not a solution. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Synthesized (evolutionary recombination: PoC-016 template decomposition × wider candidate pool); 2026-10-23 ideation-engine DIVERGENT scan. |
| Registered | 2026-10-23 (this draft, before the first run) |

## Question

Does combining category-conditioned template sub-queries (from Parent 2) with an expanded candidate pool per sub-query (from Parent 1) — retrieving top-N candidates per sub-query before union-merging down to K=3 — lift per-category recall@3 on Exclusivity, Non-Compete, and Change-of-Control by ≥10 percentage points over the single-query baseline, without regressing overall recall@3?

## Why it matters here

- PoC-016 showed template decomposition moved Exclusivity from 7%→24% (+17pp) but fell short of the +10 hard-mean bar (+6 hard mean); the residual misses may be cases where the right chunk is retrieved by a sub-query at rank 4-5 but discarded when we cap at top-1 per sub-query before union — widening the per-sub-query candidate pool before the union step could recover these.
- Parent 1's insight is that pool size relative to document length governs evidence-coverage loss; applied per sub-query rather than globally, a modest pool expansion (top-3 or top-5 per sub-query, union then re-rank to K=3 total) diversifies the retrieval surface without inflating distractors the way naive top-K increase does (PoC-009 failure mode), because sub-query specificity pre-filters for relevant chunks.

## Hypothesis

PoC-016 took only top-1 per sub-query before union, meaning a relevant chunk at rank 2-5 for a given sub-query is permanently discarded even if no other sub-query surfaces it. Expanding the per-sub-query candidate pool to top-N (N ∈ {2, 3, 5}) before the union step — then re-ranking/deduplicating the union to final K=3 — should recover those near-miss chunks for hard categories where contract surface-form variation spreads relevant evidence across several ranks. This pool-widening-per-sub-query interaction is untested in our stack and is not proposed by either parent alone.

- H1: Hard-mean recall@3 (Exclusivity + Non-Compete + Change-of-Control) improves by ≥10pp over single-query baseline (current hard mean: ~11-17% depending on category) when using template sub-queries with per-sub-query pool N=3, union-merged, re-ranked to K=3.
- H2: Exclusivity recall@3 reaches ≥30% (PoC-016 decomp alone: 24%; single-query baseline: 7%).
- H3: Overall recall@3 does not regress by more than 2pp vs the PoC-016 decomp-alone result.
- H4: There exists an optimal per-sub-query pool size N* ∈ {2, 3, 5} beyond which distractor inflation degrades hard-category performance, identifiable by sweeping N.

## Method

Reuse the PoC-016 experiment harness and CUAD dataset (1,325 items). Use the same 2-3 static sub-query templates per hard category from PoC-016. Sweep per-sub-query candidate pool size N ∈ {1 (PoC-016 baseline), 2, 3, 5}. For each N: retrieve top-N chunks per sub-query, take union of all retrieved chunks (deduped by chunk_id), then select final K=3 by re-ranking the union by max sub-query similarity score. Measure per-category recall@3 (Exclusivity, Non-Compete, Change-of-Control) and overall recall@3 vs single-query baseline and vs PoC-016 decomp (N=1). No on-device generation required.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the per-sub-query candidate pool size N ∈ {1 (=PoC-016), 2, 3, 5} before the union+rerank to K=3. **Held fixed:** EmbeddingGemma hybrid 0.9/0.1, the PoC-016 decomposition templates, the PoC-014 chunk index, final K=3, the eval set. **Measurements:** per-category + overall recall@3 vs the single-query (raw) baseline and the N=1 decomposition baseline. **Repetitions:** deterministic → single pass.

## Decision rule

Adopt (recommend productionising template decomp with optimal N) if H1 (hard-mean ≥+10pp over single-query baseline) AND H3 (overall regression ≤2pp); reject if hard-mean gain <+3pp over PoC-016 decomp-alone at all N; else inconclusive — report optimal N and per-category breakdown for targeted follow-up.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1 week

## Harness

`subquery-pool.py` (committed vectors; no model/server): for each hard-category item, rank chunks per
decomposition sub-query (hybrid 0.9/0.1), take **top-N per sub-query**, union+dedupe, re-rank the union
by max sub-query hybrid score, take final K=3. Sweep N ∈ {1,2,3,5}. Non-hard items use the raw
single-query path. recall@3 = top-3 cover ≥50% of the gold span.

## Results

MEASURED on the host, full CUAD (1,316 items), recall@3.

| Arm | overall | hard-mean | Exclusivity | Non-Compete | Change Of Control |
|---|---|---|---|---|---|
| raw (single-query) | 61.8 | 33.0 | 7 | 25 | 67 |
| decomp N=1 (PoC-016) | 62.4 | 35.7 | 20 | 33 | 54 |
| **decomp N=2 (best)** | 63.2 | **39.3** | 23 | 32 | 63 |
| decomp N=3 | 63.2 | 39.0 | 24 | 28 | 65 |
| decomp N=5 | 63.2 | 39.0 | 24 | 28 | 65 |

- **H1 (hard-mean ≥ +10 over raw):** FAIL — best +6.3 (N=2). MEASURED.
- **H2 (Exclusivity ≥ 30):** FAIL — 23% (N=2), 24% (N=3/5). MEASURED.
- **H3 (overall regression ≤ 2 vs decomp-N1):** PASS — overall *improves* +0.8. MEASURED.
- **Gain over decomp-N1:** +3.7 hard-mean at N=2 (≥ the +3 reject floor → not rejected). MEASURED.
- **H4 (optimal N):** confirmed — **N=2** is best; N≥3 trades hard-mean down (distractor inflation),
  exactly the predicted knee. MEASURED.

Per-N figures in `results/subquery-pool.json`.

## Verdict

**Inconclusive — a small, real, free refinement of the proven lever; not a solution.** Expanding the
per-sub-query pool to N=2 before the union is the **first mechanism to improve on PoC-016 decomposition**
(hard-mean 35.7 → 39.3, +3.7) and gives the **highest hard-mean the lab has recorded (39.3)**, while
*also* nudging overall recall up (+0.8) and **recovering the Change-of-Control regression that
decomposition alone caused** (67 raw → 54 at N=1 → 63 at N=2). But it falls well short of the
pre-registered +10 ambition and does not get Exclusivity to 30%. Per the decision rule (adopt needs H1
∧ H3; reject needs <+3 over decomp at all N) it is **inconclusive**.

Practically: **adopt N=2 as the decomposition default** — it is zero-cost (same vectors, one extra
candidate per sub-query), strictly ≥ N=1 on hard-mean and overall, and fixes decomposition's CoC
side-effect. It does not change the strategic picture: the hard categories remain ~39% hard-mean,
so the answer step (PoC-018) is still where the larger gains must come from. The per-category split
persists — Exclusivity responds to decomposition+pooling (7→24), Non-Compete peaks at N=1 (gold is
mis-ranked, not missing — cf. PoC-025/027), Change-of-Control is hurt by decomposition and only
recovered by pooling.

## Limits

- **Static PoC-016 templates** (2–3 sub-queries/category); learned or more numerous sub-queries are
  untested.
- **recall@3 only** — the answer step is PoC-017/018's domain; a retrieval gain this size may not
  convert (PoC-017 showed hard-category recall gains convert weakly to answer quality).
- **Hard categories only** use decomposition; overall is dominated by the unchanged fact categories.

## Reproduce

```bash
cd poc/030-subquery-pool-expansion
python3 subquery-pool.py        # committed vectors; no model/server
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g2-6` · technique: facet-recombination|structured-blend · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.65 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 2 [cuad_hard:CONFIRMED; cuad_hard:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-23. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
