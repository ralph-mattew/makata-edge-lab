# PoC 049: Does GreenLeaf's retrieval gain convert at the answer step? (OP-1/OP-2)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Lab follow-up to **PoC-045** (GreenLeaf binary index, ADOPT host/retrieval: hard-mean recall@3 +14.3 pp) — the re-validation its verdict demanded, framed by **PoC-040** (chunk-size recall gain did NOT convert to answer quality). |
| Registered | 2026-10-26 (before the first run). |

## Question

Does PoC-045's **+14.3 pp hard-category recall@3** gain from the GreenLeaf-Tiny legal embedder **convert to
answer quality** — i.e. does running the adopted generator-free extractor (PoC-036, ≤3-sentence cosine
window, N=10) over **GreenLeaf** retrieval + **GreenLeaf** sentence scoring lift hard-category span-F1 by
**≥ +5 pp** over the EmbeddingGemma extractor (22.1 hard-mean) — or does it fail to convert, like the
chunk-size gain in PoC-040?

## Why it matters here

- PoC-040 established the lab's sharpest caveat: **retrieval-coverage gains convert weakly (there, not at
  all) to hard-category answer quality.** PoC-045 produced the *largest* retrieval gain in the series
  (+14.3 pp), so it is the best candidate to break that pattern — but the conversion is **unproven**, and
  PoC-045's own verdict made this the required next experiment before any end-to-end claim.
- If it converts, GreenLeaf (+ binary index) becomes an end-to-end hard-category win and the embedder-swap
  is justified for the answer path, not just the index. If it doesn't, 045 stays a retrieval-only/storage
  result and reinforces that the bottleneck is answer **granularity**, not retrieval.

## Hypothesis

A legal embedder that retrieves the right chunk more often (045) should also score the right **sentence**
higher within it, so the generator-free extractor should convert more of the recall gain than the
chunk-size lever did (040). Untested.

- **H1:** GreenLeaf extractor hard-mean span-F1 ≥ **+5 pp** over the EmbeddingGemma extractor (PoC-036: 22.1).
- **H2:** the conversion ratio (Δspan-F1 / Δrecall@3) is **> 0** and materially above PoC-040's (~0).
- **H3 (feasibility):** generator-free, host peak RSS ≤ 6 GB (no Qwen); GreenLeaf encode cost recorded.

## Method

Reuse the PoC-036 extractor path (decomposed sub-queries → top-N chunks → split sentences → max-cosine
≤3-sentence window → span-F1) but swap the embedder from EmbeddingGemma to **GreenLeaf-Tiny** for **both**
chunk retrieval and sentence scoring (loaded via `transformers.AutoModel` + mean-pool + L2 on MPS, as
PoC-045). Evaluate on the 300 hard-category items (or the PoC-045 216-contract sample if full-corpus encode
is infeasible — see Deviations). Arms: (a) EmbeddingGemma extractor (= PoC-036, reference), (b) GreenLeaf
extractor (headline). Both generator-free, ≤3-sentence window, N=10.

- **Varies:** the embedder (GreenLeaf vs EmbeddingGemma) in retrieval + sentence scoring. **Held fixed:**
  the extractor mechanism, decomposed sub-queries, N=10, window=3, span-F1 scorer, eval items/gold.
  **Measurements:** per-cat + hard-mean span-F1, recall@3 (to compute conversion ratio), host RSS + encode
  time; contract-level bootstrap CI. **Repetitions:** deterministic → single pass.

## Decision rule

Adopt (GreenLeaf for the answer path) if **H1 (span-F1 +≥5 over 036)**. Reject if span-F1 gain **< +2**
(recall gain does not convert — 040 pattern holds). Inconclusive +2–5. Report the conversion ratio
prominently (the scientific headline either way).

## Expected outcome (engine estimate)

inconclusive · confidence ~0.5 · est. effort 1 week

## Harness (to be written at run time)

`greenleaf-answerstep.py` forks `036/extract-depth.py` with a GreenLeaf encoder (AutoModel/MPS, length-
sorted batching, cached npy) for chunk + sentence embeddings; computes span-F1 + recall@3 for the GreenLeaf
and EmbeddingGemma extractors on the same items; reports the conversion ratio. Heavy GreenLeaf vectors
gitignored. Reads committed vectors via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
pip install -U transformers torch
cd poc/049-greenleaf-answerstep-revalidation
LAB_POC_ROOT=/path/to/lab-clone/poc python3 greenleaf-answerstep.py   # GreenLeaf on MPS (slow encode; sampled)
```

---

### Engine provenance
- Lab-internal follow-up (not an inbox drop): the PoC-045 verdict named this re-validation explicitly; PoC-040
  framed the conversion risk. Verdict feeds back to the ledger and resolves whether 045 is a retrieval-only
  or end-to-end win.
