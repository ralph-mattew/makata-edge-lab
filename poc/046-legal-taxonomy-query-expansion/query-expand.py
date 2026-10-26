#!/usr/bin/env python3
"""PoC 046 — legal-taxonomy query expansion for hard categories (OP-1).

Forks PoC-030: for each hard-category item, expand into legal clause-element sub-queries (taxonomy.json),
retrieve top-N per sub-query (hybrid 0.9/0.1), union + re-rank to K=3, score recall@3. Compares the
single-query baseline, the PoC-016 generic templates (3/cat), and the legal taxonomy (7/cat).

Committed PoC-014 chunks + emb-page + emb-queries (raw question vecs); PoC-016 emb-subqueries +
decomp-templates for the generic arm; taxonomy sub-queries embedded fresh via EmbeddingGemma.
Run: LAB_POC_ROOT=/path/to/clone/poc python3 query-expand.py
"""
from __future__ import annotations
import argparse, json, math, os, random, re
from collections import Counter, defaultdict
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
P016 = _base / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
QRY_PREFIX = "task: search result | query: {t}"


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
    if not span or not gold: return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def embed(url, texts, batch=16):
    out, i = [], 0
    while i < len(texts):
        chunk = [QRY_PREFIX.format(t=t) for t in texts[i:i + batch]]
        body = json.dumps({"input": chunk}).encode()
        req = urllib.request.Request(url + "/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
        try:
            out.extend(d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]); i += batch
        except Exception:
            if batch == 1: out.append([0.0] * (len(out[-1]) if out else 768)); i += 1
            else: batch = max(1, batch // 2)
    return out


def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed); g = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for grp in (random.choice(g) for _ in g) for v in grp]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--pool", type=int, default=2); args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    subvec = {d["key"]: d["vec"] for d in map(json.loads, open(P016 / "emb-subqueries.jsonl"))}
    templates = json.loads((P016 / "decomp-templates.json").read_text())
    taxonomy = json.loads((HERE / "taxonomy.json").read_text())
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words") and json.loads(l)["contract"] in by_c and json.loads(l)["qa_id"] in qvec]

    # embed taxonomy sub-queries fresh
    taxo_texts = [s for c in HARD for s in taxonomy[c]]
    tv = embed(args.emb_url, taxo_texts)
    taxovec = {}; k = 0
    for c in HARD:
        for s in taxonomy[c]:
            taxovec[(c, s)] = tv[k]; k += 1

    def hyb(qv, qt, idxs):
        sem = [cosine(qv, cvec[i]) for i in idxs]; bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        return [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]

    def single(it, idxs):
        h = hyb(qvec[it["qa_id"]], terms(it["question"]), idxs)
        return sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]

    def pooled(it, idxs, subs, getvec):
        best = {}
        for s in subs:
            qv = getvec(it, s); h = hyb(qv, terms(s), idxs)
            for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.pool]:
                best[j] = max(best.get(j, -1e9), h[j])
        return sorted(best, key=lambda j: best[j], reverse=True)[:args.topk]

    def generic(it, idxs):
        subs = templates[it["category"]]
        return pooled(it, idxs, subs, lambda it, s: subvec[f'{it["qa_id"]}#{subs.index(s)}'])

    def taxo(it, idxs):
        subs = taxonomy[it["category"]]
        return pooled(it, idxs, subs, lambda it, s: taxovec[(it["category"], s)])

    def run(name, fn):
        per_cat, per_contract, allh = defaultdict(list), defaultdict(list), []
        for it in items:
            idxs = by_c[it["contract"]]; gold = tuple(it["gold_words"])
            hit = any(covers(spans[idxs[j]], gold) for j in fn(it, idxs))
            per_cat[it["category"]].append(hit); per_contract[it["contract"]].append(hit); allh.append(hit)
        overall = 100 * sum(allh) / len(allh)
        cats = {c: round(100 * sum(per_cat[c]) / len(per_cat[c]), 1) for c in HARD if per_cat[c]}
        hm = round(sum(cats.values()) / len(cats), 1)
        lo, hi = bootstrap(per_contract)
        return {"overall": round(overall, 1), "hard_mean": hm, "per_hard": cats, "ci": [round(lo, 1), round(hi, 1)]}

    # hard-cat items use expansion; non-hard always single-query (held fixed)
    def hybrid_arm(fn_hard):
        def f(it, idxs): return fn_hard(it, idxs) if it["category"] in HARD else single(it, idxs)
        return f

    res = {"baseline_single": run("single", single),
           "generic_016_030": run("generic", hybrid_arm(generic)),
           "legal_taxonomy": run("taxonomy", hybrid_arm(taxo)),
           "pool_N": args.pool, "n_items": len(items), "n_subqueries_per_cat": {c: len(taxonomy[c]) for c in HARD}}
    b, g, t = res["baseline_single"], res["generic_016_030"], res["legal_taxonomy"]
    res["H1_taxo_vs_single_hard"] = round(t["hard_mean"] - b["hard_mean"], 1)
    res["H2_taxo_vs_generic_hard"] = round(t["hard_mean"] - g["hard_mean"], 1)
    res["H3_overall_regression"] = round(t["overall"] - b["overall"], 1)
    h1 = res["H1_taxo_vs_single_hard"] >= 10; h3 = res["H3_overall_regression"] >= -2
    res["verdict"] = ("ADOPT" if (h1 and h3) else ("REJECT" if res["H2_taxo_vs_generic_hard"] < 3 else "INCONCLUSIVE"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "query-expand.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"recall@3 (pool N={args.pool}, {len(items)} items):")
    for name, r in [("single-query baseline", b), ("generic 016/030 (3/cat)", g), ("legal taxonomy (7/cat)", t)]:
        L(f"  {name:28} overall {r['overall']:.1f}  hard-mean {r['hard_mean']:.1f}  {r['per_hard']}")
    L(f"\nH1 taxo vs single (hard): {res['H1_taxo_vs_single_hard']:+.1f}pp [>=+10 -> {h1}]")
    L(f"H2 taxo vs generic (hard): {res['H2_taxo_vs_generic_hard']:+.1f}pp [>=+3]")
    L(f"H3 overall vs single: {res['H3_overall_regression']:+.1f}pp [>=-2 -> {h3}]")
    L(f"-> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
