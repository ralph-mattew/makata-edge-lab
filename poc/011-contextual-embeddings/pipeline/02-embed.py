#!/usr/bin/env python3
"""Stage 2 — embed queries and chunk variants with EmbeddingGemma.

Batches through a running `llama-server --embedding --embd-gemma-default` with the
exact config PoC 007 used (mean pooling, L2 normalization, 2048 context) and
EmbeddingGemma's task prefixes (documents vs query). One model load for the whole
corpus — not one subprocess per text.

  llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
    -c 2048 --host 127.0.0.1 --port 8090 --log-disable &

Verified: `llama-embedding --embd-gemma-default` returns L2-normalized vectors;
this uses the same model via the server's /v1/embeddings batch endpoint.
"""
from __future__ import annotations
import argparse, json, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent.parent / "007-embedding-retrieval-recall" / "results" / "raw"
RAW = HERE.parent / "results" / "raw"

# EmbeddingGemma task prefixes (model card; as in PoC 007).
DOC_PREFIX = "title: none | text: {t}"
QRY_PREFIX = "task: search result | query: {t}"


def embed_many(texts, label, url, batch=64):
    vecs = []
    for i in range(0, len(texts), batch):
        body = json.dumps({"input": texts[i:i + batch]}).encode()
        req = urllib.request.Request(url + "/v1/embeddings", data=body,
                                     headers={"Content-Type": "application/json"})
        data = json.load(urllib.request.urlopen(req, timeout=300))["data"]
        vecs.extend(d["embedding"] for d in data)
        print(f"  [{label}] {min(i + batch, len(texts))}/{len(texts)}")
    return vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=["standard", "naive", "ctx_qwen", "ctx_gemma", "queries"],
                    required=True, help="which text set to embed")
    ap.add_argument("--url", default="http://127.0.0.1:8090", help="llama-server embedding endpoint")
    ap.add_argument("--batch", type=int, default=8,
                    help="texts per request (keep batch*chunk_tokens <= server -b)")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    if args.condition == "queries":
        # Only embed queries whose contract is present in the (possibly scoped)
        # chunk set, so a subset run doesn't embed all 1,325 queries.
        contracts = {json.loads(l)["contract"] for l in open(RAW / "contextual-chunks.jsonl")}
        items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["contract"] in contracts]
        texts = [QRY_PREFIX.format(t=it["question"]) for it in items]
        keys = [it["qa_id"] for it in items]
    else:
        rows = [json.loads(l) for l in open(RAW / "contextual-chunks.jsonl")]
        field = {"standard": "chunk", "naive": "naive", "ctx_qwen": "ctx_qwen", "ctx_gemma": "ctx_gemma"}[args.condition]
        texts = [DOC_PREFIX.format(t=(r.get(field) or r["chunk"])) for r in rows]
        keys = [f'{r["contract"]}#p{r["page"]}#{i}' for i, r in enumerate(rows)]

    vecs = embed_many(texts, args.condition, args.url, batch=args.batch)
    out = RAW / f"emb-{args.condition}.jsonl"
    with open(out, "w") as f:
        for k, v in zip(keys, vecs):
            f.write(json.dumps({"key": k, "vec": v}) + "\n")
    print(f"wrote {len(vecs)} vectors -> {out}")


if __name__ == "__main__":
    main()
