#!/usr/bin/env python3
"""PoC 052 — rule-based clause-type labels prepended to chunks (OP-1/OP-2).

Prepend a deterministic clause-type label (+ section heading) to each chunk, re-embed with EmbeddingGemma,
measure recall@3. Generator-free analogue of PoC-011. Cautionary priors: PoC-048 (heading only) inert +0.0;
PoC-016 xref dilution -0.7. Untested element = the clause-type label.

Arms (hard-category items + their contracts' chunks, re-embedded): flat (committed) / clausetype-only / both
(clausetype + heading). heading-only is PoC-048 (cited, inert). Run: LAB_POC_ROOT=... python3 clausetype-labels.py
"""
from __future__ import annotations
import argparse, json, math, os, random, re, urllib.request
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"; RAW = OUT / "raw"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
DOC_PREFIX = "title: none | text: {t}"

# rule-based clause-type classifier (hard cats + fallback)
CLS = [
    ("Exclusivity", re.compile(r"\bexclusiv|\bsole (?:provider|right|supplier|distributor|agent)|exclusive dealing", re.I)),
    ("Non-Compete", re.compile(r"non-?compet|covenant not to compete|shall not .{0,30}compete|competitive (?:activit|business)", re.I)),
    ("Change Of Control", re.compile(r"change (?:of|in) control|change of ownership|\bmerger\b|\bacquisition\b|successor-in-interest|assign.{0,20}change of control", re.I)),
]
HEAD_RE = re.compile(r"((?:ARTICLE|SECTION|CLAUSE|EXHIBIT)\s+[IVXLC0-9]+(?:\.[0-9]+)*(?:\s*[-–.:]?\s*[A-Z][A-Za-z ]{0,40})?)", re.I)
CAPS_RE = re.compile(r"\b([A-Z][A-Z&/,'’\- ]{6,60}[A-Z])\b")


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
def classify(text):
    for label, rx in CLS:
        if rx.search(text): return label
    return "General Provisions"
def heading_for(words, start):
    window = " ".join(words[max(0, start - 80):start])
    cands = [m.group(1).strip() for m in HEAD_RE.finditer(window)] or [m.group(1).strip() for m in CAPS_RE.finditer(window)]
    return " ".join(cands[-1].split()[:40]) if cands else ""
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
    return [np.asarray(v, dtype=np.float32) for v in out]
def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed); g = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for grp in (random.choice(g) for _ in g) for v in grp]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--topk", type=int, default=3); args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    flat = [np.asarray(json.loads(l)["vec"], dtype=np.float32) for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: np.asarray(d["vec"], dtype=np.float32) for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    contracts = {c["contract"]: (" ".join(c.get("pages", []) or [])).split() for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]
    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l)["category"] in HARD and json.loads(l).get("gold_words")
             and json.loads(l)["contract"] in by_c and json.loads(l)["qa_id"] in qvec]
    keep = {it["contract"] for it in items}
    needed = sorted({i for c in keep for i in by_c[c]})
    print(f"{len(keep)} hard contracts, {len(items)} items, re-embed {len(needed)} chunks x2 arms", flush=True)

    labels = {i: classify(rows[i]["chunk"]) for i in needed}
    import collections; print("label dist:", dict(collections.Counter(labels.values())), flush=True)
    heads = {i: heading_for(contracts[rows[i]["contract"]], spans[i][0]) if spans[i] else "" for i in needed}

    ct_text = [f"[Clause Type: {labels[i]}] {rows[i]['chunk']}" for i in needed]
    both_text = [f"[Clause Type: {labels[i]}] [Section: {heads[i]}] {rows[i]['chunk']}" for i in needed]
    print(f"embedding clausetype-only ({len(needed)}) ...", flush=True); ct_v = embed(args.emb_url, ct_text)
    print(f"embedding both ({len(needed)}) ...", flush=True); both_v = embed(args.emb_url, both_text)
    ct = {i: v for i, v in zip(needed, ct_v)}; both = {i: v for i, v in zip(needed, both_v)}

    def recall(getvec):
        per_cat, per_con = defaultdict(list), defaultdict(list)
        for it in items:
            idxs = by_c[it["contract"]]; gold = tuple(it["gold_words"])
            qv = qvec[it["qa_id"]]; qt = terms(it["question"])
            sem = [float(getvec(i) @ qv) for i in idxs]; bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
            h = [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]
            top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
            hit = any(covers(spans[idxs[j]], gold) for j in top)
            per_cat[it["category"]].append(hit); per_con[it["contract"]].append(hit)
        cats = {c: round(100 * sum(per_cat[c]) / len(per_cat[c]), 1) for c in HARD if per_cat[c]}
        return {"hard_mean": round(sum(cats.values()) / len(cats), 1), "per_cat": cats, "ci": [round(x,1) for x in bootstrap(per_con)]}

    res = {"n_items": len(items), "n_contracts": len(keep),
           "flat": recall(lambda i: flat[i]),
           "clausetype_only": recall(lambda i: ct[i]),
           "both": recall(lambda i: both[i])}
    b = res["flat"]["hard_mean"]; ct_hm = res["clausetype_only"]["hard_mean"]; both_hm = res["both"]["hard_mean"]
    best = max(ct_hm, both_hm)
    res["H1_best_vs_flat"] = round(best - b, 1)
    h1 = res["H1_best_vs_flat"] >= 5
    res["ref_048"] = "heading-only chunk context: inert, +0.0 hard-mean"
    res["verdict"] = ("ADOPT" if h1 else ("REJECT" if res["H1_best_vs_flat"] < 3 else "INCONCLUSIVE"))
    (OUT / "clausetype-labels.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"recall@3 hard-mean ({len(items)} hard items, {len(keep)} contracts):")
    for k in ("flat", "clausetype_only", "both"):
        L(f"  {k:16} {res[k]['hard_mean']:5.1f}  {res[k]['per_cat']}")
    L(f"ref PoC-048 heading-only: inert (+0.0)")
    L(f"H1 best(clausetype/both) - flat = {res['H1_best_vs_flat']:+.1f} [>=+5 -> {h1}]  -> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
