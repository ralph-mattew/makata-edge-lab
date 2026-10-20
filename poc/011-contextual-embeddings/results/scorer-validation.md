# PoC 011 pipeline — scoped scorer validation (pre-run)

Before trusting any contextual-vs-standard delta, the Stage 3 recall scorer (a
Python reimplementation of PoC 007's "top-3 cover ≥50% of the gold span") must
reproduce PoC 007's known baseline. This is that check, on a scoped subset.

## Setup

- **Subset:** first 15 CUAD contracts → 1,996 chunks, **36 answerable items**
  (small, non-stratified — a sanity check, not a full reproduction).
- **Embeddings:** EmbeddingGemma via `llama-server --embedding --embd-gemma-default
  --pooling mean --embd-normalize 2 -c 16384 --parallel 8` (per-input context
  16384/8 = 2048, matching PoC 007). Batched through `/v1/embeddings`.
- **Retrieval:** hybrid, top-3; recall@3 = PoC 007's definition.

## Result (OBSERVED)

| Semantic weight | `standard` recall@3 (36 items) | 95% CI |
|---|---|---|
| 0.9 (PoC 013) | 69.4% | 55.6–81.2 |
| 1.0 (pure semantic) | 66.7% | 50.0–81.4 |
| 0.7 (PoC 007's weight) | 61.1% | 41.9–75.0 |

**PoC 007's 61.4% baseline sits well inside the CI** (and is ~bang-on at the 0.7
weight PoC 007 used). The scorer, embedding, and retrieval therefore behave
consistently with the published baseline — the pipeline is de-risked enough to
run the contextual conditions.

## Caveats

- 36 items from the first 15 contracts (not category-stratified) → wide CI and a
  point estimate a little above 61.4%. This is a consistency check, **not** a
  full reproduction; the full run scores all 1,325 items.
- The scorer still approximates 007's Swift `Scores` definition (chunk `own`
  text located in the contract word stream). It lands sensibly here; a full run
  should still compare `standard` against 007's exact 61.4% before publishing a
  verdict on the contextual conditions.

## Gotcha recorded (so the full run doesn't re-hit it)

`llama-server` divides `n_ctx` across `--parallel` slots. A bare `-c 2048` with
the default parallelism gives only **256 tokens per input** and 400s on any chunk
longer than that ("exceed_context_size_error"). Use `-c 16384 --parallel 8`
(or `--parallel 1 -c 2048`). Captured in `run.sh`.
