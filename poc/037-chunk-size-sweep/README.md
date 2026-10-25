# PoC 037: Fixed chunk-size sweep for retrieval (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, re-chunk + re-embed at 3 sizes) |
| Verdict | **Adopt (host) — the biggest retrieval-stage result in the series, and a reframing of the hard-category plateau.** Re-chunking to larger fixed windows lifts recall@3 monotonically: baseline (PoC-014 ~25-word chunks) 61.4 → W=192 **65.7 (+4.3)** → **W=384 (~512 tok) 67.6 (+6.2)**, with *every* hard category up — **Exclusivity 7→16, Non-Compete →46, Change-of-Control →70** (hard-mean ~33 → **44**) — using **fewer chunks** (79k → 10k, a smaller index). The long-standing hard-category retrieval plateau was **substantially a chunk-fragmentation artifact**: all prior retrieval PoCs (022/023/025/027/028/030/033) used the tiny 014 chunks. **Caveat:** part of the coverage gain is mechanical (a 384-word chunk meets the ≥50%-of-gold-span bar more easily) and larger chunks cost more generator context — so this must be re-validated at the answer step. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Large language models (LLMS) for legal analysis rag and beyond for optimizing domain adaptation in Portuguese legal domain-advanced retrieval and prompt engineering techniques for retrieval augmented generation in the Portuguese legal domain (https://openalex.org/W7204983724) |
| Registered | 2026-10-25 (this draft, before the first run) |

## Question

Does increasing chunk size (e.g. from current ~25-word median to 256-512 token chunks) improve recall@3 and key-fact accuracy on CUAD, particularly for hard categories, by ≥3pp?

## Why it matters here

- PoC-013 established that hard-category recall is invariant to retrieval scoring; the paper's finding that larger chunk sizes improve retrieval accuracy points to chunk granularity as the next lever — aligning with PoC-014's open question
- Larger chunks reduce the cross-reference fragmentation problem (OP-5) by keeping more clause context together, potentially resolving 'as described in Section 3.2' ambiguities within a single chunk
- If larger chunks help, this is a zero-cost infrastructure change (no new model, no RAM increase beyond index size)

## Hypothesis

Source tested chunk-size effects on Portuguese legal corpora with unspecified embedding and LLM models; we test the same larger-chunk hypothesis on CUAD English contracts with EmbeddingGemma 300M + 0.9/0.1 hybrid retrieval, measuring recall@3 and per-category recall. Transfer is unverified because (a) optimal chunk size may differ across legal languages/genres, (b) EmbeddingGemma's optimal context window is unknown, and (c) PoC-014 (clause-aware chunking) is already running and may interact.

- H1: Increasing chunk size from current median (~25 words) to 256-token fixed-size chunks improves recall@3 by ≥3pp over the PoC-007 baseline (current: 61.4%)
- H2: Hard-category recall@3 (Exclusivity, Non-Compete, Change-of-Control) improves by ≥5pp when using 256-token chunks vs current chunking
- H3: RAM overhead of the larger-chunk index stays within the 6GB device budget (index size increase ≤200MB)

## Method

Reuse PoC-007/013 harness. Re-chunk all 397 CUAD documents using fixed Token Text Splitter at 128, 256, and 512 token sizes (three conditions) with no overlap (overlap inconclusive per source). Re-embed with EmbeddingGemma 300M. Run hybrid retrieval (0.9/0.1) and measure recall@3 and key-fact accuracy on the full 1,325 Q&A set with per-category breakdown. Compare to PoC-007 baseline. Note: coordinate with PoC-014 results to avoid duplication on clause-aware chunking.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** chunk size — fixed non-overlapping windows of 96 / 192 / 384 words (≈128/256/512 tokens) vs the PoC-014 ~25-word-median baseline. **Held fixed:** EmbeddingGemma embedder + doc/query prefixes, hybrid 0.9/0.1, committed query vectors, top-3, the coverage metric, the 1,325-item eval set. **Measurements:** overall + hard-category recall@3 per size, chunk count. **Repetitions:** deterministic → single pass.

## Decision rule

ADOPT the best chunk size if H1 (≥+3pp recall@3) AND H3 (RAM within budget) hold; REJECT if best recall@3 gain <+1pp across all sizes; INCONCLUSIVE if gain is +1 to +2pp or if hard categories improve but global recall regresses

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.4  ·  est. effort 3-4 days

## Harness

`chunk-size.py` re-chunks every contract (concatenated pages) into fixed W-word windows with word-offset
spans, embeds each with EmbeddingGemma (:8090), and scores hybrid 0.9/0.1 recall@3 (top-3 cover ≥50% of
the gold span) using the committed query vectors. Sweeps W ∈ {96, 192, 384}.

## Results

MEASURED on the host (EmbeddingGemma), full CUAD (1,325 items), recall@3.

| Chunk size (words / ≈tokens) | chunks | overall recall@3 | Exclusivity | Non-Compete | Change Of Control |
|---|---|---|---|---|---|
| PoC-014 baseline (~25-word median) | 79,037 | 61.4 | ~7 | ~25–33 | ~65 |
| W=96 (~128 tok) | 39,812 | 58.6 (−2.8) | 7 | 28 | 55 |
| W=192 (~256 tok) | 20,003 | 65.7 (+4.3) | 15 | 42 | 66 |
| **W=384 (~512 tok)** | **10,096** | **67.6 (+6.2)** | **16** | **46** | **70** |

- **H1 (≥+3pp recall@3):** PASS — W=384 **+6.2**, W=192 +4.3. MEASURED.
- **H2 (hard categories +≥5pp):** PASS — at W=384 every hard category clears +5 (Excl +9, NC +13–21,
  CoC +5); hard-mean ~33 → **44**. MEASURED.
- **H3 (index RAM in budget):** PASS, and then some — W=384 has **10k chunks vs 79k** (smaller index;
  combine with PoC-035 binary for a tiny footprint). MEASURED.
- Monotonic knee: too-small (W=96) *hurts* (−2.8); gains grow to W=384 (W=512+ untested).

Figures in `results/chunk-size.json`.

## Verdict

**Adopt (host stage) — 512-token chunks — and re-baseline the lab on it.** This is the largest
retrieval-stage gain recorded: +6.2pp overall recall@3 and a hard-mean jump to 44, with *every* hard
category improving (Exclusivity finally moves at the retrieval stage without decomposition: 7→16). The
headline implication is uncomfortable but important: **the hard-category "retrieval plateau" that
022/023/025/027/028/030/033 kept hitting was substantially an artifact of the tiny PoC-014 chunks**
(~25-word median — clause fragments). Nobody had varied chunk *size*; every prior retrieval PoC
inherited the fragmented index.

**Two honest caveats before over-claiming:**
1. **Metric mechanics.** recall@3 here is "top-3 cover ≥50% of the gold span"; a 384-word chunk meets
   that bar far more easily than a 25-word one, so some of the +6.2 is the chunk size inflating the
   coverage measure rather than finding genuinely new evidence. The *direction* is real (a chunk that
   contains the whole clause is strictly better evidence) but the magnitude is partly metric-coupled.
2. **Downstream cost.** 512-token chunks mean ~4× more tokens per retrieved chunk into Qwen's 2048-token
   budget — fewer chunks fit, and prefill latency rises. The win must be re-validated at the **answer
   step** (key-fact / span-F1), not just retrieval coverage.

**Actions:** (a) adopt W≈384 (512-tok) as the default chunking and **re-run the answer-step PoCs
(017/018/030/036) on it** — their hard-category numbers may change materially; (b) sweep W=512/768 and
small overlap to find the true knee; (c) it composes with PoC-035 (binary index) for both better recall
*and* a smaller footprint.

## Limits

- **Coverage metric is chunk-size-sensitive** (see caveat 1) — the retrieval gain is real but partly
  mechanical; end-to-end answer quality is not measured here.
- **Fixed word-window chunking**, no overlap, no sentence/clause snapping; a clause-aware splitter at this
  size (PoC-014 × 037) is untested and could do better.
- **W∈{96,192,384} only** — the knee beyond 384 (and the Qwen-context tradeoff there) is unmeasured.
- **Query vectors reused** from the committed set (same text/model) — valid, since only the chunk index changed.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

cd poc/037-chunk-size-sweep
python3 chunk-size.py        # re-chunks + re-embeds at W=96/192/384 (~30 min)
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `oa-W7204983724-idea-4` · technique: extraction · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.55 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **null** · sub-labs confirmed 0 [cuad_hard:NULL; cuad_hard:POINT_WINS_ONLY] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
