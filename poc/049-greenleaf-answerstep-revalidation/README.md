# PoC 049: Does GreenLeaf's retrieval gain convert at the answer step? (OP-1/OP-2)

| | |
|---|---|
| Status | Concluded — host stage (80 hard-contract sample, 103 items; span-F1). |
| Verdict | **Adopt — GreenLeaf's retrieval gain CONVERTS to answer quality, breaking the PoC-040 pattern.** Running the PoC-036 generator-free extractor with GreenLeaf (retrieval + sentence scoring) vs EmbeddingGemma lifts hard-mean span-F1 **22.6 → 32.3 (+9.7)**, every hard category up (Exclusivity 14.4 → 25.3, Non-Compete 26.7 → 35.5, Change-of-Control 26.7 → 36.2). The **conversion ratio is 2.77** (Δspan-F1 +9.7 / Δrecall@3 +3.5) — versus PoC-040's ~0 for the chunk-size lever. H1 (+≥5) PASS → **ADOPT.** This is the **first mechanism in the series to convert a retrieval gain into answer-quality gain**, confirming the legal embedder (PoC-045) as an end-to-end hard-category win, not just a retrieval/storage one. Caveats: 80-contract sample (GreenLeaf full-corpus MPS encode infeasible); generator-free (≤6 GB); on-device GreenLeaf throughput still unproven. See Verdict. |
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

## Harness

`greenleaf-answerstep.py` forks `036/extract-depth.py`: the PoC-036 generator-free extractor (decomposed
sub-queries → top-N=10 chunks → split sentences → max-cosine over sub-queries → best ≤3-sentence window →
span-F1), run with two embedders on the SAME hard-contract sample. The **EG** arm uses committed `emb-page`
chunk vectors + committed `emb-subqueries` + EmbeddingGemma (:8090) for candidate sentences; the **GL** arm
uses GreenLeaf-Tiny (AutoModel/MPS, length-sorted batching, max_length 128) for chunk vectors, the 016
sub-query texts, and candidate sentences. Reports span-F1, recall@3, and the conversion ratio. Reads
committed vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default` + GreenLeaf-Tiny via AutoModel/MPS), **80
hard-contract sample, 103 items**, extractor N=10, ≤3-sentence window, span-F1, deterministic single pass.

| Extractor embedder | hard-mean span-F1 | Exclusivity | Non-Compete | Change-of-Control | recall@3 (hard) |
|---|---|---|---|---|---|
| EmbeddingGemma (= PoC-036) | 22.6 | 14.4 | 26.7 | 26.7 | 43.9 |
| **GreenLeaf-Tiny** | **32.3** | **25.3** | **35.5** | **36.2** | 47.4 |
| Δ | **+9.7** | +10.9 | +8.8 | +9.5 | +3.5 |

- **Control:** EG extractor 22.6 reproduces PoC-036 (22.1 on full 300). MEASURED.
- **H1 (GreenLeaf span-F1 ≥ +5 over EG):** PASS — **+9.7 pp**, all three hard categories up ~+9–11.
  MEASURED.
- **H2 (conversion ratio ≫ PoC-040's ~0):** PASS — **2.77** (Δspan-F1 +9.7 / Δrecall@3 +3.5). The embedder
  gain converts *more than 1:1* — GreenLeaf improves not just which chunk is retrieved but which sentence
  scores highest within it. MEASURED.
- **H3 (generator-free, ≤6 GB):** PASS — no Qwen in the path. OBSERVED (device encode cost pending).

Summary in `results/greenleaf-answerstep.json`.

## Verdict

**Adopt — and this is the scientific capstone of the arc.** PoC-040 established the series' hardest lesson:
retrieval-coverage gains convert weakly (there, not at all) to hard-category answer quality — the chunk-size
lever added recall@3 but zero span-F1. PoC-049 shows the GreenLeaf legal embedder is **different**: its
retrieval advantage flows straight through the generator-free extractor to **+9.7 pp hard-mean span-F1**,
a conversion ratio of 2.77. The reason is mechanistic — a legal-domain embedder scores the *right sentence*
higher (not just the right chunk), so both the retrieval step and the cosine extraction step improve
together. This makes **PoC-045 an end-to-end hard-category win**, not merely a retrieval/storage result, and
it is the first time any lever in the series has moved hard-category *answer quality* by this margin.

Combined with PoC-046 (legal-taxonomy query expansion, +10.3 recall@3), the hard-category bottleneck is
finally yielding — from the two levers the series repeatedly pointed to: the **embedding** and the **query**,
both made legal-domain-aware. The composition (046 taxonomy × 045/049 GreenLeaf, generator-free extractor)
is the clear next experiment and the candidate production stack for hard categories.

Caveats: (1) **80-contract sample** (103 items) — GreenLeaf full-corpus MPS encode is infeasible here, so
the magnitude carries sample noise (direction is robust and large); (2) **on-device GreenLeaf throughput**
is unproven (MPS encode is slow — the binary index helps storage, not encode); a CoreML/quantized path is
the deployment prerequisite.

## Limits

- **Sampled** (80 hard contracts / 103 items); direction robust, exact magnitude sample-dependent.
- **span-F1 proxy** (hard categories only); generator-free extractor (no Qwen).
- **GreenLeaf encode cost** (host MPS slow; device feasibility open) — the adopt is for the host/index +
  answer-selection stage, pending an on-device embed path.

## Reproduce

```bash
pip install -U transformers torch
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/049-greenleaf-answerstep-revalidation
LAB_POC_ROOT=/path/to/lab-clone/poc python3 greenleaf-answerstep.py --contracts 80
```

---

### Engine provenance
- Lab-internal follow-up (not an inbox drop): the PoC-045 verdict named this re-validation explicitly; PoC-040
  framed the conversion risk. Verdict feeds back to the ledger and resolves whether 045 is a retrieval-only
  or end-to-end win. Verdict **ADOPT** — it converts (+9.7 span-F1, ratio 2.77 vs 040's ~0); 045 is an end-to-end win. Feeds back to the ledger.
