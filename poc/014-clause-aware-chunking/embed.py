#!/usr/bin/env python3
"""PoC 014 — embed a chunk set (or the queries) with EmbeddingGemma via llama-server.

Same model + config + task prefixes as PoC 007/011 (mean pool, L2, ctx 2048). Start:

  llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
    -c 16384 --parallel 8 --host 127.0.0.1 --port 8090 --log-disable &

Usage:
  python3 embed.py --chunks results/raw/chunks-page.jsonl   --out results/raw/emb-page.jsonl
  python3 embed.py --chunks results/raw/chunks-clause.jsonl --out results/raw/emb-clause.jsonl
  python3 embed.py --queries --out results/raw/emb-queries.jsonl   # queries for contracts present in chunks-page
"""
from __future__ import annotations
import argparse, json, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
RAW = HERE / "results" / "raw"

DOC_PREFIX = "title: none | text: {t}"
QRY_PREFIX = "task: search result | query: {t}"


def embed_many(texts, label, url, batch):
    vecs = []
    for i in range(0, len(texts), batch):
        body = json.dumps({"input": texts[i:i + batch]}).encode()
        req = urllib.request.Request(url + "/v1/embeddings", data=body,
                                     headers={"Content-Type": "application/json"})
        data = json.load(urllib.request.urlopen(req, timeout=600))["data"]
        vecs.extend(d["embedding"] for d in data)
        if (i // batch) % 20 == 0 or i + batch >= len(texts):
            print(f"  [{label}] {min(i + batch, len(texts))}/{len(texts)}")
    return vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", help="chunks jsonl to embed (field 'chunk')")
    ap.add_argument("--queries", action="store_true", help="embed item questions instead")
    ap.add_argument("--out", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8090")
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    if args.queries:
        # restrict to contracts present in the page chunk set (scope-safe)
        present = {json.loads(l)["contract"] for l in open(RAW / "chunks-page.jsonl")}
        items = [json.loads(l) for l in open(P007 / "items.jsonl")]
        items = [it for it in items if it["contract"] in present]
        texts = [QRY_PREFIX.format(t=it["question"]) for it in items]
        keys = [it["qa_id"] for it in items]
    else:
        rows = [json.loads(l) for l in open(args.chunks)]
        texts = [DOC_PREFIX.format(t=r["chunk"]) for r in rows]
        keys = list(range(len(rows)))  # row index; scorer aligns by position

    vecs = embed_many(texts, Path(args.out).stem, args.url, args.batch)
    with open(args.out, "w") as f:
        for k, v in zip(keys, vecs):
            f.write(json.dumps({"key": k, "vec": v}) + "\n")
    print(f"wrote {len(vecs)} vectors -> {args.out}")


if __name__ == "__main__":
    main()
