# PoC 027: Cross-encoder reranking of a hybrid top-10 pool (OP-1) — executes PoC-012 host stage

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, two rerankers) |
| Verdict | **Reject.** Off-the-shelf cross-encoders do not realise the headroom PoC-025 found — they *degrade* the hard categories. `ms-marco-MiniLM-L-6-v2`: overall 61.8 → 63.0 (+1.2, within CI; H1 needs +3) but **Non-Compete 25 → 15 (−10)**, Change-of-Control −7. `bge-reranker-base`: catastrophic (overall 61.8 → **49.3**, Non-Compete 25 → 8). PoC-025 proved Non-Compete gold *is* at rank 4–10 (recall@10 51%), so the ceiling exists — but neither general-domain reranker reaches it; both demote the correct legal clauses. Reranking with available models is not the lever; a legal-domain reranker would be needed (unverified). This also closes PoC-012. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Scan or Index? Large Evidence Coverage, Answer Quality, and Cost in Long-Document RAG (http://arxiv.org/abs/2610.28957v1); promoted from the 2026-10-22 DIVERGENT ideation-engine scan. Executes the host stage of the parked [PoC-012](../012-cross-encoder-reranking). |
| Registered | 2026-10-22 (this draft, before the first run) |

## Question

Does a Hybrid+reranking configuration (semantic + BM25 candidates fed to a lightweight cross-encoder reranker) raise recall@3 on CUAD hard categories (Exclusivity, Non-Compete, Change-of-Control) by ≥5 points over the current 0.9/0.1 hybrid baseline?

## Why it matters here

- PoC-013 showed hard categories are invariant to retrieval-weight tuning; a reranking step after candidate retrieval is a structurally different mechanism that could reorder within a fixed candidate pool and surface the correct chunk
- The paper found Hybrid+reranker achieved the highest evidence coverage (94.1%) on long documents, suggesting the combination captures evidence that either component alone misses
- If even a small lift in hard-category recall transfers, it unblocks the single highest-value bottleneck in the current system

## Hypothesis

The source ran hybrid+reranker on QASPER/textbook corpora with unspecified dense embedders and cloud-based rerankers (Jev, OpenAI Decisions); we test the same structural mechanism — a hybrid candidate pool reranked by a cross-encoder — using EmbeddingGemma 300M + BM25 candidates passed to a small cross-encoder (PoC-012 design) on CUAD, measuring per-category recall@3 on hard categories. This transfer is unverified because: corpus domain differs (legal vs scientific/textbook), the source's reranker is cloud-scale, and our candidate pool size and chunk length differ.

- H1: Hybrid+cross-encoder reranking raises overall recall@3 by ≥3 points above the 61.4% baseline (current: 61.4%)
- H2: Per-category recall@3 on at least one hard category (Exclusivity ~11%, Non-Compete, Change-of-Control) improves by ≥5 points over the 0.9/0.1 hybrid baseline
- H3: End-to-end latency per query on iPhone 15 Pro remains ≤4 seconds (cross-encoder inference budget)

## Method

Reuse PoC-012/PoC-007 harness on CUAD 1,325 Q&A items. Retrieve top-10 candidates via 0.9/0.1 hybrid (current baseline), then rerank with a small on-device cross-encoder (e.g. ms-marco-MiniLM-L6 quantised to fit ≤300MB). Return top-3 after reranking. Measure overall recall@3, per-category recall@3 for Exclusivity, Non-Compete, Change-of-Control, and wall-clock latency. Compare against baseline (61.4% recall@3). PoC-012 registered this device hypothesis; this PoC executes it with explicit hard-category focus.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT if H1 (≥3-point overall lift) AND H2 (≥5-point lift on ≥1 hard category) AND H3 (latency ≤4s). REJECT if overall recall@3 < 62.4% (less than +1 point). INCONCLUSIVE if H1 holds but H2 does not, or H2 holds but H3 fails.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1-2 weeks (cross-encoder quantisation + integration into existing harness + per-category evaluation)

## Harness

`rerank.py` retrieves the hybrid 0.9/0.1 top-10 (committed PoC-014 vectors), reranks the 10 chunk
texts against the question with a sentence-transformers `CrossEncoder`, takes top-3, and measures
recall@3 overall + per category vs the hybrid top-3 baseline (contract-level bootstrap CI). No llama
server. Two rerankers run: `cross-encoder/ms-marco-MiniLM-L-6-v2` (small/fast) and
`BAAI/bge-reranker-base` (stronger/heavier).

## Results

MEASURED on the host (MPS), full CUAD 1,316 items, hybrid top-10 pool → rerank → top-3. The PoC-025
ceiling (a *perfect* top-10 reranker = recall@10) is overall 79 / Non-Compete 51 / Exclusivity 25 /
Change-of-Control 78.

| Arm | overall recall@3 | Non-Compete | Exclusivity | Change Of Control | host latency |
|---|---|---|---|---|---|
| hybrid top-3 (baseline) | 61.8 | 25.0 | 7.0 | 67.0 | — |
| + MiniLM rerank | 63.0 (CI 60.5–65.6) | **15.0 (−10)** | 6.0 (−1) | 60.0 (−7) | 41 ms/q |
| + BGE-reranker-base | **49.3** | 8.0 (−17) | 2.0 (−5) | 54.0 (−13) | 220 ms/q |

- **H1 (overall +≥3):** FAIL — MiniLM +1.2 (CI includes the baseline); BGE −12.5. MEASURED.
- **H2 (≥1 hard category +≥5):** FAIL — every hard category *regresses* under both rerankers; the
  greenlit Non-Compete drops 10–17 points. MEASURED.
- **H3 (on-device latency ≤4s):** not evaluated — device-bound, parked (host rerank is 41–220 ms/q,
  INFERRED).

Per-reranker JSON in `results/rerank-minilm.json`, `results/rerank-bge.json`; summary in
`results/comparison.txt`.

## Verdict

**Reject.** The headroom is real but unreachable with off-the-shelf rerankers. PoC-025 proved
Non-Compete gold sits at rank 4–10 (recall@10 = 51%), so a reranker *could* in principle roughly
double Non-Compete recall@3 — but both a small MS-MARCO cross-encoder and a stronger BGE reranker
instead **demote the correct legal clauses**, dropping Non-Compete to 15 and 8 respectively and
pulling every hard category down. General-domain rerankers trained on web/MS-MARCO relevance do not
transfer to CUAD clause matching (long, boilerplate-heavy legal text where the "relevant" chunk is
not the most lexically/semantically query-similar). Overall recall is flat-to-worse.

**Implications:**
- **Reranking is not the OP-1 lever** with available models. Closing [PoC-012](../012-cross-encoder-reranking)
  too: its host stage doesn't even clear the bar, so the device-stage latency/RAM question is moot.
- The only path to the PoC-025 Non-Compete headroom would be a **legal-domain-tuned cross-encoder**
  (fine-tuned on CUAD relevance pairs) — unverified, a training effort, and out of scope here.
- Combined with PoC-023 (weighting) and PoC-022 (embedder swap), **every retrieval-stage lever has
  now failed on the hard categories.** The durable movers remain query decomposition (PoC-016) and
  the answer step (PoC-018).

## Limits

- **Two off-the-shelf rerankers only** — a CUAD-fine-tuned cross-encoder is untested and is the one
  remaining way the PoC-025 headroom could be captured.
- **Pool = top-10.** A wider pool (top-20) would raise the Exclusivity ceiling (recall@20 45%) but not
  help if the reranker can't score legal relevance correctly — which it can't here.
- **Chunk length.** CUAD page chunks are long; cross-encoders truncate, which may contribute to the
  mis-ranking. A clause-aware chunking (PoC-014 alt) + reranker combo is untested.

## Reproduce

```bash
cd poc/027-hybrid-reranking
python3 rerank.py                                  # ms-marco-MiniLM-L-6-v2
python3 rerank.py --model BAAI/bge-reranker-base   # stronger/heavier
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `arxiv-2610.28957v1-idea-6` · technique: extraction · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.65 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [semantic:NULL; numeric:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22-divergent. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
