#!/usr/bin/env python3
"""PoC 017 — span-level answer quality (SQuAD-style F1) on the non-fact hard categories.

Same retrieval + Qwen path as PoC 015 Arm B (keyfact.py); the scorer is span-F1 vs the gold
answer span instead of facts.py (which can't score key_fact=None categories like Exclusivity).
Compares `raw` vs `keywords`. Only the raw->keywords DELTA is interpreted (absolute F1 is low
for long clause answers — see README Metric).

Qwen server: llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
"""
from __future__ import annotations
import argparse, json, math, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P006 = HERE.parent / "006-doc-qa-fm-gemma-qwen"
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
P015 = HERE.parent / "015-query-formulation" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]

STOP = set("a an the of to in on for and or is are be as by with at from this that these those "
           "shall will may any such other each party parties agreement contract hereof herein "
           "thereof pursuant section". split())

# --- retrieval (hybrid 0.9/0.1, identical to PoC 015) ---
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
def rank(qvec, qt, idxs, cvec, dterms, sw=0.9):
    sem = [cosine(qvec, cvec[i]) for i in idxs]
    bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
    return [sw * s + (1 - sw) * x for s, x in zip(sem, bm)]

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


def content(s):
    return [t for t in toks(s) if t not in STOP and len(t) > 2]


def span_f1(answer, gold):
    a, g = Counter(content(answer)), Counter(content(gold))
    if not a or not g:
        return 0.0, 0.0, 0.0, 0.0
    overlap = sum((a & g).values())
    prec = overlap / sum(a.values()); rec = overlap / sum(g.values())
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    contain = overlap / sum(g.values())  # share of gold content present in answer
    return prec, rec, f1, contain


def bootstrap_f1(per_contract, n=10000, seed=0):
    random.seed(seed); groups = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for g in (random.choice(groups) for _ in groups) for v in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", nargs="+", default=["raw", "keywords"])
    ap.add_argument("--url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    items = [json.loads(l) for l in open(P007 / "items.jsonl") if json.loads(l)["category"] in HARD]
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qraw = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    vvec = {d["key"]: d["vec"] for d in map(json.loads, open(P015 / "emb-queryvariants.jsonl"))}
    variants = json.loads((P015 / "query-variants.json").read_text())
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [toks(r["chunk"]) for r in rows]

    work = []
    for it in items:
        c = contracts.get(it["contract"]); g = it.get("gold_words")
        if not c or not g or it["qa_id"] not in qraw:
            continue
        words = (" ".join(c.get("pages", []) or [])).split()
        gold = " ".join(words[g[0]:g[1] + 1])
        if content(gold):
            work.append((it, gold))
    if args.limit:
        work = work[:args.limit]
    print(f"items: {len(work)} across {len(HARD)} hard categories")

    results = {}
    for cond in args.conds:
        per_cat = defaultdict(list); per_contract = defaultdict(list)
        for it, gold in work:
            cat = it["category"]; idxs = by_contract[it["contract"]]
            if cond == "raw":
                h = rank(qraw[it["qa_id"]], toks(it["question"]), idxs, cvec, dterms)
            else:
                h = rank(vvec[f"{cat}::keywords"], toks(variants[cat]["keywords"]), idxs, cvec, dterms)
            top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
            ans = qwen(args.url, it["question"], "\n\n".join(rows[idxs[j]]["chunk"] for j in top))
            _, _, f1, _ = span_f1(ans, gold)
            per_cat[cat].append(f1); per_contract[it["contract"]].append(f1)
        flat = [v for g in per_cat.values() for v in g]
        mean_f1 = 100 * sum(flat) / len(flat) if flat else 0.0
        lo, hi = bootstrap_f1(per_contract)
        hard_cats = [c for c in HARD if per_cat.get(c)]
        hard_mean = sum(100 * sum(per_cat[c]) / len(per_cat[c]) for c in hard_cats) / max(len(hard_cats), 1)
        results[cond] = {"mean_f1": mean_f1, "ci": [lo, hi], "hard_mean_f1": hard_mean,
                         "per_category": {c: 100 * sum(v) / len(v) for c, v in per_cat.items()}}
        print(f"[{cond}] span-F1 mean = {mean_f1:.1f} (CI {lo:.1f}-{hi:.1f}), hard-mean {hard_mean:.1f}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "span-quality.json").write_text(json.dumps(results, indent=2))
    if len(args.conds) == 2:
        a, b = args.conds
        print(f"\nΔ span-F1 ({b}-{a}) hard-mean = {results[b]['hard_mean_f1']-results[a]['hard_mean_f1']:+.1f}")
        for c in HARD:
            ra = results[a]["per_category"].get(c, 0); rb = results[b]["per_category"].get(c, 0)
            print(f"  {c:20} {ra:5.1f} -> {rb:5.1f}  ({rb-ra:+.1f})")


if __name__ == "__main__":
    main()
