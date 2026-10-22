# PoC (proposed): Does adding a lightweight cross-encoder reranking step (Hybrid + reran…

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

Does adding a lightweight cross-encoder reranking step (Hybrid + reranker) to our existing 0.9/0.1 hybrid retrieval on CUAD improve recall@3 and per-category recall on hard categories (Exclusivity, Non-Compete, Change-of-Control) by ≥3 points?

## Why it matters here

- The paper finds that Hybrid + reranking achieves higher evidence coverage (94.1%) than dense-only retrieval (81.3%) on long documents, suggesting reranking adds orthogonal signal beyond the base hybrid score — directly relevant to our hard categories that are invariant to weight tuning.
- If reranking can surface evidence that survives the final top-k cut even when base retrieval scores are noisy, it could break the invariance observed in PoC-013 for Exclusivity (~11% recall@3).
- Improved per-category recall on hard categories is the highest-value target in the lab (OP-1), and this mechanism is independent of chunk boundary or query formulation changes being tested in PoC-014/015.

## Hypothesis

Source ran hybrid+reranker on QASPER/textbook corpora with OpenAI-class embedders and cloud rerankers; we test whether the same mechanism — appending a reranking step to our 0.9/0.1 hybrid retrieval — improves recall@3 and per-category recall on CUAD with EmbeddingGemma 300M, within the 6GB RAM/latency constraints of an iPhone 15 Pro. This is unverified; PoC-012 parked on-device latency concerns.

- H1: Hybrid + cross-encoder reranking improves overall recall@3 by ≥3 points over the 0.9/0.1 hybrid baseline (current: 61.4%).
- H2: Per-category recall@3 on at least 2 of the 3 hard categories (Exclusivity, Non-Compete, Change-of-Control) improves by ≥5 points absolute.
- H3: End-to-end on-device latency (retrieval + rerank) remains under 3 seconds per query on iPhone 15 Pro so the approach is deployable.

## Method

Reuse PoC-007/013 harness on CUAD (397 docs, 1325 Q&A). Add a lightweight cross-encoder reranker (e.g., a quantised MiniLM or similar <200MB model that fits in RAM budget) as a post-retrieval step: retrieve top-10 via existing 0.9/0.1 hybrid, rerank to top-3. Measure recall@3 overall and per hard category. Profile RAM usage (must stay under 6GB with LLM and embedder loaded) and wall-clock latency per query. Baseline: current 61.4% recall@3 with no reranker.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT if H1 (≥+3 points overall recall@3) AND H2 (≥2 hard categories improve ≥5 points) AND H3 (latency <3s) all hold. REJECT if overall recall@3 improves <+1 point or latency >5s. INCONCLUSIVE otherwise (e.g., overall improves but hard categories do not, or latency borderline).

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1-2 weeks

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
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.7 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [numeric:POINT_WINS_ONLY; numeric:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
