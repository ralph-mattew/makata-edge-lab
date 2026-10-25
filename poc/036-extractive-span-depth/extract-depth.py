#!/usr/bin/env python3
"""PoC 036 — generator-free extractive span selection at depth (top-N pool sweep) (OP-1).

PoC-018 ran the ≤3-sentence extractive selector over the top-3 chunks. PoC-025 showed Non-Compete gold
sits at rank 4–10, so this extends the *same* extractor to a deeper pool — sweep N ∈ {3, 5, 10} chunks
before sentence-level re-scoring — in LASAGNA isolation (no other change). Does surfacing rank-4–10
sentences lift per-category span-F1, or do distractor sentences dominate?

Reuses the PoC-018 path: PoC-016 decomposed sub-queries → top-N chunks → split sentences → embed each
with EmbeddingGemma → score by max cosine over the category sub-queries → best ≤3-sentence window →
span-F1 vs gold. Committed vectors for retrieval; EmbeddingGemma server (:8090) for sentence embeddings.
Run: python3 extract-depth.py
"""
from __future__ import annotations
import argparse, json, math, random, re, resource, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
P016 = HERE.parent / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
NS = [3, 5, 10]
DOC_PREFIX = "title: none | text: {t}"
STOP = set("a an the of to in on for and or is are be as by with at from this that these those shall "
           "will may any such other each party parties agreement contract hereof herein thereof "
           "pursuant section".split())


def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def toks(s): return re.findall(r"[a-z0-9]+", s.lower())
def content(s): return [t for t in toks(s) if t not in STOP and len(t) > 2]


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


def hybrid_rank(qv, qt, idxs, cvec, dterms, sw=0.9):
    sem = [cosine(qv, cvec[i]) for i in idxs]
    bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
    return [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]


def decomp_topN(it, idxs, cvec, dterms, subvec, templates, N):
    best = {}
    for k, s in enumerate(templates[it["category"]]):
        h = hybrid_rank(subvec[f'{it["qa_id"]}#{k}'], toks(s), idxs, cvec, dterms)
        for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:N]:
            best[j] = max(best.get(j, -1e9), h[j])
    return sorted(best, key=lambda j: best[j], reverse=True)[:N]


def split_sentences(text, min_words=3, max_words=80):
    parts = re.split(r"(?<=[.;:!?])\s+|\n+", text)
    out = []
    for p in parts:
        w = p.strip().split()
        if len(w) < min_words:
            continue
        for i in range(0, len(w), max_words):
            out.append(" ".join(w[i:i + max_words]))
    return out


def span_f1(ans, gold):
    a, g = Counter(content(ans)), Counter(content(gold))
    if not a or not g:
        return 0.0
    ov = sum((a & g).values()); pr = ov / sum(a.values()); re_ = ov / sum(g.values())
    return 2 * pr * re_ / (pr + re_) if (pr + re_) else 0.0


def embed_batch(url, texts, batch=16):
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
    ap = argparse.ArgumentParser(); ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--window", type=int, default=3); args = ap.parse_args()
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    subvec = {d["key"]: d["vec"] for d in map(json.loads, open(P016 / "emb-subqueries.jsonl"))}
    templates = json.loads((P016 / "decomp-templates.json").read_text())
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [toks(r["chunk"]) for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["category"] in HARD]
    work = []
    for it in items:
        c = contracts.get(it["contract"]); g = it.get("gold_words"); idxs = by_contract.get(it["contract"], [])
        if not c or not g or not idxs: continue
        if not all(f'{it["qa_id"]}#{k}' in subvec for k in range(len(templates.get(it["category"], [])))): continue
        words = (" ".join(c.get("pages", []) or [])).split()
        gold = " ".join(words[g[0]:g[1] + 1])
        if content(gold): work.append((it, gold, idxs))
    print(f"items: {len(work)}  windows<= {args.window} sentences  depth sweep N={NS}")

    # retrieve top-10 once per item (superset); collect all candidate sentences across the union; embed once
    retrieved = {}
    allsents = []
    for it, _, idxs in work:
        top = decomp_topN(it, idxs, cvec, dterms, subvec, templates, max(NS))
        retrieved[it["qa_id"]] = [idxs[j] for j in top]  # ordered by union score, len<=10
        for ci in retrieved[it["qa_id"]]:
            allsents.extend(split_sentences(rows[ci]["chunk"]))
    uniq = list(dict.fromkeys(allsents))
    print(f"embedding {len(uniq)} unique candidate sentences ...")
    svec = dict(zip(uniq, embed_batch(args.emb_url, uniq)))

    results = {}
    for N in NS:
        per_cat = defaultdict(list)
        for it, gold, _ in work:
            cat = it["category"]; subs = [subvec[f'{it["qa_id"]}#{k}'] for k in range(len(templates[cat]))]
            chunks = retrieved[it["qa_id"]][:N]
            sents = []
            for ci in chunks:
                sents.extend(split_sentences(rows[ci]["chunk"]))
            if not sents:
                per_cat[cat].append(0.0); continue
            scores = [max(cosine(svec[s], q) for q in subs) for s in sents]
            bi = max(range(len(sents)), key=lambda i: scores[i])
            lo = max(0, bi - (args.window - 1) // 2); hi = min(len(sents), lo + args.window)
            per_cat[cat].append(span_f1(" ".join(sents[lo:hi]), gold))
        cats = {c: 100 * sum(per_cat[c]) / len(per_cat[c]) for c in HARD}
        hm = sum(cats.values()) / 3
        results[f"N{N}"] = {"hard_mean": hm, "per_category": cats}
        print(f"  N={N:2}  hard-mean span-F1 {hm:5.1f}   Excl {cats['Exclusivity']:.1f} / NonC {cats['Non-Compete']:.1f} / CoC {cats['Change Of Control']:.1f}")

    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = ru / (1024 * 1024) if ru > 1 << 30 else ru / 1024
    results["_meta"] = {"peak_rss_mb_host": round(peak_mb, 1), "n_work": len(work), "window": args.window}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extract-depth.json").write_text(json.dumps(results, indent=2))

    b3 = results["N3"]; b10 = results["N10"]
    print(f"\nPoC-018 top-3 reference: hard-mean 20.7 (Excl 12.2 / NonC 19.1 / CoC 30.8)")
    print(f"N=3 here: hard-mean {b3['hard_mean']:.1f} (sanity vs 018)")
    print(f"ΔN10-N3: NonC {b10['per_category']['Non-Compete']-b3['per_category']['Non-Compete']:+.1f} "
          f"[H1>=+10], CoC {b10['per_category']['Change Of Control']-b3['per_category']['Change Of Control']:+.1f} [H2>=+5], "
          f"Excl {b10['per_category']['Exclusivity']-b3['per_category']['Exclusivity']:+.1f} [H3 not <-3]")
    print(f"host peak RSS {peak_mb:.0f} MB (no generator) [H4 <=6GB]")


if __name__ == "__main__":
    main()
