#!/usr/bin/env python3
"""PoC 037 — fixed chunk-size sweep for retrieval (OP-1).

Current PoC-014 "page" chunks are small/variable (median ~25 words). This re-chunks every CUAD
contract into fixed W-word windows (no overlap) at W ~= {96, 192, 384} words (≈128/256/512 tokens),
re-embeds with EmbeddingGemma, and measures hybrid 0.9/0.1 recall@3 vs the 61.4% baseline — overall
and per hard category. Query vectors are the committed ones (same question text + model); only the
chunk index changes.

Server: EmbeddingGemma :8090 (embeds the re-chunked corpus). Run: python3 chunk-size.py
"""
from __future__ import annotations
import argparse, json, math, re, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
WORD_SIZES = [96, 192, 384]   # ~128 / 256 / 512 tokens (no overlap)
DOC_PREFIX = "title: none | text: {t}"
EG_BASELINE = 61.4


def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())


def bm25(qt, docs, k1=1.5, b=0.75):
    N = len(docs); avgdl = sum(len(d) for d in docs) / max(N, 1)
    df = Counter(t for d in docs for t in set(d))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    out = []
    for d in docs:
        tf = Counter(d)
        out.append(sum(idf.get(t, 0) * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl)) for t in qt))
    return out


def norm01(xs):
    lo, hi = min(xs, default=0), max(xs, default=0)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def covers(span, gold, frac=0.5):
    if not span or not gold:
        return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def embed(url, texts, batch=16):
    out, i = [], 0
    while i < len(texts):
        chunk = [DOC_PREFIX.format(t=t) for t in texts[i:i + batch]]
        body = json.dumps({"input": chunk}).encode()
        req = urllib.request.Request(url + "/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
        try:
            out.extend(d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]); i += batch
        except Exception:
            if batch == 1: out.append([0.0] * (len(out[-1]) if out else 768)); i += 1
            else: batch = max(1, batch // 2)
    return out


def chunk_contract(words, W):
    """Fixed W-word windows, no overlap. Returns [(text, (start,end))]."""
    out = []
    for s in range(0, len(words), W):
        seg = words[s:s + W]
        if seg:
            out.append((" ".join(seg), (s, s + len(seg) - 1)))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--topk", type=int, default=3); args = ap.parse_args()
    contracts = {c["contract"]: (" ".join(c.get("pages", []) or [])).split() for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words") and json.loads(l)["contract"] in contracts
             and json.loads(l)["qa_id"] in qvec]
    print(f"items: {len(items)}  contracts: {len(contracts)}  sizes(words): {WORD_SIZES}")

    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for W in WORD_SIZES:
        # build + embed the chunk index for this size
        chunks_by_c = {}; texts = []; index = []  # index: (contract, local_i)
        for c, words in contracts.items():
            ch = chunk_contract(words, W)
            chunks_by_c[c] = ch
            for li, (t, _) in enumerate(ch):
                texts.append(t); index.append((c, li))
        print(f"  W={W}: {len(texts)} chunks, embedding ...")
        vecs = embed(args.emb_url, texts)
        cvec = {};
        for (c, li), v in zip(index, vecs):
            cvec.setdefault(c, {})[li] = v
        # evaluate recall@3
        per_cat = defaultdict(list); per_all = []
        for it in items:
            c = it["contract"]; ch = chunks_by_c[c]; cv = cvec[c]
            q = qvec[it["qa_id"]]; qt = terms(it["question"])
            sem = [cosine(q, cv[li]) for li in range(len(ch))]
            bm = norm01(bm25(qt, [terms(ch[li][0]) for li in range(len(ch))]))
            h = [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]
            top = sorted(range(len(ch)), key=lambda j: h[j], reverse=True)[:args.topk]
            gold = tuple(it["gold_words"])
            hit = any(covers(ch[j][1], gold) for j in top)
            per_cat[it["category"]].append(hit); per_all.append(hit)
        overall = 100 * sum(per_all) / len(per_all)
        cats = {c: 100 * sum(per_cat[c]) / len(per_cat[c]) for c in HARD}
        hm = sum(cats.values()) / 3
        results[f"W{W}"] = {"n_chunks": len(texts), "overall": overall, "hard_mean": hm, "per_category": cats}
        print(f"    W={W}: overall {overall:.1f}  hard-mean {hm:.1f}  Excl {cats['Exclusivity']:.0f}/NonC {cats['Non-Compete']:.0f}/CoC {cats['Change Of Control']:.0f}")

    (OUT / "chunk-size.json").write_text(json.dumps({"baseline_recall": EG_BASELINE, **results}, indent=2))
    best = max(WORD_SIZES, key=lambda W: results[f"W{W}"]["overall"])
    bo = results[f"W{best}"]["overall"]
    print(f"\nbaseline (PoC-007 page chunks): {EG_BASELINE:.1f}")
    for W in WORD_SIZES:
        print(f"  W={W:3} overall {results[f'W{W}']['overall']:.1f} (Δ {results[f'W{W}']['overall']-EG_BASELINE:+.1f})")
    print(f"best W={best}: overall {bo:.1f} (Δ {bo-EG_BASELINE:+.1f})  [adopt >=+3; reject if <+1 at all sizes]")


if __name__ == "__main__":
    main()
