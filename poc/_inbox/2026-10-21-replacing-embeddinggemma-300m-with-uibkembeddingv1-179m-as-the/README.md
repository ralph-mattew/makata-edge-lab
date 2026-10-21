# PoC (proposed): Does replacing EmbeddingGemma 300M with UIBK-Embedding-v1 (179M) as th…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | UIBK-Embedding: Effective Text Retrieval by Unifying Dense and Late-Interaction Retrieval (http://arxiv.org/abs/2610.27195v1) |
| Registered | not yet — proposed 2026-10-21 |

## Question

Does replacing EmbeddingGemma 300M with UIBK-Embedding-v1 (179M) as the sole on-device embedder — using its unified dense+late-interaction representation scored with MaxSim — improve recall@3 on CUAD by ≥3 points while staying within our 6GB RAM budget?

## Why it matters here

- UIBK-Embedding-v1 is 179M parameters vs EmbeddingGemma's 300M, potentially freeing ~150–200 MB of RAM (embedder footprint reduction) which could be reallocated to a larger LLM or longer context window.
- The unified dense+token-level MaxSim mechanism may specifically help hard categories (Exclusivity, Non-Compete, Change-of-Control) where exact-phrase and entity-level matching matters and pure dense retrieval fails — attacking OP-1 as a secondary benefit.
- A single-model, single-index architecture avoids the two-model overhead of our current hybrid (EmbeddingGemma dense + BM25), potentially reducing latency.

## Hypothesis

Source evaluated UIBK-Embedding-v1 on BEIR general-domain English corpora with nDCG@10; we test whether the same unified dense+MaxSim mechanism, run on-device (iPhone 15 Pro, CoreML or ONNX export), improves recall@3 on CUAD contracts with our existing PoC 007/013 evaluation harness — this transfer is unverified.

- H1: UIBK-Embedding-v1 achieves recall@3 ≥ 64.4% on CUAD (current EmbeddingGemma baseline: 61.4%), a gain of ≥3 points.
- H2: The on-device RAM footprint of the UIBK-Embedding-v1 embedder is ≤ 420 MB (vs ~600 MB for EmbeddingGemma 300M), freeing ≥150 MB.
- H3: Per-category recall@3 on at least one hard category (Exclusivity, Non-Compete, or Change-of-Control) improves by ≥5 points absolute over the EmbeddingGemma baseline.

## Method

Reuse the PoC 007/013 evaluation harness on CUAD (397 documents, 1,325 Q&A items). Export UIBK-Embedding-v1 to ONNX or CoreML and run on iPhone 15 Pro within the 6GB budget. Build the unified MaxSim index (dense vectors embedded as extra token vectors) for all CUAD chunks at the same chunk granularity as PoC 007. Evaluate recall@3 and key-fact accuracy vs the EmbeddingGemma 0.9/0.1 hybrid baseline. Measure RAM usage during inference. Report per-category recall@3 for all hard categories identified in PoC 013.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT if H1 (recall@3 ≥ 64.4%) AND H2 (RAM ≤ 420 MB) both hold. REJECT if recall@3 < 62.4% (+<1 point) or RAM exceeds 600 MB. INCONCLUSIVE if recall@3 is 62.4–64.4% (marginal gain) or if on-device export fails latency requirements (>2s per query at P95).

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1-2 weeks (model export/quantization: 2-3 days; index rebuild: 1 day; evaluation harness adaptation: 1-2 days; run + analysis: 1-2 days)

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

- Engine idea id: `arxiv-2610.27195v1-idea-7` · technique: extraction · attacks: OP-3
- Gates (0–10): G1 8.25 · G2 8.0 · G3 6.5 · null-control Δ7.75 (real 8.0 vs null 0.25)
- Tournament: rank 3, elo 1016.0 · priority 🔥 HIGH (9.021185372005045)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
