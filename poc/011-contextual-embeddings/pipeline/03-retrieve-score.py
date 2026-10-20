#!/usr/bin/env python3
"""Stage 3 — hybrid retrieval + recall@3 per condition.

For each query, score its contract's chunks with hybrid = 0.9*cosine(query,chunk)
+ 0.1*BM25 (the 0.9/0.1 weight adopted in PoC 013), take top-3, and compute recall
as "top-3 cover >=50% of the gold answer span" (PoC 007's definition). Reports
recall per condition with a contract-level bootstrap CI.

PROVISIONAL: this reimplements PoC 007's Swift recall scorer in Python. Validate it
on the `standard` condition first — it should reproduce ~61.4% at the 0.9/0.1
weight. Do not draw a verdict until it does.
"""
from __future__ import annotations
import argparse, json, math, random, re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent.parent / "007-embedding-retrieval-recall" / "results" / "raw"
RAW = HERE.parent / "results" / "raw"


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))  # vectors are L2-normalized already


def bm25_scores(query_terms, docs_terms, k1=1.5, b=0.75):
    N = len(docs_terms)
    avgdl = sum(len(d) for d in docs_terms) / max(N, 1)
    df = Counter(t for d in docs_terms for t in set(d))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    out = []
    for d in docs_terms:
        tf = Counter(d)
        s = sum(idf.get(t, 0) * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl))
                for t in query_terms)
        out.append(s)
    return out


def norm01(xs):
    lo, hi = min(xs, default=0), max(xs, default=0)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def terms(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def contract_words(contract):
    pages = contract.get("pages") or []
    return (" ".join(pages) if isinstance(pages, list) else contract.get("text", "")).split()


def chunk_span(words, own):
    """Approximate word [start,end] of a chunk by locating its 'own' text in the
    contract word stream. Returns None if not found."""
    ow = own.split()
    if not ow:
        return None
    first = ow[0]
    for i in range(len(words) - len(ow) + 1):
        if words[i] == first and words[i:i + len(ow)] == ow:
            return (i, i + len(ow) - 1)
    return None


def covers(span, gold, frac=0.5):
    if not span or not gold:
        return False
    g0, g1 = gold
    s0, s1 = span
    inter = max(0, min(s1, g1) - max(s0, g0) + 1)
    return inter >= frac * (g1 - g0 + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=["standard", "naive", "ctx_qwen", "ctx_gemma"], required=True)
    ap.add_argument("--semantic-weight", type=float, default=0.9)  # PoC 013
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args()

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(RAW / "emb-queries.jsonl"))}
    cvec = [json.loads(l) for l in open(RAW / f"emb-{args.condition}.jsonl")]
    chunk_rows = [json.loads(l) for l in open(RAW / "contextual-chunks.jsonl")]
    # group chunk indices by contract
    by_contract = {}
    for i, r in enumerate(chunk_rows):
        by_contract.setdefault(r["contract"], []).append(i)

    per_contract_hits = {}  # contract -> [0/1,...] for bootstrap
    sw = args.semantic_weight
    for it in items:
        c = it["contract"]
        idxs = by_contract.get(c, [])
        if not idxs or it["qa_id"] not in qvec:
            continue
        q = qvec[it["qa_id"]]
        qt = terms(it["question"])
        docs_terms = [terms(chunk_rows[i].get({"standard":"chunk","naive":"naive","ctx_qwen":"ctx_qwen","ctx_gemma":"ctx_gemma"}[args.condition]) or chunk_rows[i]["chunk"]) for i in idxs]
        sem = [cosine(q, cvec[i]["vec"]) for i in idxs]
        bm = norm01(bm25_scores(qt, docs_terms))
        hybrid = [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]
        top = sorted(range(len(idxs)), key=lambda j: hybrid[j], reverse=True)[:args.topk]
        words = contract_words(contracts.get(c, {}))
        gold = tuple(it["gold_words"]) if it.get("gold_words") else None
        hit = any(covers(chunk_span(words, chunk_rows[idxs[j]]["chunk"]), gold) for j in top)
        per_contract_hits.setdefault(c, []).append(1 if hit else 0)

    flat = [h for hs in per_contract_hits.values() for h in hs]
    recall = 100 * sum(flat) / len(flat) if flat else 0.0
    # contract-level bootstrap
    random.seed(0)
    contracts_list = list(per_contract_hits.values())
    boot = []
    for _ in range(10000):
        samp = [random.choice(contracts_list) for _ in contracts_list]
        xs = [h for hs in samp for h in hs]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort()
    lo, hi = boot[250], boot[9750]
    print(f"[{args.condition}] recall@{args.topk} = {recall:.1f}% "
          f"(95% CI {lo:.1f}–{hi:.1f}) over {len(flat)} items")
    print("NOTE: provisional scorer — validate `standard` reproduces ~61.4% before trusting deltas.")


if __name__ == "__main__":
    main()
