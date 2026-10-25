# PoC 040: Composed hard-category pipeline — 512-token chunks + decomposition + N=2 pool + generator-free extractive selection at depth (OP-1/OP-2)

| | |
|---|---|
| Status | Concluded — host stage (300 hard-category items, full ladder B0/B1/C1/C2/C2p). |
| Verdict | **Reject the composition — the 512-token retrieval gain does not convert to answer quality; the levers are redundant at the answer step.** This is the answer-step re-validation PoC-037 explicitly asked for, and it closes the loop: moving to 512-token chunks lifts hard-category **recall@3 coverage to a lab-best 47.0** (B1 39.7 → C2 47.0), but **span-F1 stays flat at ~21** (B1 21.2 → C2 21.1, **H2 −0.1, H3 −1.0, H1 21.1 ≪ 30 — all FAIL**). Chunk-size *alone* (C1) even **hurts** span-F1 (−3.2 vs B1) — bigger chunks dilute sentence-level extraction with distractor sentences; decomposition only claws it back to the extractor baseline. The 030 N=2 pool adds nothing (C2p ≈ C2). The **only** real gain over the Qwen production baseline is the already-adopted generator-free extractor (C2 − B0 = **+3.6**, all from PoC-018/036). **Ship the PoC-036 extractor (N=10) on the existing 014 chunks; do not adopt 512-token chunks or the composed stack for the answer path.** H4 (generator-free, 3.9 GB) passes. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Lab-internal capstone composition, explicitly called for in **PoC-036's verdict** ("the composed stack — decomposition + N=2 pool (PoC-030) + extractive N=10 — is the natural end-to-end test"), now extended with the **PoC-037** chunk-size finding (W≈384 ≈ 512 tokens, +6.2 recall@3). Recombines five concluded PoCs: 016 (template decomposition), 030 (per-sub-query N=2 pool), 018 (generator-free extractive span selection), 036 (extractive depth N=10), 037 (fixed 512-token chunks). A parallel engine proposal — a two-stage per-hard-category deterministic-subquery retrieval pipeline — is being pursued separately as **PoC-039**. |
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

## Harness

`pipeline.py` reuses the committed retrieval vectors (014 page chunks `emb-page`, raw query `emb-queries`,
016 `emb-subqueries` + `decomp-templates.json`) and regenerates the **W=384** chunk index fresh via
EmbeddingGemma (`--embd-gemma-default`, `title: none | text:` prefix — identical to PoC-037, cached to
`results/raw/w384-index.jsonl`, 124 MB, gitignored). The extractor is **byte-identical** to PoC-018/036
(deterministic sentence splitter → max-cosine over the category sub-queries → best ≤3-sentence window),
so `B1` is a direct control for PoC-036 N=10. Sentence embeddings are computed live and cached across
arms. The `B0` arm calls Qwen (:8091) with PoC-017's exact prompt/sampling. Each arm writes
`results/raw/<arm>-answers.jsonl`; summaries in `results/pipeline.json` + `results/comparison.txt`.

## Results

MEASURED on the host (Mac16,8 M4 Pro; EmbeddingGemma via `--embd-gemma-default` + Qwen2.5-1.5B-Instruct
Q4_K_M for B0), **300 hard-category items** (100 each), ≤3-sentence window, depth N=10, single
deterministic pass. span-F1 is SQuAD token-overlap vs the gold span; contract-level bootstrap CI (10k,
seed 0). W=384 index = 6,556 chunks across 216 contracts.

**Hard-category span-F1 (the end-to-end answer metric) + recall@3 coverage:**

| Arm | Chunks | Query | Answer step | Exclusivity | Non-Compete | Change-of-Control | **hard-mean span-F1** | 95% CI | recall@3 cov. |
|---|---|---|---|---|---|---|---|---|---|
| `B0` production | 014 | raw, top-3 | Qwen generate | — | — | — | **17.5** | — | — |
| `B1` best extractor (control) | 014 | decomp, top-10 | extractive ≤3-sent | 11.9 | 22.8 | 28.9 | **21.2** | 18.4–24.3 | 39.7 |
| `C1` chunk-size only | **384** | raw, top-10 | extractive ≤3-sent | 8.9 | 17.7 | 27.5 | **18.0** | 15.3–20.9 | 44.0 |
| `C2` **full composition** | **384** | decomp, top-10 | extractive ≤3-sent | 11.8 | 20.1 | 31.5 | **21.1** | 18.3–24.1 | **47.0** |
| `C2p` C2 + 030 pool N=2 | 384 | decomp pool=2 | extractive ≤3-sent | 11.5 | 19.7 | 31.9 | **21.1** | 18.2–24.1 | 47.0 |

- **Control (B1 ≈ PoC-036 N=10):** B1 hard-mean **21.2** (Excl 11.9 / NonC 22.8 / CoC 28.9) reproduces
  PoC-036's 22.1 (Excl 13.1 / NonC 22.5 / CoC 30.6) within ~1 pt — the residual is EmbeddingGemma
  batch-to-batch nondeterminism in the live sentence embeddings (occasionally flips the best sentence).
  Same mechanism, same category profile → control validated. MEASURED.
- **H1 (C2 hard-mean span-F1 ≥ 30):** **FAIL** — 21.1. MEASURED.
- **H2 (512-token chunks add ≥ +3 through the pipeline, C2 − B1):** **FAIL** — **−0.1**. The chunk-size
  lever does **not** convert to answer quality. MEASURED.
- **H3 (composed > best single lever by ≥ +3):** **FAIL** — **−1.0** vs max(B1 21.2, PoC-036 22.1); the
  composition does not beat its best single component. MEASURED.
- **H4 (≤ 6 GB, generator-free):** **PASS** — host peak RSS **3.9 GB**, no generator in C1/C2/C2p.
  INFERRED (device figure pending). MEASURED (host).
- **The retrieval vs answer divergence (the headline):** recall@3 coverage *does* climb with the levers
  (B1 39.7 → C1 44.0 → C2 **47.0**, the lab's best hard-mean coverage, reproducing PoC-037's retrieval
  win) — but span-F1 is **flat/negative** over the same ladder. Chunk-size *alone* (C1) **hurts** span-F1
  (−3.2 vs B1) because a 512-token chunk contributes ~15–20 candidate sentences and the extra distractors
  out-vote the gold sentence; decomposition (C2) only recovers the extractor baseline. MEASURED.
- **030 N=2 pool (C2p):** identical span-F1 and recall@3 to C2 — no marginal contribution at the answer
  step. MEASURED.
- **Only real win over production:** C2 − B0 = **+3.6** span-F1, entirely from the generator-free
  extractor (PoC-018/036), not from chunk-size, decomposition depth, or pooling. MEASURED.

Per-item answers in `results/raw/{B0,B1,C1,C2,C2p}-answers.jsonl`; summary in `results/pipeline.json`.

## Verdict

**Reject the composition — but it is a high-value negative result that closes PoC-037's open question.**
PoC-037 lifted hard-category recall@3 by +6.2 with 512-token chunks and explicitly flagged that the
coverage metric is chunk-size-sensitive and must be *re-validated at the answer step*. PoC-040 is that
re-validation, run end-to-end on the adopted generator-free extractor, and the answer is unambiguous:
**the chunk-size retrieval gain does not convert.** Coverage rises to a lab-best 47.0 while span-F1 stays
pinned at ~21 (H2 −0.1), and chunk-size in isolation (C1) actually *degrades* answer quality (−3.2)
because larger chunks flood the sentence-level extractor with distractors. The composition does not beat
its best single component (H3 −1.0), so by the pre-registered decision rule — *"reject if the composition
does not beat the best single component"* — this is a **reject**.

The practical recommendation is therefore **simplicity**: ship the already-adopted **PoC-036 extractive
selector (≤3-sentence window, N=10) on the existing PoC-014 chunks**. It captures essentially all the
achievable hard-category span-F1 (~21–22) and is the sole source of the +3.6 over the Qwen production
baseline; 512-token chunks (037), decomposition depth, and the N=2 pool (030) add nothing on top of it at
the answer step — and 512-token chunks would cost ~4× the index memory for a measured answer-quality loss.

This hardens the series' recurring lesson (PoC-017, PoC-030's caveat) into a clean end-to-end
demonstration: **hard-category retrieval-recall gains convert weakly — here, not at all — to answer
quality.** The hard-category bottleneck is not retrieval coverage (now 47%); it is the *answer
granularity* — selecting the exact gold span out of many plausible sentences — which neither bigger
chunks nor wider pools address. Future effort should target span-boundary precision (e.g. a clause-span
classifier over the retrieved sentences), not further retrieval-coverage levers.

## Deviations

- **Pool vs depth (pre-registered N=2 pool).** The registration bundled "per-sub-query pool N=2 (030)"
  into the top-10 extractor, but pool=2 × 3 sub-queries ≤ 6 < 10, so the two cannot both hold literally.
  Resolution: the headline **C2 uses the PoC-036-adopted extractor config (per-sub-query pool = depth =
  10)**, and the 030 N=2 refinement is measured as a **separate arm `C2p`** (pool 2 per sub-query, union,
  depth ≤ 10). C2p ≈ C2 on every metric, so the choice is immaterial to the verdict.
- **B0 is raw-query production generate** (014 chunks, raw query, top-3, Qwen) — the true shipped stack —
  rather than PoC-018's decomposed-retrieval generate arm (which measured 15.7). Measured here at 17.5.
- **Read-only inputs when run from a worktree.** The gitignored committed vectors (007/014/016
  `results/raw`) live in the lab clone's working tree, not in a detached git worktree. `pipeline.py`
  defaults to the sibling `poc/` dir (normal clone) and honours `LAB_POC_ROOT` to point at the clone's
  `poc/` dir when run from a worktree (read-only).
- **W=384 index not committed** (124 MB, gitignored like all heavy vectors); regenerate via `pipeline.py`
  (it reproduces PoC-037's W=384 recall@3 as the C1 control).

## Limits

- **span-F1 proxy**, not a human answer-quality judgement; absolute span-F1 is low for long clause answers
  (50–70-word gold spans), same caveat as PoC-017/018/036 — interpret the Δ, not the absolute.
- **Live sentence-embedding nondeterminism** introduces ~±1 pt run-to-run noise (visible in the B1↔036
  control); the verdict rests on gaps far larger than that (H2 −0.1 is *within* noise → "no conversion",
  C1 −3.2 is well outside it).
- **Hard categories only, host stage.** Device RAM (H4) pending; fact categories unaffected (retrieval
  path for non-hard items unchanged), so H5 is a sanity check, not re-run.
- **Depth capped at N=10 and window ≤3**, inheriting PoC-036's adopted operating point.

## Reproduce

```bash
# EmbeddingGemma for chunk + sentence embeddings; Qwen only for the B0 generate baseline:
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &  # B0 only

cd poc/040-composed-hardcat-pipeline
python3 pipeline.py          # B1/C1/C2/C2p ladder (builds + caches the W=384 index on first run; needs :8090)
python3 pipeline.py --b0     # also run the Qwen production baseline (needs :8091)
# read-out: results/comparison.txt ; summary: results/pipeline.json ; per-item: results/raw/*-answers.jsonl
```

---

### Engine provenance (how this idea was generated)

- Lab-internal **capstone composition** (not a single engine inbox drop): the recombination of PoC-016 ×
  030 × 018 × 036 × 037 was called for explicitly in PoC-036's verdict. The ideation engine's parallel
  suggestion — a two-stage per-hard-category deterministic-subquery retrieval pipeline — is being pursued
  separately as **PoC-039**, and overlaps the retrieval half of this stack.
- Provenance: idea-evolution-engine (private) ground-truth ledger covers PoC-006..038; this PoC's verdict
  (**REJECT** — composition does not beat its best single component; the chunk-size retrieval gain does not
  convert to answer quality) will be exported back to the ledger to close the loop.
