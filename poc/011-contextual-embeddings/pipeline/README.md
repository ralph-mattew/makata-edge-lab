# PoC 011 pipeline — generated contextual retrieval

Implements the registered PoC 011 method: generate a per-chunk context with a
language model, prepend it before embedding (and BM25), then measure recall@3 vs
the plain baseline and the naive-template ablation.

Stages (each a script; artifacts flow via JSONL in `../results/raw/`):

| # | Script | Does | Status |
|---|--------|------|--------|
| 0 | (007's `prepare.py`) | build `contracts.jsonl`, `chunks.jsonl`, `items.jsonl` from CUAD | reuse PoC 007 |
| 1 | `01-generate-contexts.py` | LLM-generate per-chunk context (on-device Qwen + host Gemma), prompt-cached per document | **verified** (generation runs; see results/generated-context-spotcheck.md) |
| 2 | `02-embed.py` | embed queries + chunk variants (standard / naive / generated) with EmbeddingGemma | **verified** (`llama-embedding --embd-gemma-default`, mean pool, L2, ctx 2048 — matches PoC 007) |
| 3 | `03-retrieve-score.py` | hybrid 0.9 semantic + 0.1 BM25 (PoC 013 weight), top-3, recall vs gold spans, bootstrap CIs | **needs validation against PoC 007's Swift scorer before publishing** |

## Conditions (per the registration)

`standard` (plain chunk) · `naive-prepend` (static `Document:…Section:…Chunk:…`
ablation) · `generated-device` (Qwen2.5-1.5B context) · `generated-host` (Gemma-4-E2B context).

## Prerequisites (local; nothing model-weight is committed)

- llama.cpp (`llama-embedding`, `llama-server`) on PATH.
- PoC 006/007 run once so `../../007-embedding-retrieval-recall/results/raw/{contracts,chunks,items}.jsonl` exist.
- Qwen2.5-1.5B Q4 + Gemma-4-E2B Q4 GGUFs (as used by PoC 006).
- EmbeddingGemma: fetched automatically by `llama-embedding --embd-gemma-default`.

## Run

```bash
cd poc/011-contextual-embeddings/pipeline
./run.sh                 # all stages on a sample; see flags inside
# or stage by stage:
python3 01-generate-contexts.py --limit 200      # generate contexts (cost: 1 short gen/chunk)
python3 02-embed.py                               # embed queries + chunk variants
python3 03-retrieve-score.py                      # recall@3 per condition + CIs
```

## Honest status

Stage 1 (generation) and Stage 2 (EmbeddingGemma embedding) are verified to run
with the exact tools/config above. Stage 3's recall scorer **reimplements** PoC
007's "top-3 cover ≥50% of the gold span" definition in Python and must be
checked against 007's Swift `Scores` harness on the `standard` condition
(it should reproduce 61.4% at the 0.9/0.1 weight) before any verdict is drawn.
Until then, treat Stage 3 numbers as provisional. No full-corpus run is committed
here yet — this is the runnable scaffold.
