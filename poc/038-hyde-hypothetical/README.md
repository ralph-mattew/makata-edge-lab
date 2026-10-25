# PoC 038: HyDE (hypothetical document embeddings) for retrieval (OP-1/OP-2)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD) |
| Verdict | **Reject — HyDE backfires with a 1.5B generator.** Using Qwen2.5-1.5B to generate a hypothetical clause and embedding *that* as the retrieval vector **collapses** recall@3: 62.6 → **47.8 (−14.7pp)**, with every hard category worse (Exclusivity 6→2, Non-Compete 33→15, Change-of-Control 65→47). Qwen-1.5B's hypothetical clauses are generic/hallucinated and embed far from the real gold clauses, actively misleading retrieval. HyDE needs a strong generator; our weak on-device model is exactly the wrong fit — consistent with PoC-017/018/034 (the 1.5B generator is the system's weak link). See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | MohammadYehya/HypotheticalDocumentEmbeddings_HyDE — Implementation of HyDE for improvements over RAG. (https://github.com/MohammadYehya/HypotheticalDocumentEmbeddings_HyDE) |
| Registered | 2026-10-25 (this draft, before the first run) |

## Question

Does applying HyDE (hypothetical document generation via Qwen2.5-1.5B Q4 followed by embedding the generated passage instead of the raw question) to our CUAD/EmbeddingGemma hybrid stack change recall@3 by ≥+3pp over the current 61.4% baseline?

## Why it matters here

- HyDE shifts the embedding distribution from question-space to answer/document-space, which may better match how contract clause text is embedded — directly relevant to hard categories like Exclusivity where question-document lexical gap is large
- If recall@3 improves, it demonstrates that even a 1.5B generator can produce useful hypothetical passages for embedding (addressing OP-2's open question about which generation-based tricks survive a tiny generator)
- A positive result would justify combining HyDE with the freed ~235 MB RAM headroom from PoC-035 for a larger generator, attacking OP-8

## Hypothesis

The HyDE mechanism (Gao et al. 2022) generates a hypothetical answer document from the query using an LLM, then embeds that document rather than the query for retrieval. The source repo implements this pattern generically; we test whether Qwen2.5-1.5B Q4 can generate sufficiently useful hypothetical contract clause passages such that EmbeddingGemma embeddings of those passages outperform embeddings of raw questions on CUAD recall@3 — this transfer is entirely unverified, and the original HyDE paper used InstructGPT-class models, not a 1.5B quantized model.

- H1: HyDE with Qwen2.5-1.5B Q4 achieves recall@3 ≥ 64.4% (current 61.4% + 3pp) on the full CUAD eval set
- H2: HyDE improves hard-category recall@3 (Exclusivity / Non-Compete / Change-of-Control mean) by ≥+5pp over baseline, since the question-document gap is largest there
- H3: On-device latency for HyDE (generation + embedding) remains ≤ 5× the baseline retrieval latency, keeping the system usable on iPhone 15 Pro

## Method

Reuse the PoC 007/013 harness on CUAD 1,325 Q&A items. Implement HyDE: for each query, prompt Qwen2.5-1.5B Q4 to generate a short hypothetical contract clause passage (~100 tokens) that would answer the question; embed the generated passage with EmbeddingGemma 300M; retrieve using the existing 0.9/0.1 hybrid (or semantic-only as ablation). Compare recall@3 and per-category recall@3 against the 61.4% / 67.9% key-fact baseline. Also measure generation latency per query on-device. Use a bounded run (100–200 items) first to check direction before full eval.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the retrieval vector — raw-question embedding (baseline) vs HyDE (embed a Qwen-generated hypothetical clause, doc-side). **Held fixed:** the PoC-014 chunk index + committed vectors, EmbeddingGemma, BM25 on the original question terms, hybrid 0.9/0.1, top-3, the eval set. **Measurements:** overall + hard-category recall@3, HyDE vs raw. **Repetitions:** greedy generation (temp 0) → single pass.

## Decision rule

ADOPT if H1 (recall@3 ≥ 64.4%) AND H3 (latency ≤ 5× baseline) both hold. REJECT if recall@3 < 62.4% (+1pp) or if latency > 10× baseline making it unusable. INCONCLUSIVE if recall@3 is 62.4–64.3% (marginal gain, inspect hard-category breakdown before deciding).

## Expected outcome (engine estimate, not a result)

reject  ·  confidence 0.55  ·  est. effort 3-5 days (1 day prompt engineering + bounded run, 1-2 days full eval, 1 day analysis)

## Harness

`hyde.py` (Qwen :8091 + EmbeddingGemma :8090): per query, Qwen generates a hypothetical clause; it is
embedded doc-side and used as the retrieval vector. Measured on the SAME PoC-014 index as the baseline
(isolates HyDE) — recall@3 vs the raw-question embedding.

## Results

MEASURED on the host (Qwen2.5-1.5B Q4 + EmbeddingGemma), full CUAD (1,316 items), recall@3.

| Arm | overall | Exclusivity | Non-Compete | Change Of Control |
|---|---|---|---|---|
| raw question (baseline) | 62.6 | 6 | 33 | 65 |
| **HyDE** | **47.8 (-14.7)** | 2 | 15 | 47 |

- **H1 (recall@3 >= 64.4 / +3):** FAIL, catastrophically — HyDE is -14.7pp. Every hard category drops.
  MEASURED. (Decision rule: recall < 62.4 -> reject.)

## Verdict

**Reject.** HyDE assumes a generator strong enough to produce a hypothetical document that lands near the
true evidence in embedding space. Qwen2.5-1.5B Q4 is not that generator: its hypothetical clauses are
generic/boilerplate or hallucinated, so the HyDE vector pulls retrieval *away* from the gold clause --
recall@3 collapses 62.6 -> 47.8 and the hard categories are hit hardest (Non-Compete 33 -> 15). This is
the same lesson as PoC-017/018/034 from the retrieval side: **the on-device 1.5B generator is the weak
link, so any technique that routes the retrieval query *through* it loses.** HyDE would need a much
stronger generator (not available in the 6 GB budget) to help. The productive retrieval levers remain
chunk size (PoC-037) and decomposition (PoC-016/030) -- which reformulate the query with templates/
structure, not free generation.

## Limits

- **Tested with Qwen2.5-1.5B Q4 only** (the deployable model); HyDE with a frontier generator is a
  different, off-device question and not relevant to the 6 GB target.
- **One HyDE prompt / single generation** (greedy); multi-sample HyDE (average several hypotheticals)
  could denoise slightly, but a −14.7pp starting point will not become a win.
- **recall@3 only** on the PoC-014 index (to isolate HyDE); not combined with PoC-037 chunking.

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

cd poc/038-hyde-hypothetical
python3 hyde.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `gh-MohammadYehya/HypotheticalDocumentEmbeddings_HyDE-idea-10` · technique: extraction · attacks: OP-2
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.45 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **NOT_VALIDATABLE** · sub-labs confirmed - [-] · compose-retest - · slice-faithfulness-risk -
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
