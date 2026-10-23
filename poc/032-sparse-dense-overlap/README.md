# PoC 032: Sparse-dense overlap — does BM25 earn its 0.1 in the hybrid? (OP-3)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, dense vs BM25 vs hybrid) |
| Verdict | **Inconclusive by the rule → keep BM25 (do not drop it).** The "fusion tax" does **not** transfer to CUAD: dense-only recall@3 is **61.0** vs the 0.9/0.1 hybrid **62.6** — BM25's 0.1 share buys **+1.6pp** overall and **+5pp on Change-of-Control** (65 vs 60), for a negligible ~2 ms/query. H1 holds (BM25 is sparse-exclusively useful on only 5.3% of queries) but H2 fails (dense-only loses >1pp), so the proposal's "drop BM25" is not supported. Directly confirms PoC-013's 0.9/0.1 choice. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | The Fusion Tax: A Diagnostic Analysis of When Hybrid Retrieval Hurts (http://arxiv.org/abs/2610.30612v1); 2026-10-23 ideation-engine DIVERGENT scan. (Micro-lab flagged UNSCREENED — routed to the lab as the judge.) |
| Registered | 2026-10-23 (this draft, before the first run) |

## Question

Does measuring the per-query sparse-dense overlap on CUAD reveal that BM25 provides near-zero marginal coverage, justifying dropping it entirely and freeing compute for a denser index or larger LLM context?

## Why it matters here

- If BM25 contributes to fewer than 10% of retrievals on CUAD (low sparse-dense balance), the 0.1 BM25 weight is a compute and latency cost with no recall benefit — removing it frees CPU time and pipeline complexity
- Eliminating BM25 from the hybrid pipeline could allow longer query processing or a larger retrieved context within the same 6GB RAM budget
- The paper's diagnostic framework gives a principled, data-driven rationale for the 'do not fuse' decision rather than an arbitrary ablation

## Hypothesis

The paper's sparse-dense balance diagnostic was developed on BEIR; we apply the same diagnostic to CUAD with EmbeddingGemma + BM25 to measure whether BM25 provides meaningful exclusive coverage, and use the result to decide whether our 0.9/0.1 hybrid is justified or whether dense-only would match or exceed it — unverified for legal contract corpora.

- H1: BM25 provides exclusive top-3 coverage (a relevant chunk in BM25 top-3 but not dense top-3) on fewer than 15% of CUAD queries, indicating low sparse-dense balance
- H2: Dense-only (1.0/0.0) retrieval achieves recall@3 within 1pp of the 0.9/0.1 hybrid (≥60.4%), confirming the fusion tax outweighs fusion benefit on CUAD
- H3: If H1 and H2 hold, latency of the retrieval step decreases by ≥20% by eliminating BM25 scoring

## Method

Reuse PoC-007/013 harness. (1) For each of the 1,325 queries, record BM25 top-3 and dense top-3 chunk sets; compute the fraction where a gold chunk appears exclusively in BM25 top-3 (sparse-only coverage). (2) Run dense-only retrieval (weight 1.0/0.0) and measure recall@3 vs 0.9/0.1 baseline. (3) Time both pipelines on iPhone 15 Pro for latency comparison. All uses existing infrastructure, no new models.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the retrieval scorer — dense-only (1.0/0.0), BM25-only, and hybrid (0.9/0.1). **Held fixed:** EmbeddingGemma vectors, the PoC-014 chunk index, top-3, the full 1,325-item eval set. **Measurements:** recall@3 per arm (overall + hard categories), sparse-exclusive coverage (gold in BM25 top-3 but not dense top-3), host per-query BM25 vs dense cost. **Repetitions:** deterministic → single pass.

## Decision rule

ADOPT dense-only (drop BM25) if H1 holds (sparse-exclusive coverage <15%) AND H2 holds (dense-only recall@3 ≥60.4%) AND H3 holds (≥20% latency reduction); REJECT if H2 fails (dense-only recall@3 <60.4%); INCONCLUSIVE if H1 holds but H2 is borderline (60.4%–61.4%)

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.4  ·  est. effort 1-2 days

## Harness

`sparse-dense.py` (committed vectors; no model/server): per query, rank the contract's chunks by
dense cosine, BM25, and hybrid 0.9/0.1; take top-3 each; record recall@3 and whether a gold-covering
chunk is sparse-exclusive (in BM25 top-3 but not dense top-3).

## Results

MEASURED on the host, full CUAD (1,325 items), recall@3.

| Arm | overall | Exclusivity | Non-Compete | Change Of Control |
|---|---|---|---|---|
| dense-only (1.0/0.0) | 61.0 | 6 | 36 | 60 |
| BM25-only | 41.8 | 1 | 8 | 47 |
| **hybrid 0.9/0.1** | **62.6** | 6 | 33 | 65 |

- **H1 (sparse-exclusive coverage < 15%):** PASS — **5.3%** overall (4.0% on hard). BM25 adds something
  dense misses on only ~1 query in 19. MEASURED.
- **H2 (dense-only within 1pp of hybrid & ≥60.4):** FAIL on the 1pp test — dense-only 61.0 is **−1.6pp**
  vs hybrid 62.6 (and −5pp on Change-of-Control). dense-only is ≥60.4, so it lands in the decision
  rule's inconclusive band (60.4–61.4). MEASURED.
- **Cost:** BM25 scoring is ~2.0 ms/query on the host (dense ~3.9 ms/q) — the eliminable saving is tiny.
  INFERRED (device H3 not measured).

Figures in `results/sparse-dense.json`.

## Verdict

**Inconclusive by the letter; the actionable answer is KEEP BM25.** The source paper's "fusion tax"
(hybrid hurts) does not transfer to CUAD: the 0.9/0.1 hybrid beats dense-only by +1.6pp overall and
+5pp on Change-of-Control, so BM25's small weight is *earning* recall, not taxing it — even though it
is sparse-exclusively useful on only 5.3% of queries (those few cases carry the gain). Dropping BM25
would trade 1.6pp recall for ~2 ms/query, which is not worth it. This is a clean **confirmation of
PoC-013's 0.9/0.1 hybrid** via direct ablation, and a negative result for the "drop BM25" idea.

Net for the engine: do not re-propose removing BM25 / dense-only retrieval on CUAD — it costs recall,
most visibly on Change-of-Control. The hybrid weight question is now settled from both directions
(PoC-013 tuned it; PoC-032 ablated it).

## Limits

- **recall@3 only.** Latency/RAM savings (H3) are device-bound and tiny on host; not the deciding factor.
- **Fixed chunking + BM25 params** (PoC-014 page; k1=1.5, b=0.75). A different chunking could change
  BM25's marginal value, but that is PoC-014's axis.
- **Standard BM25.** A learned sparse retriever (SPLADE-style) is a different question, untested.

## Reproduce

```bash
cd poc/032-sparse-dense-overlap
python3 sparse-dense.py        # committed vectors; no model/server
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `arxiv-2610.30612v1-idea-9` · technique: extraction · attacks: OP-3
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.55 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **null** · sub-labs confirmed 1 [cuad_hard:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-23. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
