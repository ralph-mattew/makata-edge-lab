# PoC 039: Composed hard-category pipeline — 512-token chunks + decomposition + N=2 pool + generator-free extractive selection at depth (OP-1/OP-2)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** This README is the pre-registration (hypotheses + decision rule fixed before the first run). |
| Verdict | _pending — do not fill until the run concludes._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Lab-internal capstone composition, explicitly called for in **PoC-036's verdict** ("the composed stack — decomposition + N=2 pool (PoC-030) + extractive N=10 — is the natural end-to-end test"), now extended with the **PoC-037** chunk-size finding (W≈384 ≈ 512 tokens, +6.2 recall@3). Recombines five concluded PoCs: 016 (template decomposition), 030 (per-sub-query N=2 pool), 018 (generator-free extractive span selection), 036 (extractive depth N=10), 037 (fixed 512-token chunks). Parallel engine proposal held in `_inbox` (`…-a-twostage-retrieval-pipeline-1-perhardcategory-deterministic-subquery`). |
| Registered | 2026-10-25 (this draft, before the first run) |

## Question

Does **composing** the individually-validated hard-category levers into one end-to-end stack —
**512-token fixed-window chunks** (PoC-037) → **template sub-query decomposition** (PoC-016) with a
**per-sub-query candidate pool of N=2** (PoC-030) → **generator-free extractive ≤3-sentence span
selection over the top-10 chunks** (PoC-018/036) — lift **hard-category span-F1** (the end-to-end
answer metric, Exclusivity / Non-Compete / Change-of-Control) by **≥+10 points over the best single
component** and clear a **hard-mean span-F1 ≥ 30**, while remaining **generator-free and ≤ 6 GB RAM**?

## Why it matters here

- Every prior hard-category PoC moved **one lever in isolation** and landed short of the standing +10
  ambition: decomposition (016) lifted Exclusivity 7→24 but hard-mean only +6; N=2 pooling (030) reached
  the lab-best retrieval hard-mean 39.3 (+3.7 over 016); the generator-free extractor (018/036) reached
  span-F1 hard-mean 22.1 at depth N=10. None was tested **together**, so we do not know whether the gains
  **compose (additive)** or **overlap (redundant)**. PoC-036's verdict names this composition as the
  natural next experiment.
- **PoC-037 reframed the plateau.** The hard-category "ceiling" was substantially a *chunk-fragmentation
  artifact*: every retrieval PoC (016/030 included) ran on the tiny ~25-word PoC-014 chunks. Moving to
  W≈384 (~512-token) chunks lifted raw-query recall@3 +6.2 and hard-mean to ~44 — but 037's own caveat was
  that 512-token chunks cost **~4× Qwen context** at the answer step. **This pipeline dissolves that caveat:
  the answer step is generator-free (extractive), so there is no Qwen context to inflate** — the bigger,
  higher-recall chunks become *free*. The two findings (037 bigger chunks, 018 no generator) are
  complementary, and this is the first PoC to combine them.
- If the composition clears the bar, it is a **deployable 6 GB stack with no LLM in the answer path** for
  the hard categories — the strongest practical outcome the series can produce.

## Hypothesis

The four levers attack **different** failure modes — chunk fragmentation (037), multi-facet queries
(016), rank-4–10 near-misses (030/036), and generation paraphrase drift (018) — so composing them should
be **at least partly additive**, not redundant. No source, and no prior PoC, has measured these five
mechanisms together on our stack; the composition is the untested leap.

- **H1 (headline):** the full composition reaches **hard-mean span-F1 ≥ 30** — i.e. **≥ +8 over the
  PoC-036 best extractor (22.1, old chunks)** and **≥ +14 over the production generate baseline (~15.7,
  PoC-018 same-retrieval Qwen arm)**.
- **H2 (chunk-size converts through the pipeline):** the full composition on 512-token chunks beats the
  same composition on PoC-014 chunks by **≥ +3 hard-mean span-F1** — the 037 recall gain survives
  decomposition + pooling + extraction, it is not a raw-query-only artifact.
- **H3 (composition is additive, LASAGNA diagnosis):** the composed hard-mean span-F1 exceeds the **best
  single lever alone** by **≥ +3**. If composed ≈ best single lever, the levers are redundant and the
  simplest one should ship instead.
- **H4 (feasibility — the generator-free dividend):** peak RSS stays **≤ 6 GB** with **no generator
  loaded**, confirming that 037's ~4× context cost is neutralised by removing Qwen from the answer path.
- **H5 (no collateral damage):** fact-category key-fact / recall@3 does **not** regress — non-hard items
  keep the raw-query path and the existing answer step unchanged.

## Method

Compose the already-committed, already-validated components; **vary only the composition**, and measure
an **isolated → composed ladder** (LASAGNA isolation discipline) so each lever's marginal contribution is
attributable. All arms use the **generator-free ≤3-sentence extractive selector** as the answer step
(PoC-018/036) unless labelled `generate`.

**Chunk index.** Reuse PoC-037's committed **W=384** fixed-window chunks + EmbeddingGemma vectors if
present; otherwise regenerate deterministically via `037/chunk-size.py --window 384` (re-chunk all 397
contracts, re-embed via `--embd-gemma-default`, recompute gold-span coverage against the new boundaries).
The old PoC-014 (~25-word) chunk index is retained only for the chunk-size-contrast arm (B1).

**Retrieval.** Hard categories use PoC-016 template sub-queries (reuse `016/emb-subqueries.jsonl`,
`016/decomp-templates.json`) with PoC-030's per-sub-query pool **N=2**, union + dedupe, re-rank by max
sub-query hybrid score (0.9 semantic / 0.1 BM25, PoC-013), take the **top-10** chunks for the extractor.
Non-hard items use the raw single-query path (held fixed, for H5).

**Answer step.** Split each of the top-10 chunks into sentences (deterministic splitter from PoC-018),
embed each candidate sentence with EmbeddingGemma, score by **max cosine over the category's sub-query
vectors**, return the best contiguous **≤3-sentence window** (PoC-018 window=3). Generator-free.

**Arms (ladder).**

| Arm | Chunks | Query | Depth | Answer step | Isolates |
|---|---|---|---|---|---|
| `B0` production baseline | 014 (~25w) | raw | top-3 | Qwen generate (PoC-017 prompt) | the shipped stack |
| `B1` best old-chunk extractor | 014 | decomp + N=2 | top-10 | extractive ≤3-sent | composition **without** 037 |
| `C1` chunk-size only | **384** | raw | top-10 | extractive ≤3-sent | 037 chunk size, levers off |
| `C2` **full composition** | **384** | decomp + N=2 | top-10 | extractive ≤3-sent | **the headline stack** |

Single-lever isolation arms (decomp-only, N2-only, extractor-only) on 384 chunks are added as needed to
resolve H3's additivity decomposition.

- Baseline stack (confirm exact files/SHA-256 at run): EmbeddingGemma 300M (~270 MB QAT Q4_0, via
  `--embd-gemma-default`), Qwen2.5-1.5B Q4_K_M (B0 only), hybrid 0.9/0.1 (PoC-013).
- Device: iPhone 15 Pro (6 GB) target; host stage on Mac16,8 M4 Pro first.
- Dataset: CUAD (397 contracts); **300 hard-category items** (100 each) for span-F1; full 1,316-item set
  for the H5 fact-category sanity check.
- **Measurements:** per-category + hard-mean **span-F1** (SQuAD token overlap vs gold), recall@3-equiv
  coverage, host peak RSS; contract-level bootstrap CI (10k, seed 0). **Repetitions:** deterministic
  (fixed vectors + cosine extraction) → single pass; RAM sampled across the run.

## Decision rule

Written before the first run.

- **Adopt** the composed pipeline as the hard-category default if **H1** (composed hard-mean span-F1 ≥ 30)
  **AND H2** (512-token chunks add ≥ +3 through the full pipeline) **AND H4** (≤ 6 GB, generator-free).
- **Reject** if the composition does **not** beat the best single component (**H3 fails**, composed ≤ best
  single lever) — the levers are redundant and we ship the single cheapest one instead.
- **Inconclusive** if the composition beats every single component (H3 passes) but misses H1's +10 / ≥30
  bar — report the per-lever additivity decomposition and the best operating point as the live lead.
- Report **per-category** deltas prominently (Exclusivity remains the worst category; a stack that fixes
  it specifically is notable even at a modest mean).

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.50  ·  est. effort 1 week

## Harness (to be implemented at run time — not yet written)

`pipeline.py` will reuse committed vectors end-to-end (no corpus re-embedding beyond 037's W=384 index):
decomposed sub-queries → per-sub-query top-2 → union/rerank → top-10 chunks → sentence split → embed
(EmbeddingGemma :8090) → max-cosine ≤3-sentence window → span-F1. The `B0` arm calls Qwen (:8091) with
PoC-017's exact prompt/sampling on the same retrieval for a clean same-retrieval contrast. Each arm writes
`results/raw/<arm>-answers.jsonl` + a `results/pipeline.json` summary and a `comparison.txt` H1–H5
read-out. **Control to validate before trusting deltas:** `C1`/`B1` must reproduce PoC-037 recall@3 and
PoC-036 span-F1 respectively on their own chunk indexes.

## Reproduce (planned)

```bash
# EmbeddingGemma for sentence + chunk embeddings; Qwen only for the B0 generate baseline:
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &  # B0 only

cd poc/039-composed-hardcat-pipeline
# (reuse ../037-chunk-size-sweep W=384 index if committed, else: python3 ../037-chunk-size-sweep/chunk-size.py --window 384)
python3 pipeline.py --arm B0          # production baseline (Qwen generate, 014 chunks)
python3 pipeline.py --arm B1          # composition on old 014 chunks (chunk-size contrast)
python3 pipeline.py --arm C1          # 512-token chunks, raw query (chunk-size isolation)
python3 pipeline.py --arm C2          # full composition — headline
python3 pipeline.py --compare         # H1–H5 read-out + per-lever additivity table
```

---

### Engine provenance (how this idea was generated)

- Lab-internal **capstone composition** (not a single engine inbox drop): the recombination of PoC-016 ×
  030 × 018 × 036 × 037 was called for explicitly in PoC-036's verdict. The ideation engine's parallel
  suggestion — a two-stage per-hard-category deterministic-subquery retrieval pipeline — is held in
  `poc/_inbox/2026-10-25-a-twostage-retrieval-pipeline-1-perhardcategory-deterministic-subquery` and
  overlaps the retrieval half of this stack.
- Provenance: idea-evolution-engine (private) ground-truth ledger covers PoC-006..038; this PoC will feed
  the 039 verdict back after the run (ADOPT/REJECT/INCONCLUSIVE). Gate-approved composition of
  null-control-screened parents; **NOT yet empirically validated** — the lab runs the formal experiment.
