#!/usr/bin/env python3
"""PoC 047 — retrieve-then-extract: minimal Qwen verbatim-copy vs generator-free extractor (OP-1).

Three answer-step arms on identical PoC-016 decomposed retrieval (top-3) over the 300 hard-category items:
  cosine   : PoC-036 generator-free ≤3-sentence cosine window (reference)
  copy     : Qwen instructed to copy the single most relevant sentence VERBATIM (no cite/abstain) — headline
  generate : same-retrieval Qwen free generation (PoC-042-style control)
Metric: span-F1 (SQuAD token overlap vs gold, identical to 018/036). Also: verbatim-substring compliance.

Servers: EmbeddingGemma :8090 (cosine arm sentences), Qwen :8091 (copy/generate). Committed vectors via LAB_POC_ROOT.
Run: LAB_POC_ROOT=/path/to/clone/poc python3 retrieve-extract.py
"""
from __future__ import annotations
import argparse, json, math, os, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
P016 = _base / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
DOC_PREFIX = "title: none | text: {t}"
STOP = set("a an the of to in on for and or is are be as by with at from this that these those shall will "
           "may any such other each party parties agreement contract hereof herein thereof pursuant section".split())


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
def nrm(s): return re.sub(r"\s+", " ", s.lower()).strip()


def split_sentences(text, min_words=3, max_words=80):
    out = []
    for p in re.split(r"(?<=[.;:!?])\s+|\n+", text):
        w = p.strip().split()
        if len(w) < min_words: continue
        for i in range(0, len(w), max_words):
            out.append(" ".join(w[i:i + max_words]))
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


COPY_PROMPT = ("Copy the single sentence from the contract sections below that best answers the question. "
               "Output that sentence verbatim and nothing else.\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nSENTENCE:")
GEN_PROMPT = ("Answer the question using ONLY the contract sections below. Be concise. If it is not in the "
              "sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")


def qwen(url, prompt, n=120):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "n_predict": n,
                       "temperature": 0.0, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception:
            time.sleep(1.0 * (a + 1))
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3); ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0); args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    subvec = {d["key"]: d["vec"] for d in map(json.loads, open(P016 / "emb-subqueries.jsonl"))}
    templates = json.loads((P016 / "decomp-templates.json").read_text())
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    dterms = [toks(r["chunk"]) for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["category"] in HARD]
    work = []
    for it in items:
        c = contracts.get(it["contract"]); g = it.get("gold_words"); idxs = by_c.get(it["contract"], [])
        if not c or not g or not idxs: continue
        if not all(f'{it["qa_id"]}#{k}' in subvec for k in range(len(templates.get(it["category"], [])))): continue
        words = (" ".join(c.get("pages", []) or [])).split()
        gold = " ".join(words[g[0]:g[1] + 1])
        if content(gold): work.append((it, gold))
    if args.limit: work = work[:args.limit]
    print(f"items: {len(work)} hard-category", flush=True)

    def decomp_top(it):
        idxs = by_c[it["contract"]]; best = {}
        for k, s in enumerate(templates[it["category"]]):
            qv = subvec[f'{it["qa_id"]}#{k}']
            sem = [cosine(qv, cvec[i]) for i in idxs]; bm = norm01(bm25(toks(s), [dterms[i] for i in idxs]))
            h = [0.9 * x + 0.1 * y for x, y in zip(norm01(sem), bm)]
            for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]:
                best[j] = max(best.get(j, -1e9), h[j])
        return [idxs[j] for j in sorted(best, key=lambda j: best[j], reverse=True)[:args.topk]]

    retrieved = {it["qa_id"]: decomp_top(it) for it, _ in work}

    OUT.mkdir(parents=True, exist_ok=True); raw = OUT / "raw"; raw.mkdir(exist_ok=True)

    # cosine arm (PoC-036): embed candidate sentences, pick best ≤window window by max sub-query cosine
    allsents = []
    for it, _ in work:
        for ci in retrieved[it["qa_id"]]:
            allsents.extend(split_sentences(rows[ci]["chunk"]))
    uniq = list(dict.fromkeys(allsents))
    print(f"embedding {len(uniq)} candidate sentences (cosine arm) ...", flush=True)
    svec = dict(zip(uniq, embed(args.emb_url, uniq)))

    def ctx_of(it): return "\n\n".join(rows[ci]["chunk"] for ci in retrieved[it["qa_id"]])

    arms = {"cosine": defaultdict(list), "copy": defaultdict(list), "generate": defaultdict(list)}
    percon = {k: defaultdict(list) for k in arms}
    compliance = {"copy": 0, "generate": 0}
    dump = []
    for it, gold in work:
        cat = it["category"]; subs = [subvec[f'{it["qa_id"]}#{k}'] for k in range(len(templates[cat]))]
        chunks = [rows[ci]["chunk"] for ci in retrieved[it["qa_id"]]]
        allchunk = nrm(" ".join(chunks))
        # cosine
        sents = [s for ch in chunks for s in split_sentences(ch)]
        if sents:
            sc = [max(cosine(svec[s], q) for q in subs) for s in sents]
            bi = max(range(len(sents)), key=lambda i: sc[i]); lo = max(0, bi - (args.window - 1) // 2); hi = min(len(sents), lo + args.window)
            cos_ans = " ".join(sents[lo:hi])
        else:
            cos_ans = ""
        # copy (Qwen verbatim)
        copy_ans = qwen(args.qwen_url, COPY_PROMPT.format(ctx=ctx_of(it)[:6000], q=it["question"]))
        if copy_ans and nrm(copy_ans)[:100] in allchunk: compliance["copy"] += 1
        # generate (Qwen free)
        gen_ans = qwen(args.qwen_url, GEN_PROMPT.format(ctx=ctx_of(it)[:6000], q=it["question"]))
        if gen_ans and nrm(gen_ans)[:60] in allchunk: compliance["generate"] += 1
        for name, ans in (("cosine", cos_ans), ("copy", copy_ans), ("generate", gen_ans)):
            f = span_f1(ans, gold); arms[name][cat].append(f); percon[name][it["contract"]].append(f)
        dump.append({"qa_id": it["qa_id"], "cat": cat, "cosine": round(100*span_f1(cos_ans, gold),1),
                     "copy": round(100*span_f1(copy_ans, gold),1), "generate": round(100*span_f1(gen_ans, gold),1),
                     "copy_text": copy_ans[:160]})
    (raw / "answers.jsonl").write_text("\n".join(json.dumps(d) for d in dump) + "\n")

    def summ(name):
        cats = {c: round(100 * sum(arms[name][c]) / len(arms[name][c]), 1) for c in HARD if arms[name][c]}
        hm = round(sum(cats.values()) / len(cats), 1)
        lo, hi = bootstrap(percon[name])
        return {"hard_mean": hm, "per_cat": cats, "ci": [round(lo,1), round(hi,1)]}
    res = {k: summ(k) for k in arms}
    res["n"] = len(work)
    res["copy_substring_compliance_pct"] = round(100 * compliance["copy"] / len(work), 1)
    res["generate_substring_compliance_pct"] = round(100 * compliance["generate"] / len(work), 1)
    res["H1_copy_vs_cosine"] = round(res["copy"]["hard_mean"] - res["cosine"]["hard_mean"], 1)
    h1 = res["H1_copy_vs_cosine"] >= 5
    res["verdict"] = ("ADOPT" if h1 else ("REJECT" if res["H1_copy_vs_cosine"] < -0 else "INCONCLUSIVE"))
    (OUT / "retrieve-extract.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    for k in ("cosine", "copy", "generate"):
        L(f"{k:9} hard-mean span-F1 {res[k]['hard_mean']:5.1f}  {res[k]['per_cat']}")
    L(f"copy verbatim-substring compliance: {res['copy_substring_compliance_pct']}%  (generate: {res['generate_substring_compliance_pct']}%)")
    L(f"H1 copy - cosine (036): {res['H1_copy_vs_cosine']:+.1f}pp [>=+5 -> {h1}]  -> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
