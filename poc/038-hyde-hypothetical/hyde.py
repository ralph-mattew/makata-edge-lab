#!/usr/bin/env python3
"""PoC 038 — HyDE (hypothetical document embeddings) for retrieval (OP-1/OP-2).

For each query, Qwen2.5-1.5B generates a hypothetical contract clause that would answer it; that
pseudo-document is embedded (doc-side) and used as the retrieval vector instead of the raw question
embedding. Measured on the SAME PoC-014 index as the 61.4% baseline (isolates the HyDE variable).
recall@3 overall + per hard category vs the raw-question baseline.

Servers: Qwen :8091 (generate hypo doc), EmbeddingGemma :8090 (embed hypo doc). Run: python3 hyde.py
"""
from __future__ import annotations
import argparse, json, math, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
DOC_PREFIX = "title: none | text: {t}"
EG_BASELINE = 61.4
HYDE_PROMPT = ("Write a single short contract clause (2-4 sentences) that would directly answer the "
               "following question. Output only the clause text.\n\nQUESTION: {q}\nCLAUSE:")


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


def qwen(url, q, n=140):
    body = json.dumps({"messages": [{"role": "user", "content": HYDE_PROMPT.format(q=q)}],
                       "n_predict": n, "temperature": 0.0, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception:
            time.sleep(1.0 * (a + 1))
    return ""


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3); ap.add_argument("--limit", type=int, default=0); args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qv_raw = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]
    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words") and json.loads(l)["contract"] in by_contract
             and json.loads(l)["qa_id"] in qv_raw]
    if args.limit:
        items = items[:args.limit]
    print(f"items: {len(items)}  generating HyDE pseudo-docs + embedding ...")

    hypo = [qwen(args.qwen_url, it["question"]) for it in items]
    hvec = embed(args.emb_url, [h or it["question"] for h, it in zip(hypo, items)])

    def recall(mode):
        per_cat, allh = defaultdict(list), []
        for it, hv in zip(items, hvec):
            idxs = by_contract[it["contract"]]; gold = tuple(it["gold_words"]); qt = terms(it["question"])
            qv = qv_raw[it["qa_id"]] if mode == "raw" else hv
            sem = norm01([cosine(qv, cvec[i]) for i in idxs])
            bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
            h = [0.9 * s + 0.1 * b for s, b in zip(sem, bm)]
            top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
            hit = any(covers(spans[idxs[j]], gold) for j in top)
            per_cat[it["category"]].append(hit); allh.append(hit)
        overall = 100 * sum(allh) / len(allh)
        cats = {c: 100 * sum(per_cat[c]) / len(per_cat[c]) for c in HARD if per_cat[c]}
        return overall, cats

    raw_o, raw_c = recall("raw"); hy_o, hy_c = recall("hyde")
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"baseline_recall": EG_BASELINE, "raw_overall": raw_o, "hyde_overall": hy_o,
           "delta": hy_o - raw_o, "raw_per_category": raw_c, "hyde_per_category": hy_c}
    (OUT / "hyde.json").write_text(json.dumps(res, indent=2))
    print(f"\n{'arm':8} {'overall':>8}  Excl / NonC / CoC")
    print(f"{'raw':8} {raw_o:7.1f}%  {raw_c.get('Exclusivity',0):.0f}/{raw_c.get('Non-Compete',0):.0f}/{raw_c.get('Change Of Control',0):.0f}")
    print(f"{'HyDE':8} {hy_o:7.1f}%  {hy_c.get('Exclusivity',0):.0f}/{hy_c.get('Non-Compete',0):.0f}/{hy_c.get('Change Of Control',0):.0f}")
    print(f"\nHyDE overall {hy_o:.1f} vs raw {raw_o:.1f} (Δ {hy_o-raw_o:+.1f})  [adopt >=64.4; reject <62.4]")


if __name__ == "__main__":
    main()
