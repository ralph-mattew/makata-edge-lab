# PoC 045: GreenLeaf-Tiny binary-quantized first-stage index (OP-1/OP-8)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending — do not fill until the run concludes._ |
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

## Harness (to be implemented at run time)

`greenleaf-index.py` embeds the PoC-014 chunks + PoC-007 queries with GreenLeaf-Tiny (MPS), bit-packs the
sign index, Hamming top-50 → float re-rank → top-3, scores recall@3 overall + per hard category, and
profiles index bytes; writes `results/greenleaf-index.json` + `results/comparison.txt`. The GreenLeaf
vector cache (heavy) stays gitignored. Reads gitignored committed inputs via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
pip install -U sentence-transformers torch   # GreenLeaf needs trust_remote_code
cd poc/045-greenleaf-binary-index && python3 greenleaf-index.py   # downloads the HF model on first run (MPS)
```

---

### Engine provenance

- Engine idea (OP-1/OP-8), unscreened. Promoted per the user's directive to **run rather than desk-reject**;
  the model is obtainable (HF `judicialmind/greenleaf-law-embed-tiny`), so the legal-embedder claim is
  testable. Verdict feeds back to the ledger.
