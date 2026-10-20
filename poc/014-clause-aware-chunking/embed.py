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
import argparse, json, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
RAW = HERE / "results" / "raw"

DOC_PREFIX = "title: none | text: {t}"
QRY_PREFIX = "task: search result | query: {t}"


MAX_WORDS = 1200  # EmbeddingGemma context is 2048 tok; ~1200 words stays under one slot
                  # llama-server returns 500 (not silent truncation) on over-length input,
                  # so we truncate here to reproduce PoC 007's effective ctx-2048 behaviour.


def _post(url, inputs):
    body = json.dumps({"input": inputs}).encode()
    req = urllib.request.Request(url + "/v1/embeddings", data=body,
                                 headers={"Content-Type": "application/json"})
    return [d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]]


def embed_many(texts, label, url, batch):
    texts = [" ".join(t.split()[:MAX_WORDS]) for t in texts]  # bound every input
    vecs = []
    i = 0
    while i < len(texts):
        chunk = texts[i:i + batch]
        try:
            vecs.extend(_post(url, chunk))
            i += batch
        except (urllib.error.HTTPError, urllib.error.URLError):
            if len(chunk) == 1:
                # transient 500s under load — retry with backoff before giving up
                emb = None
                for attempt in range(5):
                    time.sleep(0.5 * 2 ** attempt)
                    try:
                        emb = _post(url, chunk); break
                    except Exception:
                        continue
                if emb is None:  # last resort: hard-truncate, then zero-vec
                    try:
                        emb = _post(url, [" ".join(chunk[0].split()[:400])])
                    except Exception:
                        print(f"  [{label}] WARN: row {i} unembeddable after retries, zero vector")
                        emb = [[0.0] * (len(vecs[-1]) if vecs else 768)]
                vecs.extend(emb)
                i += 1
            else:
                batch = max(1, len(chunk) // 2)  # sub-split and retry this slice
                continue
        if (i // max(batch, 1)) % 20 == 0 or i >= len(texts):
            print(f"  [{label}] {min(i, len(texts))}/{len(texts)}")
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
