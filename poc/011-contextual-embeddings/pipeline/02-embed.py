#!/usr/bin/env python3
"""Stage 2 — embed queries and chunk variants with EmbeddingGemma.

Uses `llama-embedding --embd-gemma-default` (auto-downloads the model) with the
exact config PoC 007 used: mean pooling, L2 normalization, 2048 context. Applies
EmbeddingGemma's task prefixes (documents vs query) as the model card and PoC 007
do. Produces per-text vectors for each retrieval condition.

Verified: the embedding invocation runs and returns an L2-normalized vector.
"""
from __future__ import annotations
import argparse, json, re, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent.parent / "007-embedding-retrieval-recall" / "results" / "raw"
RAW = HERE.parent / "results" / "raw"

# EmbeddingGemma task prefixes (model card; as in PoC 007).
DOC_PREFIX = "title: none | text: {t}"
QRY_PREFIX = "task: search result | query: {t}"


def embed(text: str) -> list[float]:
    """One EmbeddingGemma vector via llama-embedding (mean pool, L2-norm, ctx 2048)."""
    out = subprocess.run(
        ["llama-embedding", "--embd-gemma-default", "--pooling", "mean",
         "--embd-normalize", "2", "-c", "2048", "--embd-output-format", "array",
         "-p", text],
        capture_output=True, text=True, check=True).stdout
    nums = re.findall(r"-?\d+\.\d+(?:e-?\d+)?", out.split("[[")[-1])
    return [float(x) for x in nums]


def embed_many(texts, label):
    vecs = []
    for i, t in enumerate(texts, 1):
        vecs.append(embed(t))
        if i % 25 == 0:
            print(f"  [{label}] {i}/{len(texts)}")
    return vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=["standard", "naive", "ctx_qwen", "ctx_gemma", "queries"],
                    required=True, help="which text set to embed")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    if args.condition == "queries":
        items = [json.loads(l) for l in open(P007 / "items.jsonl")]
        texts = [QRY_PREFIX.format(t=it["question"]) for it in items]
        keys = [it["qa_id"] for it in items]
    else:
        rows = [json.loads(l) for l in open(RAW / "contextual-chunks.jsonl")]
        field = {"standard": "chunk", "naive": "naive", "ctx_qwen": "ctx_qwen", "ctx_gemma": "ctx_gemma"}[args.condition]
        texts = [DOC_PREFIX.format(t=(r.get(field) or r["chunk"])) for r in rows]
        keys = [f'{r["contract"]}#p{r["page"]}#{i}' for i, r in enumerate(rows)]

    vecs = embed_many(texts, args.condition)
    out = RAW / f"emb-{args.condition}.jsonl"
    with open(out, "w") as f:
        for k, v in zip(keys, vecs):
            f.write(json.dumps({"key": k, "vec": v}) + "\n")
    print(f"wrote {len(vecs)} vectors -> {out}")


if __name__ == "__main__":
    main()
