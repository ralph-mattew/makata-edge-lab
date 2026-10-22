# PoC (proposed): Does limiting the hybrid candidate pool size (retrieve fewer initial c…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.


| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | Scan or Index? large Evidence Coverage, Answer Quality, and Cost in Long-Document RAG (http://arxiv.org/abs/2610.28957v1) |
| Registered | not yet — proposed 2026-10-22 |

## Question

Does limiting the hybrid candidate pool size (retrieve fewer initial candidates before final top-3 selection) on CUAD change recall@3, and is there a pool size below which evidence is systematically lost for hard categories?

## Why it matters here

- The paper finds that for shorter documents (QASPER articles already fit within the hybrid candidate pool), scanning beyond the pool adds no benefit — implying pool size is the binding constraint, not scanning depth.
- CUAD contracts are long (median 25-word chunks across 397 docs); understanding whether our hybrid pool is already capturing the relevant evidence or discarding it during candidate reduction could explain why hard categories are invariant to retrieval scoring.
- A systematic pool-size sweep is cheap to implement and could separate two hypotheses: (a) evidence is never retrieved (chunk/query problem) vs (b) evidence is retrieved but then discarded (scoring/pool problem).

## Hypothesis

Source shows that candidate pool size relative to document length is a key determinant of evidence coverage loss; we test whether sweeping the hybrid candidate pool size (e.g., top-5, top-10, top-20, top-50 before final top-3 selection) on CUAD reveals a pool-size threshold below which hard-category evidence is systematically discarded — unverified on our stack.

- H1: Increasing the hybrid candidate pool from top-10 to top-30 before final top-3 selection improves overall recall@3 by ≥2 points (current: 61.4%) — suggesting evidence is retrieved but later discarded.
- H2: For hard categories (Exclusivity, Non-Compete, Change-of-Control), recall@3 remains below 20% regardless of pool size, confirming the bottleneck is upstream (chunk boundaries / query formulation, not pool truncation).
- H3: Latency increase from larger pool sizes is linear and remains under 1 second additional per query on iPhone 15 Pro.

## Method

Reuse PoC-007/013 harness. Implement pool-size sweep: for each candidate pool size k ∈ {3, 5, 10, 20, 30, 50}, retrieve top-k via 0.9/0.1 hybrid then take top-3 by score. Measure overall recall@3 and per-category recall@3 for all CUAD categories including Exclusivity, Non-Compete, Change-of-Control. Also measure latency per pool size. Baseline: current pipeline (pool=10 or default, 61.4% overall recall@3).

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

If H1 holds (pool increase lifts overall recall@3 ≥+2 points): this reveals a pool-truncation problem — adopt larger pool and escalate to OP-1 investigation. If H2 holds AND H1 does not (hard categories stay low even with larger pool): confirms bottleneck is chunking/query, not pool size — reject pool expansion, prioritise PoC-014/015. INCONCLUSIVE if overall improves but hard categories also improve slightly (mixed signal).

## Expected outcome (engine estimate, not a result)

reject  ·  confidence 0.55  ·  est. effort 2-3 days

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

- Engine idea id: `arxiv-2610.28957v1-idea-7` · technique: extraction · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.72 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [numeric:POINT_WINS_ONLY; conjunctive:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
