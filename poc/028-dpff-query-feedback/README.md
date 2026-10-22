# PoC 028: Directional Posterior Feedback Fusion (DPFF) — query-embedding PRF for hard categories (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD) |
| Verdict | **Reject.** Pseudo-relevance feedback on the query embedding adds essentially nothing over PoC-016 decomposition: best hard-mean recall@3 39.7 vs 39.3 (**Δ +0.4**, bar is +10), overall +0.1. Larger step sizes *hurt*, and **Non-Compete regresses 36→33**. This is the classic PRF failure mode — hard-category top-3 precision is too low (Exclusivity 7%, Non-Compete 25%), so nudging the query toward the top-3 centroid reinforces wrong chunks. Query *formulation* (decomposition/keywords) helps; query-embedding *feedback* does not. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Directional Posterior Feedback Fusion for Query Reformulation in Dense Retrieval (http://arxiv.org/abs/2610.29464v1) |
| Registered | 2026-10-22 (this draft, before the first run) |

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
- **Varies:** the query-embedding update — none (raw / PoC-016 decomp baselines) vs DPFF (α ∈ {0.1, 0.3, 0.5}, rounds ∈ {1, 2}), applied to the raw query and to each decomposed sub-query. **Held fixed:** EmbeddingGemma hybrid 0.9/0.1, the PoC-014 chunk index, top-3, the PoC-016 decomposition templates, the eval set. **Measurements:** per-category + overall recall@3 (hard categories called out), vs raw and decomp baselines. **Repetitions:** deterministic vector arithmetic → single pass; contract-level bootstrap CI.

## Decision rule

If H1 (+≥10 hard-mean points over decomp) and H3 (latency ≤200ms) hold: adopt DPFF as retrieval refinement layer for hard categories. If H1 < +5 points: reject (decomp-only is simpler and already approved). Otherwise (H1 in +5..+10): inconclusive, run ablation over alpha values.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.42  ·  est. effort 1 week

## Harness

`dpff.py` runs pure vector arithmetic on the committed EmbeddingGemma vectors (raw queries,
PoC-016 decomposed sub-queries, PoC-014 chunk vectors) — no model, no server. Per round:
`q' = normalize(q + α·(centroid(top-k chunks) − q))`, then re-retrieve. Applied to the raw query
and (the headline) to each decomposed sub-query before PoC-016 max-pooling. Baselines: raw hybrid
and PoC-016 decomposition.

## Results

MEASURED on the host, full CUAD (1,316 items, committed vectors). recall@3, hybrid 0.9/0.1.

| Arm | overall | hard-mean | Exclusivity | Non-Compete | Change Of Control |
|---|---|---|---|---|---|
| raw (baseline a) | 61.8 | 33.0 | 7 | 25 | 67 |
| decomp — PoC-016 (baseline b) | 63.2 | 39.3 | 23 | 36 | 59 |
| decomp + DPFF (α0.1, r1) **best** | 63.3 | **39.7** | 25 | 33 | 61 |
| decomp + DPFF (α0.3, r1) | 62.9 | 38.0 | 24 | 30 | 60 |
| decomp + DPFF (α0.5, r2) | 62.9 | 38.0 | 24 | 28 | 62 |

- **H1 (hard-mean ≥ +10 over decomp):** FAIL — best Δ = **+0.4**. MEASURED.
- **H2 (overall regression ≤ 1):** holds (+0.1), but moot. MEASURED.
- **H3 (latency ≤ 200ms):** trivially fine — vector arithmetic — but irrelevant given H1 fails.
- Larger α monotonically *hurts*; **Non-Compete regresses** (36 → 33 at best, → 28 at α0.5). MEASURED.

Summary in `results/dpff.json`; human-readable `results/comparison.txt`.

## Verdict

**Reject.** Directional pseudo-relevance feedback on the query embedding does not help — best hard-mean
gain is +0.4 over decomposition (bar +10), and it actively *hurts* Non-Compete. The cause is the
textbook PRF precondition failure: PRF only helps when the initial top-k is mostly relevant, but the
hard categories have poor top-3 precision (Exclusivity 7%, Non-Compete 25%), so the centroid of the
top-3 is dominated by *wrong* chunks and the updated query drifts toward them. Query **formulation**
(PoC-016 decomposition, PoC-015 keyword expansion) remains the only retrieval-side mover; query
**embedding feedback** is not a usable layer on top of it.

**Standing OP-1 picture (updated):** embedder swap (022), hybrid weight (023), cross-encoder reranking
(027), and now query-embedding feedback (028) have all failed on the hard categories. Every
retrieval-*scoring* and retrieval-*refinement* lever is exhausted; the durable movers are query
formulation (015/016) and the answer step (018). Future OP-1 ideas should target those, a
legal-domain-tuned component, or better chunking — not another retrieval-scoring tweak.

## Limits

- **PRF variants are not exhaustive** — direction-only Rocchio with α∈{0.1,0.3,0.5}, 1–2 rounds. A
  relevance-model/RM3 term-weighting variant or negative feedback is untested, but the precision
  precondition is the same, so a large reversal is unlikely.
- **recall@3 only** (retrieval metric); the answer step is PoC-017/018's domain.
- **Fixed chunking + committed vectors** (PoC-014 page) — a different chunking could change top-3
  precision and thus PRF's viability, but that is PoC-014's axis.

## Reproduce

```bash
cd poc/028-dpff-query-feedback
python3 dpff.py        # committed vectors; no model/server
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `synth-idea-1` · technique: problem×method · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.35 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [semantic:NULL; conjunctive:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
