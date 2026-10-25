#!/usr/bin/env python3
"""PoC 040 — composed hard-category pipeline (OP-1/OP-2).

Composes the individually-validated hard-category levers into one end-to-end stack and measures an
isolated -> composed ladder (LASAGNA discipline):

  B0  014 (~25w) chunks,  raw query,  top-3,  Qwen generate (PoC-017 prompt)     [production baseline]
  B1  014 chunks,         decomp,     top-10, extractive <=3-sent                [= PoC-036 N=10; control]
  C1  W=384 (512-tok),    raw query,  top-10, extractive <=3-sent                [chunk-size isolation]
  C2  W=384,              decomp,     top-10, extractive <=3-sent                [HEADLINE composition]
  C2p W=384, decomp pool=2 per sub-query (PoC-030) then depth<=10, extractive    [030 refinement probe]

Answer metric: span-F1 (SQuAD token overlap vs gold span), identical definition to PoC-017/018/036.
Retrieval metric: recall@3-equiv coverage (top-3 chunks cover >=50% of gold word-span).

Reuses committed vectors for 014-chunk retrieval + decomposition sub-queries; regenerates the W=384
chunk index fresh via EmbeddingGemma (identical to PoC-037, cached to results/raw/). Sentence
embeddings for the extractor are computed live. Qwen (:8091) is loaded only for B0.

Servers:
  llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
    -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
  llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &   # B0 only

Run: python3 pipeline.py            # B1/C1/C2/C2p (needs :8090)
     python3 pipeline.py --b0       # also run the Qwen production baseline (needs :8091)
"""
from __future__ import annotations
import argparse, json, math, random, re, resource, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Committed retrieval vectors (007/014/016 results/raw) are gitignored heavy artifacts that live only
# in the main lab clone's working tree, not in a fresh git worktree checkout. Read them (read-only)
# from the main clone; fall back to the sibling path if present.
LAB = Path("/Users/rlpalomaria/Projects/makata-edge-lab/poc")
_base = LAB if (LAB / "007-embedding-retrieval-recall" / "results" / "raw" / "contracts.jsonl").exists() else HERE.parent
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
P016 = _base / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"; RAW = OUT / "raw"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
W384 = 384
DOC_PREFIX = "title: none | text: {t}"
STOP = set("a an the of to in on for and or is are be as by with at from this that these those shall "
           "will may any such other each party parties agreement contract hereof herein thereof "
           "pursuant section".split())

# PoC-018/036 answer-step reference numbers (014 chunks), for control validation:
REF_036_N10 = {"hard_mean": 22.1, "Exclusivity": 13.1, "Non-Compete": 22.5, "Change Of Control": 30.6}
REF_018_GEN = 15.7  # PoC-018 same-retrieval (decomp) Qwen generate arm


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


def hybrid_rank(qv, qt, dvecs, dterms, sw=0.9):
    sem = [cosine(qv, v) for v in dvecs]
    bm = norm01(bm25(qt, dterms))
    return [sw * s + (1 - sw) * b for s, b in zip(norm01(sem), bm)]


def covers(span, gold, frac=0.5):
    if not span or not gold:
        return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


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
    ov = sum((a & g).values()); pr = ov / sum(a.values()); rc = ov / sum(g.values())
    return 2 * pr * rc / (pr + rc) if (pr + rc) else 0.0


def bootstrap_f1(per_contract, n=10000, seed=0):
    random.seed(seed); groups = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for g in (random.choice(groups) for _ in groups) for v in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


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


PROMPT = ("Answer the question using ONLY the contract sections below. Quote the specific "
          "clause text that answers it. If it is not in the sections, say \"not stated\".\n\n"
          "SECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")


def qwen(url, q, ctx, n=160):
    body = json.dumps({"messages": [{"role": "user", "content": PROMPT.format(ctx=ctx[:6000], q=q)}],
                       "n_predict": n, "temperature": 0.1, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception:
            time.sleep(1.0 * (a + 1))
    return ""


def peak_rss_mb():
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return ru / (1024 * 1024) if ru > 1 << 30 else ru / 1024


def chunk_contract(words, W):
    out = []
    for s in range(0, len(words), W):
        seg = words[s:s + W]
        if seg:
            out.append((" ".join(seg), (s, s + len(seg) - 1)))
    return out


def summarize(arm, per_cat, per_contract, cov_cat=None):
    cats = {c: 100 * sum(per_cat[c]) / len(per_cat[c]) for c in HARD if per_cat[c]}
    hm = sum(cats.values()) / max(len(cats), 1)
    lo, hi = bootstrap_f1(per_contract)
    out = {"arm": arm, "hard_mean_f1": round(hm, 2), "ci": [round(lo, 2), round(hi, 2)],
           "per_category_f1": {c: round(cats.get(c, 0.0), 2) for c in HARD},
           "n_items": sum(len(per_cat[c]) for c in HARD)}
    if cov_cat is not None:
        cc = {c: 100 * sum(cov_cat[c]) / len(cov_cat[c]) for c in HARD if cov_cat[c]}
        out["recall3_coverage"] = {c: round(cc.get(c, 0.0), 1) for c in HARD}
        out["recall3_hard_mean"] = round(sum(cc.values()) / max(len(cc), 1), 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090")
    ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--b0", action="store_true", help="also run the Qwen production baseline (needs :8091)")
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--depth", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    # ---- committed inputs ----
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    cwords = {c: (" ".join(contracts[c].get("pages", []) or [])).split() for c in contracts}
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    pvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    assert len(rows) == len(pvec)
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    subvec = {d["key"]: d["vec"] for d in map(json.loads, open(P016 / "emb-subqueries.jsonl"))}
    templates = json.loads((P016 / "decomp-templates.json").read_text())
    by_contract014 = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract014[r["contract"]].append(i)
    dterms014 = [toks(r["chunk"]) for r in rows]

    items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["category"] in HARD]
    work = []
    for it in items:
        c = it["contract"]; g = it.get("gold_words")
        if c not in contracts or not g or c not in by_contract014 or it["qa_id"] not in qvec:
            continue
        if not all(f'{it["qa_id"]}#{k}' in subvec for k in range(len(templates.get(it["category"], [])))):
            continue
        gold = " ".join(cwords[c][g[0]:g[1] + 1])
        if content(gold):
            work.append((it, gold, tuple(g)))
    if args.limit:
        work = work[:args.limit]
    print(f"work items: {len(work)}  (window<={args.window}, depth={args.depth})")

    # ---- build / load the W=384 chunk index (EmbeddingGemma, same as PoC-037) ----
    idx_path = RAW / "w384-index.jsonl"
    w384 = {}  # contract -> [(text,(s,e),vec)]
    needed = {it["contract"] for it, _, _ in work}
    if idx_path.exists():
        for l in open(idx_path):
            d = json.loads(l)
            w384.setdefault(d["c"], []).append((d["t"], tuple(d["s"]), d["v"]))
        print(f"  loaded cached W=384 index: {sum(len(v) for v in w384.values())} chunks, {len(w384)} contracts")
    missing = [c for c in needed if c not in w384]
    if missing:
        texts, index = [], []
        for c in missing:
            for (t, sp) in chunk_contract(cwords[c], W384):
                texts.append(t); index.append((c, sp))
        print(f"  embedding {len(texts)} W=384 chunks for {len(missing)} contracts via EmbeddingGemma ...")
        vecs = embed_batch(args.emb_url, texts)
        with open(idx_path, "a") as f:
            for (c, sp), t, v in zip(index, texts, vecs):
                w384.setdefault(c, []).append((t, sp, v))
                f.write(json.dumps({"c": c, "t": t, "s": list(sp), "v": v}) + "\n")

    # ---- sentence-embedding cache (shared across arms) ----
    svec = {}
    def embed_sents(sent_sets):
        need = list(dict.fromkeys(s for ss in sent_sets for s in ss if s not in svec))
        if need:
            print(f"    embedding {len(need)} new candidate sentences ...")
            for s, v in zip(need, embed_batch(args.emb_url, need)):
                svec[s] = v

    # ---- retrieval helpers ----
    def retr_014_decomp(it, N):
        idxs = by_contract014[it["contract"]]
        best = {}
        for k, s in enumerate(templates[it["category"]]):
            h = hybrid_rank(subvec[f'{it["qa_id"]}#{k}'], toks(s), [pvec[i] for i in idxs], [dterms014[i] for i in idxs])
            for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:N]:
                best[j] = max(best.get(j, -1e9), h[j])
        order = sorted(best, key=lambda j: best[j], reverse=True)[:N]
        return [(rows[idxs[j]]["chunk"], tuple(rows[idxs[j]]["span"]) if rows[idxs[j]].get("span") else None) for j in order]

    def retr_w384_raw(it, N):
        ch = w384[it["contract"]]
        dvecs = [v for _, _, v in ch]; dterms = [toks(t) for t, _, _ in ch]
        h = hybrid_rank(qvec[it["qa_id"]], toks(it["question"]), dvecs, dterms)
        order = sorted(range(len(ch)), key=lambda j: h[j], reverse=True)[:N]
        return [(ch[j][0], ch[j][1]) for j in order]

    def retr_w384_decomp(it, N, pool=None):
        """pool=None -> top-N per sub-query (= PoC-036 pool==depth). pool=k -> PoC-030 k-per-subquery."""
        per = pool if pool else N
        ch = w384[it["contract"]]
        dvecs = [v for _, _, v in ch]; dterms = [toks(t) for t, _, _ in ch]
        best = {}
        for k, s in enumerate(templates[it["category"]]):
            h = hybrid_rank(subvec[f'{it["qa_id"]}#{k}'], toks(s), dvecs, dterms)
            for j in sorted(range(len(ch)), key=lambda j: h[j], reverse=True)[:per]:
                best[j] = max(best.get(j, -1e9), h[j])
        order = sorted(best, key=lambda j: best[j], reverse=True)[:N]
        return [(ch[j][0], ch[j][1]) for j in order]

    def extract_answer(it, chunks):
        """chunks: list of (text, span). PoC-018/036 extractor: split -> max-cos sub-query -> <=window window."""
        subs = [subvec[f'{it["qa_id"]}#{k}'] for k in range(len(templates[it["category"]]))]
        sents = []
        for t, _ in chunks:
            sents.extend(split_sentences(t))
        if not sents:
            return ""
        scores = [max(cosine(svec[s], q) for q in subs) for s in sents]
        bi = max(range(len(sents)), key=lambda i: scores[i])
        lo = max(0, bi - (args.window - 1) // 2); hi = min(len(sents), lo + args.window)
        return " ".join(sents[lo:hi])

    def extract_answer_raw(it, chunks):
        """raw-query variant: score sentences vs the single committed raw-question vector."""
        q = qvec[it["qa_id"]]
        sents = []
        for t, _ in chunks:
            sents.extend(split_sentences(t))
        if not sents:
            return ""
        scores = [cosine(svec[s], q) for s in sents]
        bi = max(range(len(sents)), key=lambda i: scores[i])
        lo = max(0, bi - (args.window - 1) // 2); hi = min(len(sents), lo + args.window)
        return " ".join(sents[lo:hi])

    D = args.depth
    results = {}

    def run_extractive(tag, retr, raw_scoring=False):
        chosen = {it["qa_id"]: retr(it) for it, _, _ in work}
        embed_sents([[s for t, _ in chosen[it["qa_id"]] for s in split_sentences(t)] for it, _, _ in work])
        per_cat, per_contract, cov = defaultdict(list), defaultdict(list), defaultdict(list)
        dump = []
        for it, gold, gw in work:
            chunks = chosen[it["qa_id"]]
            ans = (extract_answer_raw if raw_scoring else extract_answer)(it, chunks)
            f1 = span_f1(ans, gold)
            per_cat[it["category"]].append(f1); per_contract[it["contract"]].append(f1)
            cov[it["category"]].append(any(covers(sp, gw) for _, sp in chunks[:3]))
            dump.append({"qa_id": it["qa_id"], "category": it["category"], "answer": ans,
                         "gold": gold, "span_f1": round(100 * f1, 2)})
        (RAW / f"{tag}-answers.jsonl").write_text("\n".join(json.dumps(d) for d in dump) + "\n")
        r = summarize(tag, per_cat, per_contract, cov)
        results[tag] = r
        print(f"[{tag:5}] hard-mean span-F1 {r['hard_mean_f1']:5.1f} (CI {r['ci'][0]:.1f}-{r['ci'][1]:.1f})  "
              f"Excl {r['per_category_f1']['Exclusivity']:.1f}/NonC {r['per_category_f1']['Non-Compete']:.1f}/"
              f"CoC {r['per_category_f1']['Change Of Control']:.1f}  | recall@3 hm {r['recall3_hard_mean']}")
        return r

    # ---- B1: 014 chunks, decomp, extractor depth-10 (control vs PoC-036 N=10) ----
    run_extractive("B1", lambda it: retr_014_decomp(it, D))
    # ---- C1: W=384 chunks, RAW query, top-10, extractor (chunk-size isolation) ----
    run_extractive("C1", lambda it: retr_w384_raw(it, D), raw_scoring=True)
    # ---- C2: W=384 chunks, decomp, depth-10 (HEADLINE) ----
    run_extractive("C2", lambda it: retr_w384_decomp(it, D))
    # ---- C2p: W=384, decomp with PoC-030 per-sub-query pool=2 then depth<=10 (030 refinement probe) ----
    run_extractive("C2p", lambda it: retr_w384_decomp(it, D, pool=2))

    # ---- B0: production baseline — 014 chunks, raw query top-3, Qwen generate ----
    if args.b0:
        per_cat, per_contract, cov = defaultdict(list), defaultdict(list), defaultdict(list)
        dump = []
        for it, gold, gw in work:
            idxs = by_contract014[it["contract"]]
            h = hybrid_rank(qvec[it["qa_id"]], toks(it["question"]), [pvec[i] for i in idxs], [dterms014[i] for i in idxs])
            top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:3]
            chunks = [(rows[idxs[j]]["chunk"], tuple(rows[idxs[j]]["span"]) if rows[idxs[j]].get("span") else None) for j in top]
            ans = qwen(args.qwen_url, it["question"], "\n\n".join(t for t, _ in chunks))
            f1 = span_f1(ans, gold)
            per_cat[it["category"]].append(f1); per_contract[it["contract"]].append(f1)
            cov[it["category"]].append(any(covers(sp, gw) for _, sp in chunks))
            dump.append({"qa_id": it["qa_id"], "category": it["category"], "answer": ans,
                         "gold": gold, "span_f1": round(100 * f1, 2)})
        (RAW / "B0-answers.jsonl").write_text("\n".join(json.dumps(d) for d in dump) + "\n")
        r = summarize("B0", per_cat, per_contract, cov); results["B0"] = r
        print(f"[B0   ] hard-mean span-F1 {r['hard_mean_f1']:5.1f} (production: raw+top3+Qwen generate)")

    # ---- read-out ----
    results["_meta"] = {"peak_rss_mb_host": round(peak_rss_mb(), 1), "window": args.window,
                        "depth": D, "n_work": len(work), "b0": bool(args.b0)}
    (OUT / "pipeline.json").write_text(json.dumps(results, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L("\n===== PoC-040 composed pipeline — read-out =====")
    L(f"control: B1 should reproduce PoC-036 N=10 (hard-mean {REF_036_N10['hard_mean']}; "
      f"Excl {REF_036_N10['Exclusivity']}/NonC {REF_036_N10['Non-Compete']}/CoC {REF_036_N10['Change Of Control']})")
    L(f"  B1 measured: hard-mean {results['B1']['hard_mean_f1']}  "
      f"Excl {results['B1']['per_category_f1']['Exclusivity']}/NonC {results['B1']['per_category_f1']['Non-Compete']}/"
      f"CoC {results['B1']['per_category_f1']['Change Of Control']}")
    best_single = max(results['B1']['hard_mean_f1'], REF_036_N10['hard_mean'])
    c2 = results['C2']['hard_mean_f1']
    L(f"\nH1 (C2 hard-mean span-F1 >= 30):            C2={c2}  -> {'PASS' if c2>=30 else 'FAIL'}")
    L(f"H2 (chunk-size adds >=+3: C2 - B1):          {c2-results['B1']['hard_mean_f1']:+.1f}  "
      f"-> {'PASS' if c2-results['B1']['hard_mean_f1']>=3 else 'FAIL'}")
    L(f"H3 (composed > best single lever by >=+3):   C2 - max(B1,036)={c2-best_single:+.1f}  "
      f"-> {'PASS' if c2-best_single>=3 else 'FAIL'}")
    L(f"H4 (host peak RSS <= 6 GB, generator-free):  {results['_meta']['peak_rss_mb_host']:.0f} MB "
      f"-> {'PASS' if results['_meta']['peak_rss_mb_host']<=6144 else 'FAIL'} (INFERRED; device pending)")
    L(f"\nladder (hard-mean span-F1):  B1={results['B1']['hard_mean_f1']}  C1={results['C1']['hard_mean_f1']}  "
      f"C2={c2}  C2p(030 pool=2)={results['C2p']['hard_mean_f1']}")
    L(f"recall@3 coverage (hard-mean): B1={results['B1']['recall3_hard_mean']}  C1={results['C1']['recall3_hard_mean']}  "
      f"C2={results['C2']['recall3_hard_mean']}  C2p={results['C2p']['recall3_hard_mean']}")
    if args.b0:
        L(f"production B0 (raw+top3+Qwen generate): hard-mean {results['B0']['hard_mean_f1']}  "
          f"(C2 - B0 = {c2-results['B0']['hard_mean_f1']:+.1f})")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
