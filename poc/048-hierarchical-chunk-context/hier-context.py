#!/usr/bin/env python3
"""PoC 048 — hierarchical parent-section context for clause chunks (OP-1).

For each PoC-014 page chunk, derive its nearest preceding section heading/path in the contract and prepend
it (capped) before re-embedding with EmbeddingGemma. Measures recall@3 vs the flat-chunk baseline. Chunk
SPANS are unchanged (recall scoring comparable); only the embedded text changes. Cautionary prior: PoC-016
cross-reference resolution (appending referenced clauses) was rejected for dilution (-0.7 overall).

Run: LAB_POC_ROOT=/path/to/clone/poc python3 hier-context.py
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
OUT = HERE / "results"; RAW = OUT / "raw"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
DOC_PREFIX = "title: none | text: {t}"
HEAD_CAP = 40  # words of heading context prepended

HEAD_RE = re.compile(r"((?:ARTICLE|SECTION|CLAUSE|EXHIBIT|APPENDIX|SCHEDULE)\s+[IVXLC0-9]+(?:\.[0-9]+)*"
                     r"(?:\s*[-–.:]?\s*[A-Z][A-Za-z ]{0,40})?)", re.I)
CAPS_RE = re.compile(r"\b([A-Z][A-Z&/,'’\- ]{6,60}[A-Z])\b")  # run of UPPERCASE title words


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
        chunk = [DOC_PREFIX.format(t=t) for t in texts[i:i + batch]]
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


def heading_for(words, start):
    """Nearest preceding section heading in the 80-word window before the chunk start (+chunk head)."""
    lo = max(0, start - 80)
    window = " ".join(words[lo:start])
    cands = [m.group(1).strip() for m in HEAD_RE.finditer(window)] or [m.group(1).strip() for m in CAPS_RE.finditer(window)]
    if not cands:
        return ""
    h = cands[-1]  # nearest preceding
    return " ".join(h.split()[:HEAD_CAP])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--topk", type=int, default=3); args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    flat = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    contracts = {c["contract"]: (" ".join(c.get("pages", []) or [])).split()
                 for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]
    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words") and json.loads(l)["contract"] in by_c and json.loads(l)["qa_id"] in qvec]

    # build heading-prepended texts for chunks that have a resolvable heading
    cache = RAW / "hier-emb.jsonl"
    hvec = dict(enumerate(flat))  # default: flat vector
    changed = []
    for i, r in enumerate(rows):
        w = contracts.get(r["contract"]); sp = spans[i]
        if not w or not sp: continue
        h = heading_for(w, sp[0])
        if h and h.lower() not in r["chunk"][:len(h) + 5].lower():
            changed.append((i, f"{h}. {r['chunk']}"))
    print(f"chunks with heading context: {len(changed)}/{len(rows)} ({100*len(changed)/len(rows):.0f}%)", flush=True)

    if cache.exists():
        for l in open(cache):
            d = json.loads(l); hvec[d["i"]] = d["v"]
        print(f"loaded cached hier embeddings: {sum(1 for _ in open(cache))}")
    else:
        texts = [t for _, t in changed]
        print(f"embedding {len(texts)} heading-prepended chunks ...", flush=True)
        vs = embed(args.emb_url, texts)
        with open(cache, "w") as f:
            for (i, _), v in zip(changed, vs):
                hvec[i] = v; f.write(json.dumps({"i": i, "v": v}) + "\n")

    def rank(cvecs, it, idxs):
        qv = qvec[it["qa_id"]]; qt = terms(it["question"])
        sem = [cosine(qv, cvecs[i]) for i in idxs]; bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        h = [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]
        return sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]

    def recall(cvecs):
        per_cat, per_contract, allh = defaultdict(list), defaultdict(list), []
        for it in items:
            idxs = by_c[it["contract"]]; gold = tuple(it["gold_words"])
            hit = any(covers(spans[idxs[j]], gold) for j in rank(cvecs, it, idxs))
            per_cat[it["category"]].append(hit); per_contract[it["contract"]].append(hit); allh.append(hit)
        overall = 100 * sum(allh) / len(allh)
        cats = {c: round(100 * sum(per_cat[c]) / len(per_cat[c]), 1) for c in HARD if per_cat[c]}
        return {"overall": round(overall, 1), "hard_mean": round(sum(cats.values()) / len(cats), 1),
                "per_hard": cats, "ci": [round(x, 1) for x in bootstrap(per_contract)]}

    base = recall(flat); hier = recall(hvec)
    res = {"n_items": len(items), "chunks_with_heading": len(changed), "heading_coverage_pct": round(100*len(changed)/len(rows), 1),
           "flat_baseline": base, "hierarchical": hier,
           "delta_overall": round(hier["overall"] - base["overall"], 1),
           "delta_hard_mean": round(hier["hard_mean"] - base["hard_mean"], 1),
           "ref_016_xref": "rejected: -0.7 overall / -1.0 hard (dilution)"}
    h1 = res["delta_hard_mean"] >= 10; h2 = res["delta_overall"] >= -1
    res["H1_hard_ge10"] = h1; res["H2_overall_reg_le1"] = h2
    res["verdict"] = ("ADOPT" if (h1 and h2) else ("REJECT" if (res["delta_hard_mean"] < 3 or res["delta_overall"] < -1) else "INCONCLUSIVE"))
    (OUT / "hier-context.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"heading coverage: {res['heading_coverage_pct']}% of chunks")
    L(f"flat baseline:  overall {base['overall']:.1f}  hard-mean {base['hard_mean']:.1f}  {base['per_hard']}")
    L(f"hierarchical:   overall {hier['overall']:.1f}  hard-mean {hier['hard_mean']:.1f}  {hier['per_hard']}")
    L(f"Δ overall {res['delta_overall']:+.1f}  Δ hard-mean {res['delta_hard_mean']:+.1f}  (016 xref ref: -0.7/-1.0)")
    L(f"H1 hard +>=10: {h1}   H2 overall reg <=1: {h2}   -> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
