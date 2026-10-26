#!/usr/bin/env python3
"""PoC 053 — pre-retrieval clause-term binding (query prefix) (OP-1).

Prepend a static canonical clause-term prefix to the hard-category query before embedding, measure
recall@3. Isolates the VOCABULARY half of PoC-046's taxonomy win (vs decomposition/pooling). Arms:
question-only (baseline), prefix-only, concat(prefix+question); reference = PoC-046 taxonomy (pooled).

Committed PoC-014 chunks + emb-page + emb-queries; PoC-046 taxonomy.json for the reference arm.
Run: LAB_POC_ROOT=/path/to/clone/poc python3 clauseterm-binding.py
"""
from __future__ import annotations
import argparse, json, math, os, random, re, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
P046 = _base / "046-legal-taxonomy-query-expansion"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
QRY_PREFIX = "task: search result | query: {t}"

CANON = {
    "Exclusivity": "exclusive rights sole provider exclusivity period exclusive territory exclusive dealing exclusivity clause",
    "Non-Compete": "non-competition covenant not to compete competitive restriction no-compete competitive activities non-compete",
    "Change Of Control": "change of control acquisition merger assignment on change successor-in-interest takeover provision",
}


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
    taxonomy = json.loads((P046 / "taxonomy.json").read_text())
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]
    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words") and json.loads(l)["contract"] in by_c and json.loads(l)["qa_id"] in qvec]
    hard_items = [it for it in items if it["category"] in HARD]

    # embed prefix-only + concat queries for hard items; + taxonomy sub-queries (reference)
    prefix_text = {it["qa_id"]: CANON[it["category"]] for it in hard_items}
    concat_text = {it["qa_id"]: CANON[it["category"]] + " " + it["question"] for it in hard_items}
    uniq_prefix = sorted(set(prefix_text.values()))
    pv = dict(zip(uniq_prefix, embed(args.emb_url, uniq_prefix)))
    cc = {qid: v for qid, v in zip(concat_text, embed(args.emb_url, list(concat_text.values())))}
    taxo_texts = sorted({s for c in HARD for s in taxonomy[c]})
    tvec = dict(zip(taxo_texts, embed(args.emb_url, taxo_texts)))

    def hyb(qv, qt, idxs):
        sem = [cosine(qv, cvec[i]) for i in idxs]; bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        return [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]

    def single_top(qv, qt, idxs):
        h = hyb(qv, qt, idxs); return sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]

    def taxo_top(it, idxs):
        best = {}
        for s in taxonomy[it["category"]]:
            h = hyb(tvec[s], terms(s), idxs)
            for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.pool]:
                best[j] = max(best.get(j, -1e9), h[j])
        return sorted(best, key=lambda j: best[j], reverse=True)[:args.topk]

    def run(name, topfn):
        per_cat, per_con = defaultdict(list), defaultdict(list)
        for it in hard_items:
            idxs = by_c[it["contract"]]; gold = tuple(it["gold_words"])
            hit = any(covers(spans[idxs[j]], gold) for j in topfn(it, idxs))
            per_cat[it["category"]].append(hit); per_con[it["contract"]].append(hit)
        cats = {c: round(100 * sum(per_cat[c]) / len(per_cat[c]), 1) for c in HARD if per_cat[c]}
        hm = round(sum(cats.values()) / len(cats), 1)
        return {"hard_mean": hm, "per_cat": cats, "ci": [round(x, 1) for x in bootstrap(per_con)]}

    res = {
        "question_only": run("q", lambda it, idxs: single_top(qvec[it["qa_id"]], terms(it["question"]), idxs)),
        "prefix_only":   run("p", lambda it, idxs: single_top(pv[prefix_text[it["qa_id"]]], terms(CANON[it["category"]]), idxs)),
        "concat":        run("c", lambda it, idxs: single_top(cc[it["qa_id"]], terms(concat_text[it["qa_id"]]), idxs)),
        "ref_046_taxonomy": run("t", taxo_top),
        "n_hard": len(hard_items),
    }
    b = res["question_only"]["hard_mean"]; best_bind = max(res["prefix_only"]["hard_mean"], res["concat"]["hard_mean"])
    taxo = res["ref_046_taxonomy"]["hard_mean"]
    res["H1_binding_vs_single"] = round(best_bind - b, 1)
    res["H2_binding_vs_046"] = round(best_bind - taxo, 1)
    h1 = res["H1_binding_vs_single"] >= 5
    res["verdict"] = ("ADOPT" if (h1 and res["H2_binding_vs_046"] >= -2) else ("REJECT" if res["H1_binding_vs_single"] < 3 else "INCONCLUSIVE"))
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "clauseterm-binding.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"recall@3 (hard-mean), {len(hard_items)} hard items:")
    for k in ("question_only", "prefix_only", "concat", "ref_046_taxonomy"):
        L(f"  {k:18} {res[k]['hard_mean']:5.1f}  {res[k]['per_cat']}")
    L(f"\nH1 best-binding vs single: {res['H1_binding_vs_single']:+.1f} [>=+5 -> {h1}]")
    L(f"H2 best-binding vs 046 taxonomy: {res['H2_binding_vs_046']:+.1f} (>=-2 means ties/beats 046)")
    L(f"-> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
