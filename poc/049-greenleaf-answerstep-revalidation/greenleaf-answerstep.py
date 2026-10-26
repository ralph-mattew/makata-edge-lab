#!/usr/bin/env python3
"""PoC 049 — does GreenLeaf's retrieval gain convert at the answer step? (OP-1/OP-2)

Runs the PoC-036 generator-free extractor (decomposed sub-queries -> top-N chunks -> split sentences ->
max-cosine over sub-queries -> best <=3-sentence window -> span-F1) with TWO embedders and compares:
  EG  : EmbeddingGemma (committed emb-page chunk vecs + :8090 for 016 sub-queries & candidate sentences)
  GL  : GreenLeaf-Tiny (AutoModel/MPS) for chunk vecs + sub-queries + candidate sentences
Reports hard-mean span-F1 for both, recall@3 for both, and the conversion ratio (Δspan-F1 / Δrecall@3)
against PoC-040's ~0. Hard-contract sample (GreenLeaf full-corpus encode is infeasible on MPS; see README).

Servers: EmbeddingGemma :8090 (EG arm). Run: LAB_POC_ROOT=/path/to/clone/poc python3 greenleaf-answerstep.py --contracts 80
"""
from __future__ import annotations
import argparse, json, math, os, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
P016 = _base / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"; RAW = OUT / "raw"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
GL_MODEL = "judicialmind/greenleaf-law-embed-tiny"
EG_DOC = "title: none | text: {t}"
STOP = set("a an the of to in on for and or is are be as by with at from this that these those shall will "
           "may any such other each party parties agreement contract hereof herein thereof pursuant section".split())


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
def covers(span, gold, frac=0.5):
    if not span or not gold: return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)
def split_sentences(text, min_words=3, max_words=80):
    out = []
    for p in re.split(r"(?<=[.;:!?])\s+|\n+", text):
        w = p.strip().split()
        if len(w) < min_words: continue
        for i in range(0, len(w), max_words): out.append(" ".join(w[i:i + max_words]))
    return out
def span_f1(ans, gold):
    a, g = Counter(content(ans)), Counter(content(gold))
    if not a or not g: return 0.0
    ov = sum((a & g).values()); pr = ov / sum(a.values()); rc = ov / sum(g.values())
    return 2 * pr * rc / (pr + rc) if (pr + rc) else 0.0
def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed); g = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for grp in (random.choice(g) for _ in g) for v in grp]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def eg_embed(url, texts, prefix, batch=16):
    out, i = [], 0
    while i < len(texts):
        chunk = [prefix.format(t=t) for t in texts[i:i + batch]]
        body = json.dumps({"input": chunk}).encode()
        req = urllib.request.Request(url + "/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
        try:
            out.extend(d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]); i += batch
        except Exception:
            if batch == 1: out.append([0.0] * (len(out[-1]) if out else 768)); i += 1
            else: batch = max(1, batch // 2)
    return [np.asarray(v, dtype=np.float32) for v in out]


def gl_encoder():
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(GL_MODEL, trust_remote_code=True)
    mdl = AutoModel.from_pretrained(GL_MODEL, trust_remote_code=True).to("mps").eval()
    def emb(texts, batch=160, max_length=128, tag=""):
        order = sorted(range(len(texts)), key=lambda i: len(texts[i])); out = [None] * len(texts); t0 = time.time()
        for b0 in range(0, len(order), batch):
            idx = order[b0:b0 + batch]
            b = tok([texts[i] for i in idx], padding=True, truncation=True, max_length=max_length, return_tensors="pt").to("mps")
            with torch.no_grad(): o = mdl(**b)
            h = o.last_hidden_state if hasattr(o, "last_hidden_state") else o[0]
            m = b["attention_mask"].unsqueeze(-1).float()
            v = torch.nn.functional.normalize((h * m).sum(1) / m.sum(1).clamp(min=1e-9), dim=1).cpu().numpy().astype(np.float32)
            for k, i in enumerate(idx): out[i] = v[k]
            if (b0 // batch) % 40 == 0: print(f"    [{tag}] {b0+len(idx)}/{len(texts)} ({(b0+len(idx))/(time.time()-t0+1e-9):.0f}/s)", flush=True)
        return np.asarray(out, dtype=np.float32)
    return emb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--depth", type=int, default=10)
    ap.add_argument("--window", type=int, default=3); ap.add_argument("--contracts", type=int, default=80)
    ap.add_argument("--seed", type=int, default=0); args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    egc = np.array([json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")], dtype=np.float32)
    subvec_eg = {d["key"]: np.asarray(d["vec"], dtype=np.float32) for d in map(json.loads, open(P016 / "emb-subqueries.jsonl"))}
    templates = json.loads((P016 / "decomp-templates.json").read_text())
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    dterms = [toks(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["category"] in HARD]
    work = []
    for it in items:
        c = contracts.get(it["contract"]); g = it.get("gold_words"); idxs = by_c.get(it["contract"], [])
        if not c or not g or not idxs: continue
        if not all(f'{it["qa_id"]}#{k}' in subvec_eg for k in range(len(templates.get(it["category"], [])))): continue
        gold = " ".join((" ".join(c.get("pages", []) or [])).split()[g[0]:g[1] + 1])
        if content(gold): work.append((it, gold))
    # sample hard contracts
    random.seed(args.seed); hc = sorted({it["contract"] for it, _ in work}); random.shuffle(hc)
    keep = set(hc[:args.contracts])
    work = [(it, g) for it, g in work if it["contract"] in keep]
    needed = sorted({i for c in keep for i in by_c[c]})
    print(f"sampled {len(keep)} hard contracts, {len(work)} items, {len(needed)} chunks to GL-embed", flush=True)

    # ---- GreenLeaf embeddings: chunks + sub-queries + (later) sentences ----
    enc = gl_encoder()
    glc = np.zeros((len(rows), 1024), dtype=np.float32)
    t0 = time.time(); glc[needed] = enc([rows[i]["chunk"] for i in needed], tag="chunks")
    print(f"GL chunk embed: {(time.time()-t0)/60:.1f} min", flush=True)
    sub_texts = sorted({s for c in HARD for s in templates[c]})
    sub_gl = dict(zip(sub_texts, enc(sub_texts, tag="subq")))
    subvec_gl = {f'{it["qa_id"]}#{k}': sub_gl[templates[it["category"]][k]]
                 for it, _ in work for k in range(len(templates[it["category"]]))}

    def decomp_topN(it, cvecs, subv, N):
        idxs = by_c[it["contract"]]; best = {}
        for k, s in enumerate(templates[it["category"]]):
            qv = subv[f'{it["qa_id"]}#{k}']
            sem = [float(cvecs[i] @ qv) for i in idxs]; bm = norm01(bm25(toks(s), [dterms[i] for i in idxs]))
            h = [0.9 * x + 0.1 * y for x, y in zip(norm01(sem), bm)]
            for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:N]:
                best[j] = max(best.get(j, -1e9), h[j])
        return [idxs[j] for j in sorted(best, key=lambda j: best[j], reverse=True)[:N]]

    # candidate sentences for the chosen chunks (both embedders)
    def extract(retr, sentvec, subv):
        per_cat, per_con, cov = defaultdict(list), defaultdict(list), defaultdict(list)
        for it, gold in work:
            top = retr(it); gw = tuple(it["gold_words"])
            cov[it["category"]].append(any(covers(spans[j], gw) for j in top[:3]))
            subs = [subv[f'{it["qa_id"]}#{k}'] for k in range(len(templates[it["category"]]))]
            sents = [s for ci in top for s in split_sentences(rows[ci]["chunk"])]
            if not sents: per_cat[it["category"]].append(0.0); per_con[it["contract"]].append(0.0); continue
            sc = [max(float(sentvec[s] @ q) for q in subs) for s in sents]
            bi = max(range(len(sents)), key=lambda i: sc[i]); lo = max(0, bi - (args.window - 1) // 2); hi = min(len(sents), lo + args.window)
            f = span_f1(" ".join(sents[lo:hi]), gold)
            per_cat[it["category"]].append(f); per_con[it["contract"]].append(f)
        cats = {c: round(100 * sum(per_cat[c]) / len(per_cat[c]), 1) for c in HARD if per_cat[c]}
        covs = {c: round(100 * sum(cov[c]) / len(cov[c]), 1) for c in HARD if cov[c]}
        return {"hard_mean_f1": round(sum(cats.values()) / len(cats), 1), "per_cat": cats,
                "recall3_hard": round(sum(covs.values()) / len(covs), 1), "ci": [round(x, 1) for x in bootstrap(per_con)]}

    # collect all candidate sentences once per embedder
    def all_sentences(retr):
        S = []
        for it, _ in work:
            for ci in retr(it): S.extend(split_sentences(rows[ci]["chunk"]))
        return list(dict.fromkeys(S))

    retr_eg = lambda it: decomp_topN(it, egc, subvec_eg, args.depth)
    retr_gl = lambda it: decomp_topN(it, glc, subvec_gl, args.depth)

    print("embedding EG candidate sentences (:8090) ...", flush=True)
    eg_sents = all_sentences(retr_eg); eg_sv = dict(zip(eg_sents, eg_embed(args.emb_url, eg_sents, EG_DOC)))
    print(f"embedding GL candidate sentences ({len(all_sentences(retr_gl))}) ...", flush=True)
    gl_sents = all_sentences(retr_gl); gl_sv = dict(zip(gl_sents, enc(gl_sents, tag="sent")))

    eg = extract(retr_eg, eg_sv, subvec_eg)
    gl = extract(retr_gl, gl_sv, subvec_gl)

    d_f1 = round(gl["hard_mean_f1"] - eg["hard_mean_f1"], 1)
    d_r3 = round(gl["recall3_hard"] - eg["recall3_hard"], 1)
    conv = round(d_f1 / d_r3, 2) if d_r3 else None
    h1 = d_f1 >= 5
    res = {"n_items": len(work), "n_contracts": len(keep), "depth": args.depth,
           "embeddinggemma_extractor": eg, "greenleaf_extractor": gl,
           "delta_span_f1": d_f1, "delta_recall3": d_r3, "conversion_ratio": conv,
           "ref_poc036": "hard-mean span-F1 22.1 (full 300)", "ref_poc040": "chunk-size conversion ~0",
           "ref_poc045": "GreenLeaf recall@3 hard-mean +14.3 (216-contract sample)",
           "H1_span_f1_ge5": h1}
    res["verdict"] = ("ADOPT" if h1 else ("REJECT" if d_f1 < 2 else "INCONCLUSIVE"))
    (OUT / "greenleaf-answerstep.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"sample: {len(work)} hard items / {len(keep)} contracts, extractor N={args.depth}, window<={args.window}")
    L(f"EmbeddingGemma extractor: span-F1 {eg['hard_mean_f1']}  {eg['per_cat']}  | recall@3 {eg['recall3_hard']}")
    L(f"GreenLeaf      extractor: span-F1 {gl['hard_mean_f1']}  {gl['per_cat']}  | recall@3 {gl['recall3_hard']}")
    L(f"Δ span-F1 {d_f1:+.1f}   Δ recall@3 {d_r3:+.1f}   conversion ratio {conv}  (PoC-040 ref ~0)")
    L(f"H1 span-F1 +>=5: {h1}  -> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
