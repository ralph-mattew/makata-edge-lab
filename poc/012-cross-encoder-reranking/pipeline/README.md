# PoC 012 pipeline — cross-encoder reranking (host stage)

Host-stage harness for the registered PoC 012: hybrid retrieval → top-10 → cross-encoder
rerank → top-3, vs the hybrid-top-3 baseline.

| Script | Does | Status |
|--------|------|--------|
| `rerank-score.py` | hybrid top-10 (reuses 007/011 embeddings + BM25) → CrossEncoder rerank → recall@3 + CI + host latency | **scaffold — not yet run** |

## Run (later)

Depends on PoC 011's retrieval artifacts (`emb-queries.jsonl`, `emb-standard.jsonl`,
`contextual-chunks.jsonl`) and 007's `items.jsonl`/`contracts.jsonl`.

```bash
cd poc/012-cross-encoder-reranking/pipeline
python3 rerank-score.py                              # baseline hybrid top-3 (validate ~61.4% first)
python3 rerank-score.py --rerank --model cross-encoder/ms-marco-TinyBERT-L-2-v2   # fast/tiny
python3 rerank-score.py --rerank --model BAAI/bge-reranker-base                   # accuracy
# mxbai-rerank-base-v1: see note below (custom loader)
```

## Reranker models (per the registration)

- **ms-marco-TinyBERT-L-2** (4M) — loads directly as a `CrossEncoder`; the fast/cheap option.
- **BGE-reranker-base** (278M) — loads directly as a `CrossEncoder`; the accuracy option.
- **mxbai-rerank-base-v1** (184M) — the registration's primary; may need the
  `mxbai-rerank` package or a transformers loader rather than plain `CrossEncoder`.
  Wire it in before the primary run.

## Honest status / scope

- **Not run yet** — deliberately, to avoid competing for GPU with the live PoC 011
  generation. Code is ready.
- **H4 (on-iPhone latency) is out of scope here** — host stage only; the iPhone
  measurement needs a device + ONNX/Core ML export (see the registration's
  Implementation Notes).
- The recall scorer is the **same provisional one as PoC 011** — validate the
  `baseline` reproduces ~61.4% before trusting any rerank delta.
- Merit note: reranking is a known RAG technique; its value here is the measured
  on-device latency/memory tradeoff (H4/H5), which this host scaffold does **not**
  answer. Weigh against the chunking/question-formulation bottleneck (PoC 009/013
  found the hard categories are retrieval-scoring-invariant) before investing the
  device-stage effort.
