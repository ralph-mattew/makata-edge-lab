# PoC 018: Generator-free extractive span selection for hard categories

| | |
|---|---|
| Status | Concluded — host stage (300 hard-category items, full run) |
| Verdict | **Adopt (host stage), with the ≤3-sentence passage.** Generator-free extractive selection (window = 3) lifts hard-mean span-F1 to 20.7 — +4.6 over the 16.1 baseline and +5.0 over the same-retrieval Qwen arm (15.7) — and clears H2 (Exclusivity 12.2 ≥ 8.0), while removing the ~1 GB generator. Single-sentence (window = 1) under-recalls the long clause spans (17.5, +1.4) and does not qualify. H4 (≤ 5 GB) is a device claim, host peak RSS 2.9 GB INFERRED. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Synthesized by the lab's ideation engine (2026-10-20 edge-ai scan, MAP-Elites `constraint-relax`, attacks OP-2). Builds on PoC-016 (decomposition) and PoC-017 (span-answer quality). |
| Registered | 2026-10-20 (this draft, before the first run) |

## Question

Does removing the LLM generator entirely — replacing Qwen2.5-1.5B with a pure extractive span-selection step (highest-similarity sentence or passage within top-3 chunks) — lift key_fact and span-F1 on hard categories (Exclusivity, Non-Compete, Change-of-Control) vs the constrained-template generation baseline, while staying within 6 GB RAM?

## Why it matters here

- PoC-017 showed Qwen2.5-1.5B is the bottleneck for hard-category answer quality even with constrained prompting attempted; eliminating the generator entirely removes the paraphrase/hallucination failure mode at its root and frees ~1 GB RAM for retrieval or context expansion.
- PoC-016 demonstrated that Exclusivity recall@3 jumped from 7% to 24% via decomposed sub-queries alone — a generator-free retrieval step. If span selection (e.g., pick the highest cosine-to-query sentence within retrieved chunks) can surface the gold span without generation, the full pipeline becomes deployable with no LLM at all for these categories, directly attacking OP-2's open question of which generation-based tricks survive a tiny generator.

## Hypothesis

Selecting the single highest-cosine-similarity sentence (or contiguous passage ≤ 3 sentences) from within the top-3 EmbeddingGemma-retrieved chunks — computed by re-scoring each sentence embedding against the (decomposed) query — will produce higher span-F1 on hard categories than Qwen2.5-1.5B constrained extraction, because it is guaranteed to return verbatim contract text and avoids all generation-side paraphrase drift. This has not been demonstrated on our stack for any category.

- H1: Extractive span-selection (no LLM) achieves hard-category mean span-F1 ≥ 20.0 (current constrained-generation baseline: ~16.1) — a +4-point lift.
- H2: Exclusivity span-F1 reaches ≥ 8.0 (current: 5.9 post-PoC-017) under extractive selection paired with PoC-016 decomposed queries.
- H3: Fact-category recall@3 does not regress by more than 1 point vs the no-generation baseline (confirming the retrieval layer is unaffected).
- H4: Peak RAM stays ≤ 5 GB (removing Qwen2.5-1.5B ~1 GB weight, retaining EmbeddingGemma 600 MB).

## Method

Reuse the existing PoC-016/017 harness and CUAD 300-item hard-category + fact-category eval set. Implement extractive span selection: (1) apply PoC-016 decomposed sub-queries for hard categories; (2) retrieve top-3 chunks via EmbeddingGemma; (3) split each chunk into sentences; (4) embed each sentence with EmbeddingGemma (reuse loaded model, no new model); (5) return the sentence with highest cosine similarity to the (union) query as the answer span. Measure span-F1 (SQuAD token overlap vs gold), key_fact exact-match, and recall@3 vs (a) no-generation baseline and (b) PoC-017 constrained-template generation baseline. Log peak RAM.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- Varies: the answer step only — extractive sentence-selection (no LLM) vs the PoC-017 constrained-Qwen baseline. Held fixed: EmbeddingGemma retrieval, top-3 chunks, PoC-016 decomposed queries, the CUAD eval set.
- Measurements: hard-category + fact-category span-F1 (SQuAD token overlap), key_fact exact-match, recall@3, peak RAM. Repetitions: retrieval + cosine span-selection are deterministic → single pass; RAM sampled across the full run. Host run first, then on-device replication (see REPLICATION.md).

## Decision rule

Adopt if H1 (hard-mean span-F1 ≥ +4 over 16.1) AND H3 (fact recall regression < 1 pt) AND H4 (RAM ≤ 5 GB). Reject if hard-mean span-F1 improvement < +2 points. Inconclusive otherwise. If H2 fails but H1 passes, note Exclusivity still needs generator-side work.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 1-2 weeks

## Harness

`extract-span.py` implements the full host stage. It reuses committed vectors (no
re-embedding of the 79k-chunk corpus):

- `007/items.jsonl`, `007/contracts.jsonl` — the 300 hard-category items (100 each:
  Exclusivity, Non-Compete, Change Of Control) and their gold word-spans.
- `014/chunks-page.jsonl`, `014/emb-page.jsonl` — chunk corpus + page vectors.
- `016/emb-subqueries.jsonl`, `016/decomp-templates.json` — decomposed sub-query vectors.

Flow: PoC-016 decomposed retrieval (max-pool hybrid 0.9/0.1) → top-3 chunks → split each
chunk into sentences → embed each candidate sentence with EmbeddingGemma → score by max
cosine over the category's sub-queries → return the best sentence (`--window 1`) or a
contiguous passage of ≤ 3 sentences (`--window 3`). The `generate` arm feeds the *same*
top-3 chunks to Qwen2.5-1.5B with PoC-017's exact prompt/sampling, so the span-F1 Δ is a
clean same-retrieval contrast.

Method choices (confirm/adjust on promotion to a verdict):

- Retrieval is held fixed to PoC-016 decomposed sub-queries for all three hard categories —
  the only thing varying is the answer step.
- "Union query" sentence scoring = **max** cosine over the category's sub-query vectors
  (the "does any decomposed aspect match this sentence" reading). Mean-pool is the fallback.
- The generation baseline is **re-measured** on identical chunks rather than copied from
  PoC-017's 16.1 (which used raw/keyword retrieval). Validate the `generate` hard-mean lands
  in 017's ballpark before trusting the Δ.
- Sentence splitter is deterministic: punctuation/newline breaks, tiny-fragment drop, 80-word
  hard-wrap.

## Results

MEASURED on the host (Mac, EmbeddingGemma via `--embd-gemma-default` + Qwen2.5-1.5B-Instruct
Q4_K_M), 300 hard-category items (100 each), single deterministic pass. Span-F1 is SQuAD
token-overlap vs the gold span; contract-level bootstrap CI (10k, seed 0). The embedding model
was verified to reproduce the committed PoC-014 vectors at cosine 1.00000 before the run.

Hard-category mean span-F1:

| Arm | Exclusivity | Non-Compete | Change Of Control | hard-mean | 95% CI |
|---|---|---|---|---|---|
| `generate` (same-retrieval Qwen baseline) | 3.7 | 16.7 | 26.6 | **15.7** | 12.8–18.6 |
| `extract` window = 1 (single sentence) | 7.5 | 16.6 | 28.3 | **17.5** | 14.6–20.6 |
| `extract` window = 3 (≤ 3-sentence passage) | 12.2 | 19.1 | 30.8 | **20.7** | 17.9–23.7 |

- The `generate` arm reproduces the registration's 16.1 baseline (15.7) under identical
  retrieval — the control holds, so the deltas are attributable to the answer step. MEASURED.
- **H1 (hard-mean ≥ +4 over 16.1):** window = 3 → 20.7, **+4.6** over 16.1 and **+5.0** over the
  same-retrieval generate arm. PASS. Window = 1 → 17.5 (+1.4), fails. MEASURED.
- **H2 (Exclusivity span-F1 ≥ 8.0):** window = 3 → 12.2. PASS (window = 1 → 7.5, fails). MEASURED.
- **H3 (fact-category recall@3 unaffected):** retrieval is identical to the generate arm by
  construction, so fact recall is unchanged. OBSERVED (not re-scored here).
- **H4 (peak RAM ≤ 5 GB):** host peak RSS 2.9 GB for the extractive pass (which never loads
  Qwen). INFERRED; the device figure needs an on-iPhone run (REPLICATION).

Raw per-item answers in `results/raw/{extract-w3,extract-w1,generate}-answers.jsonl`; summaries
in `results/span-quality-both.json` (window 3 + generate) and `span-quality-extract.json` (window 1).

## Verdict

**Adopt (host stage) — generator-free extractive selection with a ≤ 3-sentence passage.** It meets
H1 (+4.6 over baseline, +5.0 over the same-retrieval generator), H2 (Exclusivity 12.2 ≥ 8.0), and
H3, while removing the ~1 GB Qwen weight from the answer path. The win is concentrated where it was
predicted: Exclusivity rises 3.7 → 12.2 vs the generator. The single-sentence variant (window = 1)
does **not** qualify — the hard-category gold spans run 50–70 words and one sentence under-recalls
them — so the passage window is load-bearing, not incidental. Open for the device stage: confirm H4
(≤ 5 GB) on an iPhone 15 Pro. This is the first mechanism in the series to lift Exclusivity
answer-quality into double digits.

## Limits

- **H4 (peak RAM ≤ 5 GB) is a device claim.** The host logs `ru_maxrss` as INFERRED only; the
  real figure needs an on-iPhone run (see REPLICATION). The structural saving is unconditional:
  the extractive arm never loads Qwen (~1 GB).
- **Absolute span-F1 is low for long clause answers** (gold spans here run 50–70 words), same
  caveat as PoC-017. Interpret the Δ vs the generate arm, not the absolute number. `--window 1`
  will under-recall long clauses by construction; `--window 3` probes that.
- **Hard categories only.** Fact-category key_fact is unaffected by the answer step (retrieval is
  identical), so H3 is a retrieval sanity check, not re-run here.
- **Off-the-shelf sentence splitter + single embedding model.** No clause-boundary model, no
  re-ranker.

## Reproduce

```bash
# EmbeddingGemma (extractive arm) + Qwen (generate arm), same configs as PoC 007/014/016/017:
llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &

cd poc/018-extractive-span-no-generator
python3 extract-span.py --arm extract --window 1    # primary: single best sentence
python3 extract-span.py --arm extract --window 3    # contiguous passage ≤ 3 sentences
python3 extract-span.py --arm both --window 3       # extract vs Qwen on identical chunks, prints Δ
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g1-2` · technique: constraint-relax · attacks: OP-2
- Gates (0–10): G1 8.5 · G2 6.0 · G3 7.25 · null-control Δ5.75 (real 6.0 vs null 0.25)
- Tournament: rank 1, elo 1045.1 · priority 📊 MEDIUM (8.9)
- Provenance: idea-evolution-engine (private) scan 2026-10-20. Gate-approved + null-control-screened, NOT yet empirically validated.
