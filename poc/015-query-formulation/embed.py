#!/usr/bin/env python3
"""PoC 015 — embed the per-category query transforms (gloss / keywords / sub-queries).

Reuses PoC 014 emb-page.jsonl (chunks) and emb-queries.jsonl (raw per-item queries) at
score time; here we only embed the authored transforms, once per category. Writes
results/raw/emb-queryvariants.jsonl keyed "<category>::gloss|keywords|sub<k>".

Server: llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
          -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
"""
from __future__ import annotations
import argparse, json, time, urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent / "results" / "raw"
QRY_PREFIX = "task: search result | query: {t}"


def _post(url, inputs):
    body = json.dumps({"input": inputs}).encode()
    req = urllib.request.Request(url + "/v1/embeddings", data=body,
                                 headers={"Content-Type": "application/json"})
    return [d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]]


def embed_many(texts, url, batch=8):
    vecs, i = [], 0
    while i < len(texts):
        chunk = texts[i:i + batch]
        try:
            vecs.extend(_post(url, chunk)); i += batch
        except (urllib.error.HTTPError, urllib.error.URLError):
            if len(chunk) == 1:
                emb = None
                for a in range(5):
                    time.sleep(0.5 * 2 ** a)
                    try: emb = _post(url, chunk); break
                    except Exception: continue
                vecs.extend(emb or [[0.0] * (len(vecs[-1]) if vecs else 768)]); i += 1
            else:
                batch = max(1, len(chunk) // 2)
    return vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8090")
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()
    variants = json.loads((RAW / "query-variants.json").read_text())
    texts, keys = [], []
    for cat, v in variants.items():
        texts.append(QRY_PREFIX.format(t=v["gloss"])); keys.append(f"{cat}::gloss")
        texts.append(QRY_PREFIX.format(t=v["keywords"])); keys.append(f"{cat}::keywords")
        for k, s in enumerate(v["subqueries"]):
            texts.append(QRY_PREFIX.format(t=s)); keys.append(f"{cat}::sub{k}")
    vecs = embed_many(texts, args.url, args.batch)
    with open(RAW / "emb-queryvariants.jsonl", "w") as f:
        for k, vec in zip(keys, vecs):
            f.write(json.dumps({"key": k, "vec": vec}) + "\n")
    print(f"wrote {len(vecs)} query-variant vectors -> emb-queryvariants.jsonl")


if __name__ == "__main__":
    main()
