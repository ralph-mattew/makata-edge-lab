#!/usr/bin/env python3
"""PoC 014 — hybrid recall@3 + span-integrity for one chunking condition.

Reuses PoC 007/011's validated scorer: per item, restrict to its contract's chunks,
hybrid = 0.9*cosine + 0.1*BM25 (PoC 013 weight), top-3, recall = top-3 cover >=50%
of the gold answer span (PoC 007 definition). Adds:
  - per-category recall (for H2: the weight-invariant hard categories)
  - span-integrity: fraction of gold spans fully contained in a single chunk (H3)
  - contract-level bootstrap CI (as PoC 009)

Writes results/recall-<cond>.json for compare.py. Validate `page` reproduces ~61.4%.
"""
from __future__ import annotations
import argparse, json, math, random, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
RAW = HERE / "results" / "raw"
OUT = HERE / "results"


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def bm25_scores(qt, docs_terms, k1=1.5, b=0.75):
    N = len(docs_terms)
    avgdl = sum(len(d) for d in docs_terms) / max(N, 1)
    df = Counter(t for d in docs_terms for t in set(d))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    out = []
    for d in docs_terms:
        tf = Counter(d)
        out.append(sum(idf.get(t, 0) * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl))
                       for t in qt))
    return out


def norm01(xs):
    lo, hi = min(xs, default=0), max(xs, default=0)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def terms(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def contract_words(c):
    pages = c.get("pages") or []
    return (" ".join(pages) if isinstance(pages, list) else c.get("text", "")).split()


def locate(words, own, start=0):
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
    s0, s1 = span
    g0, g1 = gold
    inter = max(0, min(s1, g1) - max(s0, g0) + 1)
    return inter >= frac * (g1 - g0 + 1)


def contains(span, gold):
    return bool(span and gold and span[0] <= gold[0] and span[1] >= gold[1])


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
    ap.add_argument("--cond", required=True, help="page | clause (reads chunks-<cond>.jsonl + emb-<cond>.jsonl)")
    ap.add_argument("--semantic-weight", type=float, default=0.9)
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args()

    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(RAW / "emb-queries.jsonl"))}
    rows = [json.loads(l) for l in open(RAW / f"chunks-{args.cond}.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(RAW / f"emb-{args.cond}.jsonl")]
    assert len(rows) == len(cvec), f"{len(rows)} chunks vs {len(cvec)} vectors"

    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    # precompute each chunk's word span (use stored span, else locate)
    span_cache = {}

    def chunk_span(ci):
        if ci in span_cache:
            return span_cache[ci]
        r = rows[ci]
        sp = tuple(r["span"]) if r.get("span") else locate(contract_words(contracts[r["contract"]]), r["chunk"])
        span_cache[ci] = sp
        return sp

    sw = args.semantic_weight
    per_contract, per_cat = defaultdict(list), defaultdict(list)
    si_hits, si_total = defaultdict(int), defaultdict(int)  # span-integrity per category
    for it in items:
        c = it["contract"]
        idxs = by_contract.get(c, [])
        if not idxs or it["qa_id"] not in qvec:
            continue
        gold = tuple(it["gold_words"]) if it.get("gold_words") else None
        q, qt = qvec[it["qa_id"]], terms(it["question"])
        dterms = [terms(rows[i]["chunk"]) for i in idxs]
        sem = [cosine(q, cvec[i]) for i in idxs]
        bm = norm01(bm25_scores(qt, dterms))
        hybrid = [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]
        top = sorted(range(len(idxs)), key=lambda j: hybrid[j], reverse=True)[:args.topk]
        hit = any(covers(chunk_span(idxs[j]), gold) for j in top)
        per_contract[c].append(1 if hit else 0)
        per_cat[it["category"]].append(1 if hit else 0)
        # span-integrity: is the gold span fully inside ANY single chunk of this contract?
        si_total[it["category"]] += 1
        if any(contains(chunk_span(i), gold) for i in idxs):
            si_hits[it["category"]] += 1

    flat = [h for g in per_contract.values() for h in g]
    recall = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap(per_contract)
    si_all = 100 * sum(si_hits.values()) / max(sum(si_total.values()), 1)

    cats = {cat: (100 * sum(v) / len(v), len(v)) for cat, v in per_cat.items()}
    result = {"cond": args.cond, "recall": recall, "ci": [lo, hi], "n_items": len(flat),
              "n_chunks": len(rows), "span_integrity": si_all,
              "per_category": {cat: {"recall": r, "n": n} for cat, (r, n) in cats.items()},
              "span_integrity_by_category": {cat: 100 * si_hits[cat] / si_total[cat] for cat in si_total}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"recall-{args.cond}.json").write_text(json.dumps(result, indent=2))

    print(f"[{args.cond}] recall@{args.topk} = {recall:.1f}% (95% CI {lo:.1f}–{hi:.1f}) "
          f"over {len(flat)} items, {len(rows)} chunks")
    print(f"[{args.cond}] span-integrity (gold fully in one chunk) = {si_all:.1f}%")
    if args.cond == "page":
        print("  VALIDATE: page should reproduce ~61.4% (PoC 007) before trusting the clause delta.")


if __name__ == "__main__":
    main()
