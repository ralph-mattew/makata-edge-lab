#!/usr/bin/env python3
"""PoC 019 — template decomposition + constrained substring extraction.

Combines PoC-016 decomposed retrieval with a constrained answer step: Qwen2.5-1.5B is
prompted to copy a verbatim substring of the retrieved chunks ("Return only the exact
sentence(s)... Do not paraphrase. If none apply, output NONE."), then a post-generation
string-match validator rejects any output that is not a substring of the top-3 chunks and
falls back to the first sentence of the highest-scored chunk. Compares span-F1 on the three
hard categories vs the PoC-017 free-generation baseline run on the SAME retrieved chunks.

Retrieval is held fixed to PoC-016's decomposed sub-query path (max-pool hybrid 0.9/0.1),
reusing committed vectors — no re-embedding. Only the Qwen server is needed (no embedding
server: the answer step is generation + string matching, not sentence embedding).

Server:
  llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &

Examples:
  python3 constrained-extract.py --arm constrained         # constrained + validator
  python3 constrained-extract.py --arm free                # PoC-017 free-generation baseline
  python3 constrained-extract.py --arm both                # both, print the span-F1 delta
"""
from __future__ import annotations
import argparse, json, math, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
P016 = HERE.parent / "016-crossref-decomposition" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]

STOP = set("a an the of to in on for and or is are be as by with at from this that these those "
           "shall will may any such other each party parties agreement contract hereof herein "
           "thereof pursuant section".split())

# ---- retrieval (hybrid 0.9/0.1, PoC-016 decomposed sub-queries for hard cats) ----
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
    subs = templates[it["category"]]
    best = {}
    for k, s in enumerate(subs):
        h = hybrid_rank(subvec[f'{it["qa_id"]}#{k}'], toks(s), idxs, cvec, dterms)
        for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:tk]:
            best[j] = max(best.get(j, -1), h[j])
    return sorted(best, key=lambda j: best[j], reverse=True)[:tk]


# ---- scoring (span-F1, identical definition to PoC 017) ----
def content(s): return [t for t in toks(s) if t not in STOP and len(t) > 2]


def span_f1(answer, gold):
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


# ---- substring validator ----
def _norm(s):
    return re.sub(r"\s+", " ", s.lower()).strip()


def first_sentence(text):
    for p in re.split(r"(?<=[.;:!?])\s+|\n+", text):
        p = p.strip()
        if len(p.split()) >= 3:
            return p
    return text.strip()


def validate(output, chunks):
    """Return (final_answer, accepted). Accept if the (normalized) model output appears as a
    substring of any retrieved chunk. NONE / empty / non-substring -> reject, fall back to the
    first sentence of the highest-scored chunk (chunks are passed highest-first)."""
    out = output.strip()
    if out.upper() == "NONE" or not out:
        return first_sentence(chunks[0]), False
    no = _norm(out)
    if any(no in _norm(c) for c in chunks) and len(no) >= 8:
        return out, True
    return first_sentence(chunks[0]), False


# ---- Qwen client ----
PROMPT_CONSTRAINED = (
    "Return only the exact sentence(s) from the passages below that answer the question. "
    "Do not paraphrase or add words. If no passage answers the question, output NONE.\n\n"
    "PASSAGES:\n{ctx}\n\nQUESTION: {q}\nEXACT SENTENCE(S):")

PROMPT_FREE = (  # PoC-017 free-generation baseline, identical wording
    "Answer the question using ONLY the contract sections below. Quote the specific clause text "
    "that answers it. If it is not in the sections, say \"not stated\".\n\n"
    "SECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")


def qwen(url, prompt, n=160):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}],
                       "n_predict": n, "temperature": 0.0, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception:
            time.sleep(1.0 * (a + 1))
    return ""


def summarize(arm, per_cat, per_contract, extra=None):
    flat = [v for g in per_cat.values() for v in g]
    mean_f1 = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap_f1(per_contract)
    cats = {c: 100 * sum(v) / len(v) for c, v in per_cat.items() if v}
    hard = [c for c in HARD if c in cats]
    hard_mean = sum(cats[c] for c in hard) / max(len(hard), 1)
    out = {"arm": arm, "mean_f1": mean_f1, "ci": [lo, hi], "hard_mean_f1": hard_mean,
           "per_category": cats, "n_items": len(flat)}
    if extra:
        out.update(extra)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["constrained", "free", "both"], default="constrained")
    ap.add_argument("--url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

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
    print(f"items: {len(work)} across {len(HARD)} hard categories  (arm={args.arm})")

    # Retrieval is identical for both arms; chunks passed highest-score-first for the fallback.
    retrieved = {}
    for it, _, idxs in work:
        top = decomp_top3(it, idxs, cvec, dterms, subvec, templates, args.topk)
        retrieved[it["qa_id"]] = [rows[idxs[j]]["chunk"] for j in top]

    results = {}
    OUT.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT / "raw"; raw_dir.mkdir(exist_ok=True)

    if args.arm in ("constrained", "both"):
        per_cat, per_contract = defaultdict(list), defaultdict(list)
        accepted = 0; rejected = 0; dump = []
        for it, gold, _ in work:
            chunks = retrieved[it["qa_id"]]
            raw = qwen(args.url, PROMPT_CONSTRAINED.format(ctx="\n\n".join(chunks)[:6000], q=it["question"]))
            ans, ok = validate(raw, chunks)
            accepted += ok; rejected += (not ok)
            f1 = span_f1(ans, gold)
            per_cat[it["category"]].append(f1); per_contract[it["contract"]].append(f1)
            dump.append({"qa_id": it["qa_id"], "category": it["category"], "raw": raw,
                         "answer": ans, "accepted": ok, "gold": gold, "span_f1": round(100 * f1, 2)})
        (raw_dir / "constrained-answers.jsonl").write_text("\n".join(json.dumps(d) for d in dump) + "\n")
        n = accepted + rejected
        results["constrained"] = summarize("constrained", per_cat, per_contract,
                                            {"validator": {"accepted": accepted, "rejected": rejected,
                                                           "reject_rate": round(100 * rejected / max(n, 1), 1)}})

    if args.arm in ("free", "both"):
        per_cat, per_contract = defaultdict(list), defaultdict(list)
        dump = []
        for it, gold, _ in work:
            chunks = retrieved[it["qa_id"]]
            ans = qwen(args.url, PROMPT_FREE.format(ctx="\n\n".join(chunks)[:6000], q=it["question"]))
            f1 = span_f1(ans, gold)
            per_cat[it["category"]].append(f1); per_contract[it["contract"]].append(f1)
            dump.append({"qa_id": it["qa_id"], "category": it["category"], "answer": ans,
                         "gold": gold, "span_f1": round(100 * f1, 2)})
        (raw_dir / "free-answers.jsonl").write_text("\n".join(json.dumps(d) for d in dump) + "\n")
        results["free"] = summarize("free", per_cat, per_contract)

    results["_meta"] = {"topk": args.topk, "n_work": len(work)}
    (OUT / f"constrained-{args.arm}.json").write_text(json.dumps(results, indent=2))

    for arm in ("constrained", "free"):
        if arm in results:
            r = results[arm]
            tail = f"  validator reject {r['validator']['reject_rate']}%" if "validator" in r else ""
            print(f"[{arm:12}] span-F1 mean {r['mean_f1']:5.1f} (CI {r['ci'][0]:.1f}-{r['ci'][1]:.1f})  "
                  f"hard-mean {r['hard_mean_f1']:5.1f}{tail}")
            for c in HARD:
                if c in r["per_category"]:
                    print(f"               {c:20} {r['per_category'][c]:5.1f}")
    if args.arm == "both":
        d = results["constrained"]["hard_mean_f1"] - results["free"]["hard_mean_f1"]
        print(f"\nΔ hard-mean span-F1 (constrained - free) = {d:+.1f}  "
              f"[adopt >= +5 over 16.1 baseline, reject if < +2]")


if __name__ == "__main__":
    main()
