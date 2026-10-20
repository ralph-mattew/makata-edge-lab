#!/usr/bin/env python3
"""PoC 012 host stage — cross-encoder reranking over hybrid retrieval.

Pipeline: hybrid (0.9 semantic + 0.1 BM25, PoC 013 weight) retrieves top-10
candidates per query; a cross-encoder rescores each (query, chunk) pair; take the
reranked top-3; measure recall@3 vs the hybrid-top-3 baseline, with a
contract-level bootstrap CI and host reranking latency.

Reuses PoC 007/011 retrieval artifacts (no re-embedding):
  - 007 items.jsonl, contracts.jsonl
  - 011 pipeline emb-queries.jsonl, emb-standard.jsonl, contextual-chunks.jsonl

Reranker via sentence-transformers CrossEncoder. ms-marco-TinyBERT / BGE-reranker
load directly; mxbai-rerank may need its own loader (see README). Download happens
on first use.

STATUS: host-stage scaffold — not yet run (would compete with the live PoC 011
generation; also the on-iPhone latency hypothesis H4 needs a device). The recall
scorer shares PoC 011's provisional definition — validate `baseline` ~61.4% first.
"""
from __future__ import annotations
import argparse, json, math, random, re, time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P011 = HERE.parent.parent / "011-contextual-embeddings" / "results" / "raw"


def cosine(a, b):  # vectors are L2-normalized
    return sum(x * y for x, y in zip(a, b))


def terms(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def bm25(query_terms, docs_terms, k1=1.5, b=0.75):
    N = len(docs_terms) or 1
    avgdl = sum(len(d) for d in docs_terms) / N
    df = Counter(t for d in docs_terms for t in set(d))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    out = []
    for d in docs_terms:
        tf = Counter(d)
        out.append(sum(idf.get(t, 0) * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl))
                       for t in query_terms))
    return out


def norm01(xs):
    lo, hi = min(xs, default=0), max(xs, default=0)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def contract_words(c):
    pages = c.get("pages") or []
    return (" ".join(pages) if isinstance(pages, list) else c.get("text", "")).split()


def chunk_span(words, own):
    ow = own.split()
    if not ow:
        return None
    for i in range(len(words) - len(ow) + 1):
        if words[i] == ow[0] and words[i:i + len(ow)] == ow:
            return (i, i + len(ow) - 1)
    return None


def covers(span, gold, frac=0.5):
    if not span or not gold:
        return False
    s0, s1 = span; g0, g1 = gold
    inter = max(0, min(s1, g1) - max(s0, g0) + 1)
    return inter >= frac * (g1 - g0 + 1)


def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed)
    groups = list(per_contract.values())
    boot = []
    for _ in range(n):
        samp = [random.choice(groups) for _ in groups]
        xs = [h for g in samp for h in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort()
    return boot[int(0.025 * n)], boot[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cross-encoder/ms-marco-MiniLM-L-6-v2",
                    help="CrossEncoder (e.g. cross-encoder/ms-marco-TinyBERT-L-2-v2, BAAI/bge-reranker-base)")
    ap.add_argument("--retrieve-k", type=int, default=10)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--semantic-weight", type=float, default=0.9)
    ap.add_argument("--rerank", action="store_true", help="apply the cross-encoder (else baseline hybrid top-3)")
    args = ap.parse_args()

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P011 / "emb-queries.jsonl"))}
    rows = [json.loads(l) for l in open(P011 / "contextual-chunks.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P011 / "emb-standard.jsonl")]
    by_contract = {}
    for i, r in enumerate(rows):
        by_contract.setdefault(r["contract"], []).append(i)

    reranker = None
    if args.rerank:
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder(args.model)

    per_contract, latencies = {}, []
    sw = args.semantic_weight
    for it in items:
        idxs = by_contract.get(it["contract"], [])
        if not idxs or it["qa_id"] not in qvec:
            continue
        q, qt = qvec[it["qa_id"]], terms(it["question"])
        dterms = [terms(rows[i]["chunk"]) for i in idxs]
        sem = [cosine(q, cvec[i]) for i in idxs]
        bm = norm01(bm25(qt, dterms))
        hybrid = [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]
        cand = sorted(range(len(idxs)), key=lambda j: hybrid[j], reverse=True)[:args.retrieve_k]
        if reranker:
            t0 = time.time()
            scores = reranker.predict([(it["question"], rows[idxs[j]]["chunk"]) for j in cand])
            latencies.append((time.time() - t0) * 1000)
            cand = [c for _, c in sorted(zip(scores, cand), key=lambda t: t[0], reverse=True)]
        top = cand[:args.topk]
        words = contract_words(contracts.get(it["contract"], {}))
        gold = tuple(it["gold_words"]) if it.get("gold_words") else None
        hit = any(covers(chunk_span(words, rows[idxs[j]]["chunk"]), gold) for j in top)
        per_contract.setdefault(it["contract"], []).append(1 if hit else 0)

    flat = [h for g in per_contract.values() for h in g]
    recall = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap(per_contract)
    label = f"rerank:{args.model}" if reranker else "baseline hybrid top-3"
    print(f"[{label}] recall@{args.topk} = {recall:.1f}% (95% CI {lo:.1f}-{hi:.1f}) over {len(flat)} items")
    if latencies:
        latencies.sort()
        print(f"  rerank latency/query (host): median {latencies[len(latencies)//2]:.0f}ms "
              f"p95 {latencies[int(0.95*len(latencies))]:.0f}ms over {len(latencies)} queries")
    print("NOTE: provisional scorer (shared with PoC 011) — validate baseline ~61.4% before trusting the delta.")


if __name__ == "__main__":
    main()
