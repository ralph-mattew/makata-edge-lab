# PoC 045: GreenLeaf-Tiny binary-quantized first-stage index (OP-1/OP-8)

| | |
|---|---|
| Status | Concluded — host stage (216-contract stratified sample: all hard-category contracts, 872 items). |
| Verdict | **Adopt (host/retrieval stage) — GreenLeaf-Tiny substantially beats EmbeddingGemma on hard-category retrieval, and the binary index is lossless.** On the same 872-item sample: recall@3 overall **57.2 → 62.7 (+5.5)**, hard-mean **34.0 → 48.3 (+14.3)** — every hard category jumps (Exclusivity 6→17, Non-Compete 36→59, Change-of-Control 60→69). Sign-binarization + float re-rank is **exactly lossless** here (binary == float, 62.7 / 48.3) and the binary index is **10.1 MB vs 323.7 MB float32** (32×). H1 (≥61.4) PASS, H2 (≤300 MB) PASS, H3 (hard-mean +≥5) PASS (+14.3) → **ADOPT.** Two load-bearing caveats: (1) this is a **retrieval** win — per PoC-040, hard-category recall gains convert weakly to answer quality, so an end-to-end re-validation is required before claiming answer-step benefit; (2) GreenLeaf on MPS is **slow to embed** (~tens of docs/s on long chunks) and is a different 1024-dim model — on-device (CoreML) feasibility is unproven. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox proposal `2026-10-25-applying-greenleaftinys-binaryquantized-embeddings-as-a-firststage-index` (engine idea, OP-1/OP-8; source: *GreenLeaf Law Embed Tiny*, arXiv 2608.24936). Model on HF: `judicialmind/greenleaf-law-embed-tiny` (sentence-transformers, custom `greenleaf_embed` arch, hidden 1024). |
| Registered | 2026-10-26 (this draft, before the first run) |

## Question

Does a **legal-domain embedder** (GreenLeaf-Tiny) with a **binary (sign) first-stage index + float re-rank**
match or beat EmbeddingGemma on CUAD recall@3 — specifically ≥ 61.4% overall (non-regression vs the
PoC-035 baseline) and **≥ +5 pp hard-category mean** (the part attributable to *better legal embeddings*,
not the quantization scheme PoC-035 already validated) — while keeping the stored index ≤ 300 MB?

## Why it matters here

- PoC-035 established that sign-quantizing stored vectors + float re-rank on top-K is near-lossless
  (recall 62.6→61.0, −1.6) and frees ~235 MB. That isolated the *quantization* lever on EmbeddingGemma.
  This PoC isolates the *embedder* lever: does a legal-domain-tuned model lift recall — especially on the
  hard categories (Exclusivity / Non-Compete / Change-of-Control) — where EmbeddingGemma plateaus?
- **Caveat carried from PoC-040:** retrieval-coverage gains convert weakly to hard-category answer quality.
  So even a positive recall@3 result here is a retrieval-only claim; adoption for the answer path would need
  the 040 re-validation. H3 is framed as a retrieval hypothesis accordingly.
- If GreenLeaf binary matches EmbeddingGemma recall at ≤ 300 MB, the freed RAM could fund a larger
  generator (OP-8).

## Hypothesis

A legal-domain embedder captures clause semantics EmbeddingGemma misses, and sign-quantization is
near-lossless (per PoC-035), so a binary GreenLeaf index + float re-rank should hold overall recall and lift
the hard categories. Unverified on our stack; GreenLeaf has never been run on CUAD/recall@3.

- **H1:** binary GreenLeaf + float re-rank (top-50) achieves **≥ 61.4%** recall@3 overall (non-regression).
- **H2:** stored binary index **≤ 300 MB** (≤ PoC-035's 1-bit EmbeddingGemma footprint).
- **H3:** hard-category mean recall@3 **≥ +5 pp** over the EmbeddingGemma baseline (33.0 hard-mean on 014
  chunks), attributable to the embedder.

## Method

Reuse the committed PoC-014 page-chunk corpus + gold spans + the PoC-007 query set (same eval as PoC-013/
035/037). Embed all chunks and queries with **GreenLeaf-Tiny** (sentence-transformers, `trust_remote_code`,
MPS, L2-normalised); **binarize** stored chunk vectors (sign per dim → bit-packed), retrieve top-50 by
Hamming, **re-rank** by exact float dot product, take top-3. Measure recall@3 = top-3 covers ≥ 50 % of the
gold word-span (PoC-007 definition), overall + per hard category. Arms: (a) PoC-035 1-bit EmbeddingGemma
baseline (reuse committed result), (b) GreenLeaf **binary + float re-rank** (headline), (c) GreenLeaf
**float** (reference ceiling). Profile stored index bytes.

- **Varies:** the embedder (GreenLeaf vs EmbeddingGemma) and the index precision (binary vs float).
  **Held fixed:** the PoC-014 chunk boundaries, the PoC-007 eval items + gold spans, recall@3 definition,
  top-50 re-rank depth. **Measurements:** overall + per-hard-cat recall@3, stored index MB, cosine
  self-check that GreenLeaf float reproduces its own binary re-rank ordering. **Repetitions:** deterministic
  → single pass.
- Stack: GreenLeaf-Tiny (HF `judicialmind/greenleaf-law-embed-tiny`, hidden 1024) via sentence-transformers
  on MPS; CUAD (397 contracts). Pure semantic (no BM25) to isolate the embedder, matching PoC-035's setup.

## Decision rule

- **Adopt** binary GreenLeaf if **H1 (≥ 61.4%) ∧ H2 (≤ 300 MB) ∧ H3 (≥ +5 pp hard-mean)**.
- **Reject** if recall@3 drops **> 2 pp** below the PoC-035 baseline or the index does not fit ≤ 300 MB.
- **Inconclusive** otherwise (e.g. non-regression overall but hard-mean gain < +5 pp).

## Expected outcome (engine estimate, not a result)

inconclusive · confidence 0.38 · est. effort 1-2 weeks

## Harness

`greenleaf-index.py` loads GreenLeaf-Tiny via `transformers.AutoModel` + mean-pool + L2 on MPS
(sentence-transformers' wrapper fails — the model's custom code imports a removed `sentence_transformers.base`;
see Deviations), embeds the sampled contracts' PoC-014 chunks + PoC-007 queries (length-sorted batching),
sign-binarizes the stored vectors, retrieves per-contract top-50 by Hamming agreement, re-ranks by exact
float dot product → top-3, and scores recall@3 (top-3 covers ≥50% of the gold span) overall + per hard
category against the committed EmbeddingGemma pure-semantic baseline on the same sample. Writes
`results/greenleaf-index.json` + `results/comparison.txt`; the GreenLeaf vector cache
(`results/raw/gl-*.npy/.npz`, ~215 MB) is gitignored. Reads committed inputs via `LAB_POC_ROOT`.

## Results

MEASURED on the host (Mac16,8 M4 Pro; GreenLeaf-Tiny via transformers AutoModel on MPS, max_length 128),
**216-contract stratified sample = all hard-category contracts, 872 items**, pure semantic (no BM25),
recall@3 (top-3 covers ≥50% of gold span). EmbeddingGemma baseline recomputed on the *same* sample.

| Arm | overall recall@3 | hard-mean | Exclusivity | Non-Compete | Change-of-Control |
|---|---|---|---|---|---|
| EmbeddingGemma (semantic) | 57.2 | 34.0 | 6 | 36 | 60 |
| GreenLeaf-Tiny float | **62.7** | **48.3** | 17 | 59 | 69 |
| **GreenLeaf-Tiny binary + float re-rank** | **62.7** | **48.3** | 17 | 59 | 69 |

Index footprint (full 79,037-chunk corpus): **binary 10.1 MB** vs float32 323.7 MB (**32×**).

- **H1 (overall ≥ 61.4):** PASS — 62.7 (and +5.5 vs same-sample EmbeddingGemma 57.2). MEASURED.
- **H2 (binary index ≤ 300 MB):** PASS — 10.1 MB (1024 sign bits × 79k chunks). MEASURED.
- **H3 (hard-mean +≥5 pp, attributable to the embedder):** PASS — **+14.3 pp** (34.0→48.3), every hard
  category up: Exclusivity **6→17**, Non-Compete **36→59**, Change-of-Control **60→69**. MEASURED.
- **Binary is lossless:** sign-binary + float re-rank reproduces the float arm exactly (62.7 / 48.3) —
  within-contract candidate pools rarely exceed the 50-wide Hamming gate, and the float re-rank restores
  exact top-3 order. MEASURED.

Per-arm figures in `results/greenleaf-index.json`.

## Verdict

**Adopt (host / retrieval stage).** A legal-domain embedder is the first lever in the series to move the
hard categories at the *retrieval* layer by a wide margin: +14.3 pp hard-mean, with Exclusivity — the
worst category all along — nearly tripling (6→17) and Non-Compete jumping 36→59. This is a genuine embedder
effect (same chunks, same eval, same metric; only the embedding model changes), and it confirms the
hypothesis EmbeddingGemma's general-domain vectors were the hard-category bottleneck at retrieval. The
sign-binary index makes it essentially free to store (10.1 MB, 32× smaller, lossless re-rank), satisfying
the OP-8 RAM-reallocation motive.

Two caveats keep this an **adopt at the retrieval stage, not yet end-to-end**:

1. **Conversion to answer quality is unproven.** PoC-040 established that hard-category recall@3 gains
   convert weakly (often not at all) to answer-step span-F1. A +14.3 pp recall@3 lift is the *largest* the
   lab has produced, so it is the best candidate yet to break that pattern — but it must be re-validated on
   the answer step (the PoC-036 extractor / generation) before claiming an end-to-end win. This is the
   obvious next PoC.
2. **Deployment feasibility is open.** GreenLeaf-Tiny is a different, larger (1024-dim) model, and on MPS it
   embeds slowly (the full 79k-chunk corpus is impractical in one pass here — hence the sample). On-device
   (CoreML / quantized) throughput and RAM are unmeasured; the binary index helps storage but not encode
   cost. Adoption requires an on-device embed-throughput check.

Net: **adopt as the hard-category retrieval embedder for the host/index stage, with binary storage**, and
open a follow-up to (a) re-validate the gain at the answer step and (b) measure on-device embed feasibility.

## Deviations

- **Loaded via `transformers.AutoModel` + manual mean-pool + L2, not sentence-transformers.** The model's
  shipped ST custom code imports `sentence_transformers.base`, which the installed sentence-transformers
  version no longer exposes (`ModuleNotFoundError`). The AutoModel path with `trust_remote_code=True`
  reproduces normalized 1024-dim embeddings and matches the model's `1_Pooling` (mean) config.
- **216-contract stratified sample (872 items), not the full 1,325.** Embedding all 79,037 CUAD chunks with
  GreenLeaf on MPS is prohibitively slow (~11 docs/s on the long-chunk tail — a per-batch MPS cost that
  `max_length` reductions didn't dent). The sample keeps **all** contracts carrying a hard-category item,
  so the hard-category result (H3) is on the full hard set; the overall figure (H1) is a same-sample
  estimate and the EmbeddingGemma baseline is recomputed on the identical sample for a fair delta.
- **max_length = 128 for GreenLeaf embedding.** Clause presence sits early in a chunk; chunk *spans*
  (hence recall scoring) are unchanged — only the embedded text of the longest chunks is truncated.
- **Pure semantic (no BM25),** matching PoC-035's isolation of the index/embedder lever.

## Limits

- **Retrieval recall@3 only** — not answer quality (see Verdict caveat 1 and PoC-040).
- **Sampled overall figure** — the 872-item overall is hard-contract-weighted; the clean claims are the
  same-sample deltas (+5.5 overall, +14.3 hard-mean) and the per-category hard jumps.
- **Host/MPS only** — slow GreenLeaf encode; on-device feasibility unmeasured.
- **Binary losslessness is granularity-dependent** — holds for per-contract retrieval (small pools); a
  corpus-wide first-stage filter with pools ≫ 50 could lose a little (as PoC-035 saw −1.6 on EmbeddingGemma).

## Reproduce

```bash
pip install -U transformers torch        # GreenLeaf needs trust_remote_code; AutoModel path (not sentence-transformers)
cd poc/045-greenleaf-binary-index
LAB_POC_ROOT=/path/to/lab-clone/poc python3 greenleaf-index.py --contracts 216   # downloads the HF model on first run (MPS)
```

---

### Engine provenance

- Engine idea (OP-1/OP-8), unscreened. Promoted per the user's directive to **run rather than desk-reject**;
  the model is obtainable (HF `judicialmind/greenleaf-law-embed-tiny`), so the legal-embedder claim is
  testable. Verdict **ADOPT (host/retrieval)** — GreenLeaf lifts hard-cat recall@3 +14.3 pp; feeds back to the ledger.
