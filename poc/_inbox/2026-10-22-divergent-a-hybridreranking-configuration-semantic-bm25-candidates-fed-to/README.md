# PoC (proposed): Does a Hybrid+reranking configuration (semantic + BM25 candidates fed …

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

Does a Hybrid+reranking configuration (semantic + BM25 candidates fed to a lightweight cross-encoder reranker) raise recall@3 on CUAD hard categories (Exclusivity, Non-Compete, Change-of-Control) by ≥5 points over the current 0.9/0.1 hybrid baseline?

## Why it matters here

- PoC-013 showed hard categories are invariant to retrieval-weight tuning; a reranking step after candidate retrieval is a structurally different mechanism that could reorder within a fixed candidate pool and surface the correct chunk
- The paper found Hybrid+reranker achieved the highest evidence coverage (94.1%) on long documents, suggesting the combination captures evidence that either component alone misses
- If even a small lift in hard-category recall transfers, it unblocks the single highest-value bottleneck in the current system

## Hypothesis

The source ran hybrid+reranker on QASPER/textbook corpora with unspecified dense embedders and cloud-based rerankers (Jev, OpenAI Decisions); we test the same structural mechanism — a hybrid candidate pool reranked by a cross-encoder — using EmbeddingGemma 300M + BM25 candidates passed to a small cross-encoder (PoC-012 design) on CUAD, measuring per-category recall@3 on hard categories. This transfer is unverified because: corpus domain differs (legal vs scientific/textbook), the source's reranker is cloud-scale, and our candidate pool size and chunk length differ.

- H1: Hybrid+cross-encoder reranking raises overall recall@3 by ≥3 points above the 61.4% baseline (current: 61.4%)
- H2: Per-category recall@3 on at least one hard category (Exclusivity ~11%, Non-Compete, Change-of-Control) improves by ≥5 points over the 0.9/0.1 hybrid baseline
- H3: End-to-end latency per query on iPhone 15 Pro remains ≤4 seconds (cross-encoder inference budget)

## Method

Reuse PoC-012/PoC-007 harness on CUAD 1,325 Q&A items. Retrieve top-10 candidates via 0.9/0.1 hybrid (current baseline), then rerank with a small on-device cross-encoder (e.g. ms-marco-MiniLM-L6 quantised to fit ≤300MB). Return top-3 after reranking. Measure overall recall@3, per-category recall@3 for Exclusivity, Non-Compete, Change-of-Control, and wall-clock latency. Compare against baseline (61.4% recall@3). PoC-012 registered this device hypothesis; this PoC executes it with explicit hard-category focus.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT if H1 (≥3-point overall lift) AND H2 (≥5-point lift on ≥1 hard category) AND H3 (latency ≤4s). REJECT if overall recall@3 < 62.4% (less than +1 point). INCONCLUSIVE if H1 holds but H2 does not, or H2 holds but H3 fails.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1-2 weeks (cross-encoder quantisation + integration into existing harness + per-category evaluation)

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

- Engine idea id: `arxiv-2610.28957v1-idea-6` · technique: extraction · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.65 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [semantic:NULL; numeric:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22-divergent. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
