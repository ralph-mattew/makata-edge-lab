#!/usr/bin/env python3
"""PoC 015 Arm B — end-to-end key-fact accuracy: does the recall@3 gain convert to answers?

For the key-fact-scorable categories (date/duration/jurisdiction — PoC 006 questions.json),
retrieve top-3 with a given query transform, feed the chunks to Qwen2.5-1.5B, and score whether
the answer contains a gold key fact (PoC 006 facts.py). Compares `raw` vs `keywords` (Arm A's
winner). Only items whose GOLD span yields a parsable fact are scorable.

NOTE (scope): the HARD categories (Exclusivity/Non-Compete/Change-of-Control) have key_fact=None
in PoC 006 — they are NOT key-fact-scorable, so Arm B cannot settle them. It settles conversion
on the fact-bearing categories where keywords moved recall most (Agreement Date, Warranty Duration).

Qwen server (chat endpoint):
  llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
"""
from __future__ import annotations
import argparse, json, math, re, sys, time, urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
P006 = HERE.parent / "006-doc-qa-fm-gemma-qwen"
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
RAW = HERE / "results" / "raw"
OUT = HERE / "results"
sys.path.insert(0, str(P006))
import facts  # PoC 006 key-fact extractor/scorer

# --- retrieval (same hybrid 0.9/0.1 as Arm A) ---
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
def rank(qvec, qt, idxs, cvec, dterms, sw=0.9):
    sem = [cosine(qvec, cvec[i]) for i in idxs]
    bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
    return [sw * s + (1 - sw) * x for s, x in zip(sem, bm)]

PROMPT = ("Answer the question using ONLY the contract sections below. Be concise — give just the "
          "specific fact (a date, a duration, or a jurisdiction). If it is not in the sections, say "
          "\"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")

def qwen(url, q, ctx, n=80):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", nargs="+", default=["raw", "keywords"])
    ap.add_argument("--url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="cap scorable items (0=all)")
    args = ap.parse_args()

    kind_by_cat = {q["category"]: q["key_fact"] for q in json.load(open(P006 / "questions.json"))
                   if q["key_fact"]}
    items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["category"] in kind_by_cat]
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qraw = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    vvec = {d["key"]: d["vec"] for d in map(json.loads, open(RAW / "emb-queryvariants.jsonl"))}
    variants = json.loads((RAW / "query-variants.json").read_text())
    from collections import defaultdict
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]

    # gold facts per item (skip items whose gold span yields no parsable fact)
    scorable = []
    for it in items:
        c = contracts.get(it["contract"]);
        if not c or it["qa_id"] not in qraw: continue
        words = (" ".join(c.get("pages", []) or [])).split()
        g = it.get("gold_words")
        if not g: continue
        gtext = " ".join(words[g[0]:g[1] + 1])
        gold = facts.key_facts(kind_by_cat[it["category"]], gtext)
        if gold:
            scorable.append((it, [tuple(f) for f in gold]))
    if args.limit:
        scorable = scorable[:args.limit]
    print(f"scorable key-fact items: {len(scorable)} across {len(kind_by_cat)} categories")

    results = {}
    for cond in args.conds:
        per_cat_hit, per_cat_n = defaultdict(int), defaultdict(int)
        for it, gold in scorable:
            cat = it["category"]; idxs = by_contract[it["contract"]]
            if cond == "raw" or cat not in variants:
                h = rank(qraw[it["qa_id"]], terms(it["question"]), idxs, cvec, dterms)
                top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
            else:  # keywords
                h = rank(vvec[f"{cat}::keywords"], terms(variants[cat]["keywords"]), idxs, cvec, dterms)
                top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
            ctx = "\n\n".join(rows[idxs[j]]["chunk"] for j in top)
            ans = qwen(args.url, it["question"], ctx)
            afacts = {tuple(f) for f in facts.key_facts(kind_by_cat[cat], ans)}
            hit = bool(afacts & set(gold))
            per_cat_hit[cat] += hit; per_cat_n[cat] += 1
        acc = 100 * sum(per_cat_hit.values()) / max(sum(per_cat_n.values()), 1)
        results[cond] = {"accuracy": acc,
                         "per_category": {c: {"acc": 100 * per_cat_hit[c] / per_cat_n[c], "n": per_cat_n[c]}
                                          for c in per_cat_n}}
        print(f"[{cond}] key-fact accuracy = {acc:.1f}% over {sum(per_cat_n.values())} items")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "keyfact-armB.json").write_text(json.dumps(results, indent=2))
    if len(args.conds) == 2:
        a, b = args.conds
        print(f"\nΔ key-fact accuracy ({b} - {a}) = {results[b]['accuracy'] - results[a]['accuracy']:+.1f} pts")
        print(f"{'category':32} {a:>8} {b:>8} {'Δ':>7}")
        for cat in results[a]["per_category"]:
            ra = results[a]["per_category"][cat]["acc"]; rb = results[b]["per_category"][cat]["acc"]
            print(f"{cat:32} {ra:>7.1f}% {rb:>7.1f}% {rb-ra:>+6.1f}")


if __name__ == "__main__":
    main()
