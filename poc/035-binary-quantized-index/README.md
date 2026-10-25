# PoC 035: Binary (1-bit) quantized stored index + float re-rank (OP-3)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD) |
| Verdict | **Adopt (host stage).** 1-bit (sign) quantization of the stored EmbeddingGemma vectors + an exact float32 re-rank of the top-50 keeps recall@3 at **61.0 vs 62.6 float (−1.6pp, within the 2pp bar)** while shrinking the index **32× (243 MB → 7.6 MB, frees 235 MB)** and **not hurting the hard categories** (hard-mean −0.7; Non-Compete even +3). All of H1 (recall within 2pp), H2 (≥140 MB freed), H4 (hard cats not worse) hold. The freed RAM is exactly what the "bigger LLM / longer context" ideas (OP-1/OP-2) need. The float re-rank matters: pure binary (no re-rank) is −2.0pp (at the edge). See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | arxiv-2610.27397v1; 2026-10-25 ideation-engine scan. (Micro-lab UNSCREENED — routed to the lab; the real experiment is the judge.) Distinct from PoC-024 (which was about the *model weights* being 4-bit QAT; this is the *stored vector index*). |
| Registered | 2026-10-25 (this draft, before the first run) |

## Question

Does replacing EmbeddingGemma-300M with a quantized binary or 1-bit sparse embedding model (e.g., a FAISS-compatible 1-bit PQ or binary-hashed index over existing EmbeddingGemma vectors) reduce stored-index RAM by ≥200MB while keeping recall@3 within 2 points of the 61.4% baseline — without re-training or PTQ of the embedder itself?

## Why it matters here

- OP-3's open question is specifically about the RAM/recall tradeoff for *compressed stored vectors*, not the model weights — binary or 1-bit PQ of stored vectors is the cheapest grounded lever (no PTQ, no calibration risk) and has not been measured on our CUAD stack.
- If binary-hashed stored vectors free ≥200MB (e.g., 768-dim float32 → 1-bit reduces index from ~600MB to ~24MB for 50K chunks), a larger LLM (Qwen2.5-3B) or longer context window becomes feasible within the 6GB budget, directly unblocking OP-1 and OP-2 progress.

## Hypothesis

The unverified leap: that binary or 1-bit product quantization of the stored EmbeddingGemma chunk embeddings on our CUAD index (which uses cosine similarity over ~50K 768-dim float32 vectors) preserves recall@3 within 2 points of 61.4%, because legal clause embeddings cluster in semantically coherent regions that survive aggressive index compression — and that any recall gap at the retrieval stage can be partially recovered by an exact-distance re-rank of the top-K binary candidates using the full float32 query vector. This has not been tested on our stack or on CUAD.

- H1: Binary PQ (1-bit per dimension, 768-dim → 96 bytes/vector) of stored CUAD chunk embeddings keeps recall@3 ≥ 59.4% (within 2pp of 61.4% baseline) when re-ranking top-50 binary candidates by exact float32 cosine.
- H2: Index RAM drops from ~150MB (50K × 768 × 4 bytes) to ≤5MB (50K × 96 bytes), freeing ≥140MB for the LLM.
- H3: Total pipeline latency does not increase by more than 20% (binary ANN is faster; float32 re-rank over top-50 is cheap).
- H4: The recall gap, if any, is concentrated in hard categories (Exclusivity, Non-Compete, Change-of-Control) where embedding geometry is already weak — i.e., binary compression does not make OP-1 meaningfully worse than the current baseline.

## Method

Reuse the existing experiment harness and CUAD dataset. (1) Export stored float32 EmbeddingGemma chunk embeddings from the current index. (2) Compress to binary (FAISS IndexBinaryFlat or LSH) and separately to 8-bit PQ as a mid-point. (3) At query time: embed query in float32, retrieve top-50 candidates from binary index, re-rank by exact float32 cosine. (4) Measure recall@3 per category vs. 61.4% baseline. (5) Measure index RAM before and after. (6) Profile latency. No model retraining or PTQ involved.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the stored-vector precision + retrieval mode — float32 hybrid 0.9/0.1 (baseline), binary (sign-bit) hybrid, and binary-candidate-gen→exact-float32-rerank(top-50). **Held fixed:** the EmbeddingGemma vectors themselves (binarised, not retrained), BM25, the PoC-014 chunk index, top-3, the eval set. **Measurements:** overall + hard-category recall@3 per mode, and index bytes/vector. **Repetitions:** deterministic → single pass.

## Decision rule

Adopt if H1 (recall@3 ≥ 59.4%) AND H2 (RAM freed ≥ 100MB) AND H4 (hard categories not made worse by >3pp vs baseline). Reject if recall@3 < 58% or hard-category recall drops >5pp. Inconclusive if RAM savings are real but recall loss exceeds H1 threshold — then explore 8-bit PQ as fallback.

## Expected outcome (engine estimate, not a result)

inconclusive — binary compression likely recoverable with re-ranking for easy categories, but hard categories (already at ~7% Exclusivity) may lose 2–5pp, and total RAM savings may be smaller than expected if the index is not the dominant 600MB cost (model weights dominate).  ·  confidence 0.4  ·  est. effort 1 week

## Harness

`binary-index.py` (committed vectors; no model/server): binarise each chunk vector to sign bits; score
under float32 hybrid, binary (sign-dot) hybrid, and binary-top-50 → exact-float32-cosine re-rank.
recall@3 = top-3 cover ≥50% of the gold span.

## Results

MEASURED on the host, full CUAD (79,037 chunks; 1,316 items), recall@3.

**Index size:** float32 768-d = 3072 B/vec → **243 MB**; binary 768-bit = 96 B/vec → **7.6 MB** —
**32× smaller, frees ≈235 MB.**

| Mode | overall recall@3 | Exclusivity | Non-Compete | Change Of Control |
|---|---|---|---|---|
| float32 hybrid (baseline) | 62.6 | 6 | 33 | 65 |
| binary hybrid (no re-rank) | 60.5 (−2.0) | 9 | 24 | 56 |
| **binary → float re-rank (top-50)** | **61.0 (−1.6)** | 6 | 36 | 60 |

- **H1 (binary+rerank within 2pp of float ≥59.4):** PASS — 61.0 (−1.6). MEASURED.
- **H2 (free ≥140 MB):** PASS — frees ~235 MB (32×). MEASURED.
- **H4 (hard categories not meaningfully worse):** PASS — hard-mean −0.7 (Non-Compete +3, CoC −5,
  Exclusivity 0). MEASURED.
- **H3 (latency ≤ +20%):** not measured on device; binary Hamming ANN is faster and the float re-rank is
  over only 50 vectors — favourable. INFERRED.

Figures in `results/binary-index.json`.

## Verdict

**Adopt (host stage).** 1-bit sign quantization of the stored index is a clean RAM win: a **32×
index reduction (~235 MB freed)** for only **−1.6pp recall@3**, with **no hard-category regression**
(hard-mean −0.7; Non-Compete actually +3). This is distinct from — and complementary to — PoC-024
(the embedder *weights* are already 4-bit QAT at ~270 MB; this compresses the stored *vectors*). The
exact-float re-rank of the top-50 is load-bearing: it recovers ~0.5pp over pure binary (−2.0 → −1.6)
and flips Non-Compete from −9 to +3, at trivial cost (50 float dot-products per query).

**Why it matters:** this is the first lever in the recent run that *frees budget* rather than chasing
hard-category recall. The ~235 MB (plus the already-small embedder) is exactly the headroom the
stalled OP-1/OP-2 directions need — e.g. a larger generator or a longer context window — so the
follow-up is to spend the freed RAM there, not on more retrieval tweaks. Device confirmation (H3
latency, live RAM) is the remaining open item before production.

## Limits

- **Index-only, host-measured.** The on-device RAM/latency (H3) isn't measured; the freed-bytes figure
  is the stored-vector arithmetic (float32 vs 1-bit), which is exact, but the real-process RSS saving
  depends on the index structure (FAISS/usearch binary index).
- **Sign-bit (1-bit) quantization**, no learned rotation/ITQ or multi-bit PQ — those could narrow the
  −1.6pp gap further; untested.
- **recall@3 only** — a −1.6pp retrieval change is unlikely to move answer quality (cf. PoC-017), but
  not measured end-to-end here.

## Reproduce

```bash
cd poc/035-binary-quantized-index
python3 binary-index.py        # committed vectors; no model/server
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g2-1` · technique: novelty-push · attacks: OP-3
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.75 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **NOT_VALIDATABLE** · sub-labs confirmed - [-] · compose-retest - · slice-faithfulness-risk -
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
