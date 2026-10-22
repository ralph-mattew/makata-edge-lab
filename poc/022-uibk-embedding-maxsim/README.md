# PoC 022: UIBK-Embedding-v1 (179M) late-interaction MaxSim retrieval (OP-3)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, 1,325 items) |
| Verdict | **Inconclusive (host stage); do not promote to device yet.** UIBK MaxSim recall@3 = **63.2%** (CI 60.5–65.8) vs EmbeddingGemma 61.4% → **+1.8**, inside the pre-registered inconclusive band (adopt ≥ +3 / reject < +1), so H1 is not met. H3 *does* fire on one hard category — **Non-Compete 25 → 41 (+16)** — but Exclusivity regresses (7 → 4) and Change-of-Control is flat, so it's a redistribution, not a net retrieval win. The marginal overall gain doesn't justify the device-stage cost (H2 RAM / CoreML export) yet. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | UIBK-Embedding: Effective Text Retrieval by Unifying Dense and Late-Interaction Retrieval (http://arxiv.org/abs/2610.27195v1). Model: [DataScience-UIBK/uibk-embedding-v1](https://huggingface.co/DataScience-UIBK/uibk-embedding-v1) (Apache 2.0, 179M). Promoted from the 2026-10-21 ideation-engine scan. |
| Registered | 2026-10-21 (this draft, before the first run) |

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

- Baseline: EmbeddingGemma 300M hybrid 0.9/0.1, recall@3 **61.4%** (PoC-007). Candidate: UIBK-Embedding-v1 179M, loaded via PyLate as a ColBERT model; its plain MaxSim = token-MaxSim + 0.75·dense-cosine in one pass (one model, one index).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD (397 docs, 1,325 items).
- **Varies:** the embedder + scorer only — UIBK MaxSim vs EmbeddingGemma hybrid. **Held fixed:** the PoC-014 chunk granularity, per-contract candidate set, the PoC-007 recall definition (top-3 cover ≥ 50% of gold span) and gold spans.
- **Measurements (host):** recall@3 overall + per-category incl. hard categories, contract-level bootstrap CI. **Parked (device):** H2 (≤ 420 MB RAM) and the CoreML/ONNX export + P95 latency — these need an iPhone, like [PoC-012](../012-cross-encoder-reranking). This host run decides whether the retrieval quality justifies the device work. **Repetitions:** deterministic encode+MaxSim → single pass.

## Decision rule

ADOPT if H1 (recall@3 ≥ 64.4%) AND H2 (RAM ≤ 420 MB) both hold. REJECT if recall@3 < 62.4% (+<1 point) or RAM exceeds 600 MB. INCONCLUSIVE if recall@3 is 62.4–64.4% (marginal gain) or if on-device export fails latency requirements (>2s per query at P95).

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1-2 weeks (model export/quantization: 2-3 days; index rebuild: 1 day; evaluation harness adaptation: 1-2 days; run + analysis: 1-2 days)

## Harness

`uibk-maxsim.py` loads UIBK-Embedding-v1 via PyLate (`models.ColBERT(..., trust_remote_code=True)`)
and scores each query against its contract's chunks by **MaxSim** (the model's unified score =
token-MaxSim + 0.75·dense-cosine, baked into the returned per-token 128-d vectors). recall@3 reuses
the validated PoC-007 path (gold word-spans + PoC-014 chunk spans). To stay within memory it streams
each contract's chunks in sub-batches and computes MaxSim as a segment-summed `(Q @ Dᵀ).max`
(vectorised over queries), holding only one sub-batch of token vectors at a time.

Engineering notes (for the replication): encoding runs on MPS at ~12 chunks/s (≈ 45 min for the
79k-chunk corpus); **encode `--batch` must stay small (16)** — batch 128 blew ModernBERT's attention
buffer to 16.9 GiB on long chunks. PyLate also downgrades the host torch/transformers/sentence-
transformers, so run it in an isolated env if other work needs the newer versions.

## Results

MEASURED on the host (Mac, MPS, UIBK-Embedding-v1 via PyLate), full CUAD 1,325 items, single
deterministic pass. recall@3 = top-3 cover ≥ 50% of the gold span; contract-level bootstrap CI.

| Metric | EmbeddingGemma hybrid (baseline) | UIBK MaxSim | Δ |
|---|---|---|---|
| **overall recall@3** | 61.4% (61.8% same-chunk, PoC-016) | **63.2%** (CI 60.5–65.8) | **+1.8** |
| Exclusivity | 7.0% | 4.0% | −3.0 |
| Non-Compete | 25.0% | 41.0% | **+16.0** |
| Change Of Control | 67.0% | 66.0% | −1.0 |
| hard-category mean | 33.0% | 37.0% | +4.0 |

(EmbeddingGemma hard-category numbers are PoC-016 `page/raw`, the same chunk set and retrieval the
UIBK run replaces.)

- **H1 (recall@3 ≥ 64.4%, i.e. +3):** NOT met — 63.2% (+1.8) sits in the pre-registered inconclusive
  band (62.4–64.4%). MEASURED.
- **H2 (RAM ≤ 420 MB):** not measured — device-bound, parked (see Limits).
- **H3 (≥ +5 on a hard category):** PASS on **Non-Compete (+16.0)**; but Exclusivity *regresses* (−3)
  and Change-of-Control is flat, so the hard-mean gain (+4) is a redistribution across categories,
  not a uniform lift. MEASURED.

Summary in `results/uibk-maxsim.json`; human-readable `results/comparison.txt`.

> **Smoke-vs-full caution (OBSERVED):** a 40-item smoke on the first items gave 80–85% recall — wildly
> optimistic because those early contracts are small/easy. The representative full-set number is 63.2%.
> Never read a verdict off a non-stratified smoke.

## Verdict

**Inconclusive (host stage) — do not promote to the device stage yet.** As a drop-in replacement for
EmbeddingGemma, UIBK-Embedding-v1's overall recall@3 gain is marginal (+1.8, inside the inconclusive
band) — not the ≥ +3 the decision rule requires to adopt, but better than the reject floor. The one
real signal is **Non-Compete +16 (25 → 41)**: late-interaction token matching clearly helps that
phrase-heavy category. But it *costs* Exclusivity (−3), so it reshuffles rather than lifts hard-category
retrieval, echoing the PoC-013 finding that the hard categories are largely retrieval-scoring-invariant.
Given a marginal overall gain and a real device cost (H2 RAM, CoreML/ONNX export, P95 latency — all
unmeasured here), the device work isn't justified on these numbers. **Worth a cheap follow-up first:**
use UIBK MaxSim only as a *Non-Compete-specific* retriever, or hybridise it with EmbeddingGemma, before
any single-model replacement. The engine's "inconclusive · confidence 0.45" estimate was accurate.

## Limits

- **Host only.** H2 (≤ 420 MB device RAM), the CoreML/ONNX export, and P95 latency are **parked**
  (device-bound, like [PoC-012](../012-cross-encoder-reranking)); this run only answers retrieval quality.
- **Candidate set = the query's own contract's chunks** (same as PoC-007/014) — a per-document retrieval
  setting, not a cross-library index; PLAID/usearch at library scale is untested.
- **Dense+MaxSim fusion is the model's fixed 0.75 weight.** Tuning the token/dense mix is untested.
- **Chunk granularity is PoC-014's** (page chunks); UIBK supports 2048-token docs, so a coarser chunking
  could change the picture.

## Reproduce

```bash
pip install pylate     # downgrades torch/transformers — use an isolated env if needed
cd poc/022-uibk-embedding-maxsim
python3 uibk-maxsim.py --batch 16     # full run (~45-60 min, encodes CUAD chunks on MPS)
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `arxiv-2610.27195v1-idea-7` · technique: extraction · attacks: OP-3
- Gates (0–10): G1 8.25 · G2 8.0 · G3 6.5 · null-control Δ7.75 (real 8.0 vs null 0.25)
- Tournament: rank 3, elo 1016.0 · priority 🔥 HIGH (9.021185372005045)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
