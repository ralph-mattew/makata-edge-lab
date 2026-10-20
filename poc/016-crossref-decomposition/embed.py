#!/usr/bin/env python3
"""PoC 016 — embed the xref chunks and the decomposition sub-queries.

Reuses PoC 014's EmbeddingGemma vectors to avoid re-embedding 79k chunks:
  --xref        : align to PoC 014 emb-page.jsonl (same row order as chunks-page); embed
                  ONLY the rows marked changed in chunks-xref.jsonl, copy the page vector
                  for the rest. Writes emb-xref.jsonl aligned to chunks-xref rows.
  --subqueries  : embed each hard-category sub-query (from decomp-templates.json) once per
                  item in that category. Writes emb-subqueries.jsonl keyed by "<qa_id>#<k>".

Server (same config as PoC 007/014):
  llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
    -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
"""
from __future__ import annotations
import argparse, json, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
RAW = HERE / "results" / "raw"

DOC_PREFIX = "title: none | text: {t}"
QRY_PREFIX = "task: search result | query: {t}"
MAX_WORDS = 1200


def _post(url, inputs):
    body = json.dumps({"input": inputs}).encode()
    req = urllib.request.Request(url + "/v1/embeddings", data=body,
                                 headers={"Content-Type": "application/json"})
    return [d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]]


def embed_many(texts, label, url, batch=8):
    texts = [" ".join(t.split()[:MAX_WORDS]) for t in texts]
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
                    try:
                        emb = _post(url, chunk); break
                    except Exception:
                        continue
                if emb is None:
                    try:
                        emb = _post(url, [" ".join(chunk[0].split()[:400])])
                    except Exception:
                        emb = [[0.0] * (len(vecs[-1]) if vecs else 768)]
                vecs.extend(emb); i += 1
            else:
                batch = max(1, len(chunk) // 2); continue
        if (i // max(batch, 1)) % 20 == 0 or i >= len(texts):
            print(f"  [{label}] {min(i, len(texts))}/{len(texts)}")
    return vecs


def do_xref(url, batch):
    # Overlay approach: embed ONLY the changed rows and write them keyed by row index.
    # The scorer reads PoC 014 emb-page.jsonl as the base and overlays these — so we
    # never hold the 1.3 GB page-vector file in memory here.
    changed = []
    for i, l in enumerate(open(RAW / "chunks-xref.jsonl")):
        r = json.loads(l)
        if r.get("changed"):
            changed.append((i, r["chunk"]))
    print(f"  embedding {len(changed)} changed rows (scorer overlays onto emb-page)")
    vecs = embed_many([DOC_PREFIX.format(t=t) for _, t in changed], "xref", url, batch) if changed else []
    with open(RAW / "emb-xref-changed.jsonl", "w") as f:
        for (i, _), v in zip(changed, vecs):
            f.write(json.dumps({"key": i, "vec": v}) + "\n")
    print(f"wrote {len(vecs)} changed vectors -> emb-xref-changed.jsonl")


def do_subqueries(url, batch):
    templates = json.loads((RAW / "decomp-templates.json").read_text())
    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    texts, keys = [], []
    for it in items:
        subs = templates.get(it["category"])
        if not subs:
            continue
        for k, s in enumerate(subs):
            texts.append(QRY_PREFIX.format(t=s)); keys.append(f'{it["qa_id"]}#{k}')
    vecs = embed_many(texts, "subqueries", url, batch)
    with open(RAW / "emb-subqueries.jsonl", "w") as f:
        for k, v in zip(keys, vecs):
            f.write(json.dumps({"key": k, "vec": v}) + "\n")
    print(f"wrote {len(vecs)} sub-query vectors -> emb-subqueries.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xref", action="store_true")
    ap.add_argument("--subqueries", action="store_true")
    ap.add_argument("--url", default="http://127.0.0.1:8090")
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    if args.xref:
        do_xref(args.url, args.batch)
    if args.subqueries:
        do_subqueries(args.url, args.batch)


if __name__ == "__main__":
    main()
