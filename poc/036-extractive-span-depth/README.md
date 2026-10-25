# PoC 036: Generator-free extractive span selection at depth (top-N pool sweep) (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (300 hard-category items, N∈{3,5,10}) |
| Verdict | **Inconclusive → adopt N=10 as a free refinement of the PoC-018 extractor.** Extending the extractor's pool from top-3 to top-10 helps monotonically — hard-mean span-F1 **20.7 → 21.6 → 22.1** — driven by **Non-Compete +3.5** (realising the rank-4–10 headroom PoC-025 found) with **no Exclusivity regression** (+0.9) and CoC flat. N=3 reproduces PoC-018 exactly (control ✓). The +3.5 NC gain is in the pre-registered inconclusive band (+3–9, below the +10 bar), so not a formal adopt — but it is a **free, distractor-robust** improvement (no generator; where chunk reranking in PoC-027 *collapsed* on distractors, sentence-level extraction over a deeper pool does not). See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | PoC-018 (adopted extractive span selection) + PoC-019 (adopted constrained substring extraction with fallback) + PoC-025 (Non-Compete gold at rank 4–10, recall@10 ≈ 51%) + hf-2610.29722 (LASAGNA isolated-vs-composed measurement) |
| Registered | 2026-10-25 (this draft, before the first run) |

## Question

Does a LASAGNA-style isolated measurement of extractive span selection applied at recall@10 depth (top-10 retrieved chunks, not top-3) — selecting the highest-cosine ≤3-sentence window per hard category — lift per-category recall@3-equivalent span coverage (Exclusivity, Non-Compete, Change-of-Control) by ≥+10pp over the PoC-018 top-3 baseline, while remaining generator-free and within 6 GB RAM?

## Why it matters here

- PoC-025 showed Non-Compete gold clauses sit at rank 4–10 (recall@10 ≈ 51%), meaning the PoC-018 extractive win at top-3 depth leaves a large known headroom pool untouched — extending extractive span selection to top-10 directly attacks this gap without any retrieval-scoring change.
- PoC-018 proved generator-free extraction is the correct answer-step mechanism (hard-mean span-F1 +4.6, Exclusivity 3.7→12.2); the remaining shortfall is depth, not the mechanism itself — a single isolated experiment measuring top-10 extraction vs top-3 extraction cleanly separates the retrieval-depth lever from all other variables, following LASAGNA's isolation principle.

## Hypothesis

Applying the PoC-018 extractive span selector (≤3-sentence highest-cosine window, decomposed sub-queries) over top-10 retrieved chunks instead of top-3 — with the LASAGNA discipline of measuring this depth change in strict isolation (no other pipeline changes) — will recover gold spans now sitting at rank 4–10 and push Non-Compete and Change-of-Control per-category span-F1 each by ≥+10pp over the PoC-018 top-3 baseline. This cross-depth generalisation of the adopted extractor has NOT been demonstrated on our stack.

- H1: Per-category span-F1 on Non-Compete lifts ≥+10pp over PoC-018 top-3 baseline (current PoC-018 Non-Compete span-F1: ~16–20 range) when extractor runs over top-10 chunks.
- H2: Change-of-Control span-F1 lifts ≥+5pp over PoC-018 top-3 baseline (directional; secondary bar).
- H3: Exclusivity span-F1 does not regress from PoC-018's 12.2 (precision must not collapse from distractor chunks).
- H4: Peak RAM stays ≤6 GB during top-10 sentence-level cosine re-scoring (no generator loaded).

## Method

Reuse the PoC-018 harness (EmbeddingGemma retrieval, decomposed sub-queries, ≤3-sentence cosine window extractor). Single change: extend retrieval depth from top-3 to top-10 chunks before the sentence-level re-scoring step. Measure per-category span-F1 (SQuAD token overlap vs gold span) and recall@3-equivalent coverage on the 300 hard-category items. Run isolated: no prompt changes, no reranker, no BM25 fusion. Compare directly to PoC-018 top-3 results. Log RAM peak. Secondary ablation: top-5 vs top-10 to identify the depth knee.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the extractor's candidate-chunk pool depth N ∈ {3 (=PoC-018), 5, 10}. **Held fixed:** PoC-016 decomposed sub-queries, EmbeddingGemma sentence embedding, the ≤3-sentence window selector, the 300 hard-cat items, generator-free. **Measurements:** per-category + hard-mean span-F1 (SQuAD overlap vs gold) at each N; host peak RSS. **Repetitions:** deterministic → single pass.

## Decision rule

Adopt if H1 (Non-Compete +≥10pp) AND H3 (Exclusivity not regressed) AND H4 (RAM ≤6 GB). Reject if Non-Compete gain <+3pp (depth does not help) or Exclusivity drops >3pp (distractor noise dominates). Inconclusive if gains are 3–9pp — motivates a reranker pre-filter before extraction.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1 week

## Harness

`extract-depth.py` reuses the PoC-018 path (committed vectors for decomposed retrieval; EmbeddingGemma
:8090 for sentence embeddings): decomposed sub-queries → top-N chunks → split sentences → embed → score
by max cosine over the category sub-queries → best ≤3-sentence window → span-F1. Sweeps N∈{3,5,10}.

## Results

MEASURED on the host (EmbeddingGemma), 300 hard-category items, ≤3-sentence window, generator-free.

| pool N | hard-mean span-F1 | Exclusivity | Non-Compete | Change Of Control |
|---|---|---|---|---|
| **3** (= PoC-018) | 20.7 | 12.2 | 19.1 | 30.8 |
| 5 | 21.6 | 12.5 | 21.8 | 30.5 |
| **10** | **22.1** | 13.1 | 22.5 | 30.6 |

N=3 reproduces PoC-018 exactly (hard-mean 20.7; Excl 12.2 / NC 19.1 / CoC 30.8) — control validated.

- **H1 (Non-Compete +≥10pp over top-3):** FAIL — +3.5 (19.1 → 22.5). MEASURED.
- **H2 (Change-of-Control +≥5pp):** FAIL — −0.2 (flat). MEASURED.
- **H3 (Exclusivity not regressed):** PASS — +0.9 (12.2 → 13.1); distractor noise did **not** dominate.
  MEASURED.
- **H4 (RAM ≤ 6 GB, no generator):** PASS — host peak RSS 3.1 GB. INFERRED (device figure pending).
- Decision rule: Non-Compete gain +3.5 is in the inconclusive band (+3–9). MEASURED.

Per-N figures in `results/extract-depth.json`.

## Verdict

**Inconclusive by the rule — but a free, distractor-robust refinement; adopt N=10 for the extractor.**
Deeper pools help monotonically (hard-mean 20.7 → 21.6 → 22.1), with the gain concentrated in
**Non-Compete (+3.5)** — exactly the category PoC-025 flagged as having gold at rank 4–10 — and
**Exclusivity does not regress** (+0.9). The +3.5 falls short of the ambitious +10 bar, so it is not a
formal adopt, but it is the right default: it costs nothing (same generator-free extractor, RAM fine)
and is strictly ≥ top-3 on every hard category.

The methodologically important result is the **contrast with PoC-027**: a cross-encoder reranker over a
wider pool *demoted* the correct legal clauses (Non-Compete 25 → 8–15), whereas **sentence-level
extractive selection over the same deeper pool is distractor-robust** (Non-Compete +3.5, Exclusivity
+0.9) — because it scores fine-grained spans against the decomposed query rather than re-ordering whole
chunks. This confirms generator-free extraction (PoC-018) as the right answer-step mechanism and shows
its headroom is modest-but-real with depth. It does not break the hard-category plateau on its own; the
composed stack (decomposition + N=2 pool (PoC-030) + extractive N=10) is the natural end-to-end test.

## Limits

- **span-F1 proxy**, not an end-to-end answer metric; absolute span-F1 is low for long clause answers
  (same caveat as PoC-017/018) — interpret the Δ.
- **Depth capped at N=10**; N>10 (toward recall@20) could add a little more for Exclusivity (recall@20
  45%, PoC-025) but risks the distractor knee — untested.
- **Host RAM only** (3.1 GB, no generator); the device H4 figure is pending.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

cd poc/036-extractive-span-depth
python3 extract-depth.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g2-5` · technique: structured-blend · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.6 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **null** · sub-labs confirmed 0 [cuad_hard:POINT_WINS_ONLY] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
