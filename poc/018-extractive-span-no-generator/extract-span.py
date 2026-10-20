#!/usr/bin/env python3
"""PoC 018 — generator-free extractive span selection for the hard categories.

Replaces the Qwen2.5-1.5B answer step with a pure extractive step: from the top-3
EmbeddingGemma-retrieved chunks, split into sentences, re-score each sentence against
the (decomposed) query with EmbeddingGemma, and return the highest-cosine sentence (or a
contiguous passage of <= N sentences). Compares span-F1 vs the SAME-retrieval Qwen
constrained-generation arm (the PoC-017 baseline, re-measured here under identical
retrieval for an apples-to-apples delta).

Retrieval is held fixed to PoC-016's decomposed sub-query path for the hard categories
(max-pool hybrid 0.9/0.1 over the template sub-queries), reusing committed vectors — no
re-embedding of the 79k chunk corpus. Only the sentences selected into the span are
embedded live (EmbeddingGemma server, same config as PoC 007/014/016).

Servers:
  # EmbeddingGemma (sentence embeddings + required for the extractive arm):
  llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
    -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
  # Qwen (only for the `generate` comparison arm):
  llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &

Examples:
  python3 extract-span.py --arm extract --window 1       # primary: single best sentence
  python3 extract-span.py --arm extract --window 3       # contiguous passage <= 3 sentences
  python3 extract-span.py --arm generate                 # re-measure the Qwen baseline
  python3 extract-span.py --arm both --window 1          # both, print the delta
"""
from __future__ import annotations
import argparse, json, math, random, re, resource, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
P015 = HERE.parent / "015-query-formulation" / "results" / "raw"
P016 = HERE.parent / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]

DOC_PREFIX = "title: none | text: {t}"  # same doc-side prefix as PoC 014/016 embedding

STOP = set("a an the of to in on for and or is are be as by with at from this that these those "
           "shall will may any such other each party parties agreement contract hereof herein "
           "thereof pursuant section".split())

# ---- retrieval (hybrid 0.9/0.1, decomposed sub-queries for hard cats: PoC 016) ----
def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def toks(s): return re.findall(r"[a-z0-9]+", s.lower())


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


def hybrid_rank(qvec, qterms, idxs, cvec, dterms, sw=0.9):
    sem = [cosine(qvec, cvec[i]) for i in idxs]
    bm = norm01(bm25(qterms, [dterms[i] for i in idxs]))
    return [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]


def decomp_top3(it, idxs, cvec, dterms, subvec, templates, tk=3):
    """PoC-016 decomposed retrieval: max-pool hybrid over the category's sub-queries."""
    subs = templates[it["category"]]
    best = {}
    for k, s in enumerate(subs):
        h = hybrid_rank(subvec[f'{it["qa_id"]}#{k}'], toks(s), idxs, cvec, dterms)
        for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:tk]:
            best[j] = max(best.get(j, -1), h[j])
    return sorted(best, key=lambda j: best[j], reverse=True)[:tk]


# ---- sentence splitting + span assembly ----
def split_sentences(text, min_words=3, max_words=80):
    """Split a chunk into candidate sentences. Contract text is messy; keep this simple and
    deterministic — break on sentence punctuation and newlines, drop tiny fragments, and
    hard-wrap very long runs so one giant 'sentence' can't swallow a whole clause."""
    parts = re.split(r"(?<=[.;:!?])\s+|\n+", text)
    sents = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        w = p.split()
        if len(w) < min_words:
            continue
        for i in range(0, len(w), max_words):
            sents.append(" ".join(w[i:i + max_words]))
    return sents


# ---- scoring ----
def content(s):
    return [t for t in toks(s) if t not in STOP and len(t) > 2]


def span_f1(answer, gold):
    """SQuAD-style token-overlap F1, identical definition to PoC 017."""
    a, g = Counter(content(answer)), Counter(content(gold))
    if not a or not g:
        return 0.0
    overlap = sum((a & g).values())
    prec = overlap / sum(a.values()); rec = overlap / sum(g.values())
    return 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0


def bootstrap_f1(per_contract, n=10000, seed=0):
    random.seed(seed); groups = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for g in (random.choice(groups) for _ in groups) for v in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


# ---- EmbeddingGemma client (sentence embeddings) ----
def embed_batch(url, texts, batch=16):
    out = []
    i = 0
    while i < len(texts):
        chunk = [DOC_PREFIX.format(t=t) for t in texts[i:i + batch]]
        body = json.dumps({"input": chunk}).encode()
        req = urllib.request.Request(url + "/v1/embeddings", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            out.extend(d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"])
            i += batch
        except Exception:
            if batch == 1:
                out.append([0.0] * (len(out[-1]) if out else 768)); i += 1
            else:
                batch = max(1, batch // 2)
    return out


# ---- Qwen client (comparison arm only) — identical prompt/sampling to PoC 017 ----
PROMPT = ("Answer the question using ONLY the contract sections below. Quote the specific "
          "clause text that answers it. If it is not in the sections, say \"not stated\".\n\n"
          "SECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")


def qwen(url, q, ctx, n=160):
    body = json.dumps({"messages": [{"role": "user", "content": PROMPT.format(ctx=ctx[:6000], q=q)}],
                       "n_predict": n, "temperature": 0.1, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception:
            time.sleep(1.0 * (a + 1))
    return ""


def peak_rss_mb():
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return ru / (1024 * 1024) if ru > 1 << 30 else ru / 1024  # macOS=bytes, Linux=KB


def summarize(arm, per_cat, per_contract):
    flat = [v for g in per_cat.values() for v in g]
    mean_f1 = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap_f1(per_contract)
    cats = {c: 100 * sum(v) / len(v) for c, v in per_cat.items() if v}
    hard = [c for c in HARD if c in cats]
    hard_mean = sum(cats[c] for c in hard) / max(len(hard), 1)
    return {"arm": arm, "mean_f1": mean_f1, "ci": [lo, hi], "hard_mean_f1": hard_mean,
            "per_category": cats, "n_items": len(flat)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["extract", "generate", "both"], default="extract")
    ap.add_argument("--window", type=int, default=1, help="contiguous sentences in the span (1 or 3)")
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090")
    ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    # Inputs: hard-category items + the committed retrieval vectors (no re-embedding).
    items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["category"] in HARD]
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    assert len(rows) == len(cvec), f"{len(rows)} rows vs {len(cvec)} page vecs"
    subvec = {d["key"]: d["vec"] for d in map(json.loads, open(P016 / "emb-subqueries.jsonl"))}
    templates = json.loads((P016 / "decomp-templates.json").read_text())

    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [toks(r["chunk"]) for r in rows]

    # Build the work set: items with a gold span, a contract, and full decomposition vectors.
    work = []
    for it in items:
        c = contracts.get(it["contract"]); g = it.get("gold_words")
        idxs = by_contract.get(it["contract"], [])
        if not c or not g or not idxs:
            continue
        if not all(f'{it["qa_id"]}#{k}' in subvec for k in range(len(templates.get(it["category"], [])))):
            continue
        words = (" ".join(c.get("pages", []) or [])).split()
        gold = " ".join(words[g[0]:g[1] + 1])
        if content(gold):
            work.append((it, gold, idxs))
    if args.limit:
        work = work[:args.limit]
    print(f"items: {len(work)} across {len(HARD)} hard categories  (arm={args.arm}, window={args.window})")

    # Precompute retrieved top-3 chunk indices (identical for both arms).
    retrieved = {}
    for it, _, idxs in work:
        top = decomp_top3(it, idxs, cvec, dterms, subvec, templates, args.topk)
        retrieved[it["qa_id"]] = [idxs[j] for j in top]

    results = {}
    OUT.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT / "raw"; raw_dir.mkdir(exist_ok=True)

    # ---- extractive arm ----
    if args.arm in ("extract", "both"):
        # Collect every candidate sentence across all retrieved chunks, embed once.
        sent_by_item = {}
        all_sents = []
        for it, _, _ in work:
            sents = []
            for ci in retrieved[it["qa_id"]]:
                sents.extend(split_sentences(rows[ci]["chunk"]))
            sent_by_item[it["qa_id"]] = sents
            all_sents.extend(sents)
        uniq = list(dict.fromkeys(all_sents))
        print(f"  embedding {len(uniq)} unique candidate sentences via EmbeddingGemma ...")
        vecs = embed_batch(args.emb_url, uniq)
        svec = dict(zip(uniq, vecs))

        per_cat, per_contract = defaultdict(list), defaultdict(list)
        dump = []
        for it, gold, _ in work:
            sents = sent_by_item[it["qa_id"]]
            cat = it["category"]
            subs = [subvec[f'{it["qa_id"]}#{k}'] for k in range(len(templates[cat]))]
            if not sents:
                ans = ""
                best_i = -1
            else:
                scores = [max(cosine(svec[s], q) for q in subs) for s in sents]
                best_i = max(range(len(sents)), key=lambda i: scores[i])
                lo = max(0, best_i - (args.window - 1) // 2)
                hi = min(len(sents), lo + args.window)
                ans = " ".join(sents[lo:hi])
            f1 = span_f1(ans, gold)
            per_cat[cat].append(f1); per_contract[it["contract"]].append(f1)
            dump.append({"qa_id": it["qa_id"], "category": cat, "answer": ans,
                         "gold": gold, "span_f1": round(100 * f1, 2)})
        (raw_dir / f"extract-w{args.window}-answers.jsonl").write_text(
            "\n".join(json.dumps(d) for d in dump) + "\n")
        results["extract"] = summarize(f"extract-w{args.window}", per_cat, per_contract)

    # ---- generation arm (re-measures the PoC-017 baseline under identical retrieval) ----
    if args.arm in ("generate", "both"):
        per_cat, per_contract = defaultdict(list), defaultdict(list)
        dump = []
        for it, gold, _ in work:
            ctx = "\n\n".join(rows[ci]["chunk"] for ci in retrieved[it["qa_id"]])
            ans = qwen(args.qwen_url, it["question"], ctx)
            f1 = span_f1(ans, gold)
            per_cat[it["category"]].append(f1); per_contract[it["contract"]].append(f1)
            dump.append({"qa_id": it["qa_id"], "category": it["category"], "answer": ans,
                         "gold": gold, "span_f1": round(100 * f1, 2)})
        (raw_dir / "generate-answers.jsonl").write_text(
            "\n".join(json.dumps(d) for d in dump) + "\n")
        results["generate"] = summarize("generate", per_cat, per_contract)

    results["_meta"] = {"peak_rss_mb_host": round(peak_rss_mb(), 1),
                        "window": args.window, "topk": args.topk, "n_work": len(work)}
    (OUT / f"span-quality-{args.arm}.json").write_text(json.dumps(results, indent=2))

    for arm in ("extract", "generate"):
        if arm in results:
            r = results[arm]
            print(f"[{r['arm']:12}] span-F1 mean {r['mean_f1']:5.1f} (CI {r['ci'][0]:.1f}-{r['ci'][1]:.1f})  "
                  f"hard-mean {r['hard_mean_f1']:5.1f}")
            for c in HARD:
                if c in r["per_category"]:
                    print(f"               {c:20} {r['per_category'][c]:5.1f}")
    if args.arm == "both":
        d = results["extract"]["hard_mean_f1"] - results["generate"]["hard_mean_f1"]
        print(f"\nΔ hard-mean span-F1 (extract - generate) = {d:+.1f}  "
              f"[adopt >= +4 over 16.1 baseline, reject if < +2]")
    print(f"host peak RSS: {results['_meta']['peak_rss_mb_host']:.0f} MB (INFERRED; device H4 is on-iPhone)")


if __name__ == "__main__":
    main()
