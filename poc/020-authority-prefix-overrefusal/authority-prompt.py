#!/usr/bin/env python3
"""PoC 020 — does the authority-framing system prompt cause over-refusal?

Three system-prompt variants, identical user turn and identical retrieval, over the full CUAD
answerable set:
  A (authority)  : "You are a legal expert ..." — the production authority framing
  B (plain)      : no system message at all
  C (task-only)  : neutral task instruction, no legal framing

For each item: EmbeddingGemma hybrid 0.9/0.1 retrieval (raw query, top-3, committed vectors —
no re-embedding) → Qwen2.5-1.5B with each system prompt. Measures key-fact accuracy (PoC-006
facts.py, on the date/duration/jurisdiction categories), refusal/hedge rate (on every
answerable item — a refusal or "not stated" IS a miss here), and recall@3 (retrieval is
identical across variants → computed once). Everything stratified by category, with the
PoC-013 hard categories called out.

Server:
  llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &

Examples:
  python3 authority-prompt.py                       # all three variants, full set
  python3 authority-prompt.py --variants A B         # subset
  python3 authority-prompt.py --limit 200            # quick smoke run
"""
from __future__ import annotations
import argparse, json, math, re, sys, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P006 = HERE.parent / "006-doc-qa-fm-gemma-qwen"
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
sys.path.insert(0, str(P006))
import facts  # PoC-006 key-fact extractor/scorer

HARD = {"Exclusivity", "Non-Compete", "Change Of Control"}  # PoC-013 hard categories

# System-prompt variants. The user turn is byte-identical across all three, so only the
# authority framing varies. Variant A represents Xylo's production legal-expert framing —
# reconcile its exact wording with the app's system prompt on promotion to a verdict.
SYSTEM = {
    "A": "You are a legal expert specializing in contract analysis. Carefully review the "
         "contract excerpts and provide a precise, authoritative legal answer.",
    "B": None,  # plain: no system message
    "C": "Answer the question using the provided text.",
}

USER = ("Answer the question using ONLY the contract sections below. Be concise — give just the "
        "specific fact (a date, a duration, or a jurisdiction). If it is not in the sections, say "
        "\"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")

# Over-refusal / hedge markers. On the answerable CUAD set, any of these signals a non-answer.
REFUSAL = re.compile(
    r"\b(not stated|not specified|not mentioned|not provided|not found|does not (?:contain|mention|specify)|"
    r"no (?:information|mention|such)|cannot (?:find|determine|be determined|provide|answer)|"
    r"could not find|unable to|i(?:'m| am)? not able|as an ai|i am not a lawyer|"
    r"consult (?:a|an|your)|i apologize|unfortunately|insufficient (?:information|context))\b", re.I)


# --- retrieval (hybrid 0.9/0.1, raw query) ---
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


def covers(span, gold, frac=0.5):
    if not span or not gold:
        return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def qwen(url, system, user, n=80):
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": user}]
    body = json.dumps({"messages": msgs, "n_predict": n, "temperature": 0.0,
                       "cache_prompt": True}).encode()
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
    ap.add_argument("--variants", nargs="+", default=["A", "B", "C"], choices=["A", "B", "C"])
    ap.add_argument("--url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    kind_by_cat = {q["category"]: q["key_fact"] for q in json.load(open(P006 / "questions.json"))
                   if q["key_fact"]}
    items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    # Build work set + retrieve once (identical across variants). Record gold facts where scorable.
    work = []  # (item, ctx, gold_facts_or_None, recall_hit)
    for it in items:
        idxs = by_contract.get(it["contract"]); c = contracts.get(it["contract"])
        if not idxs or not c or it["qa_id"] not in qvec:
            continue
        h = rank(qvec[it["qa_id"]], terms(it["question"]), idxs, cvec, dterms)
        top = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
        ctx = "\n\n".join(rows[idxs[j]]["chunk"] for j in top)
        gold = tuple(it["gold_words"]) if it.get("gold_words") else None
        recall_hit = any(covers(spans[idxs[j]], gold) for j in top)
        gfacts = None
        if it["category"] in kind_by_cat and gold:
            words = (" ".join(c.get("pages", []) or [])).split()
            gf = facts.key_facts(kind_by_cat[it["category"]], " ".join(words[gold[0]:gold[1] + 1]))
            gfacts = {tuple(f) for f in gf} if gf else None
        work.append((it, ctx, gfacts, recall_hit))
    if args.limit:
        work = work[:args.limit]

    n_scorable = sum(1 for _, _, gf, _ in work if gf)
    recall = 100 * sum(1 for _, _, _, hit in work if hit) / max(len(work), 1)
    print(f"items: {len(work)}  (key-fact scorable: {n_scorable})  recall@{args.topk} = {recall:.1f}% "
          f"(identical across variants)")

    OUT.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT / "raw"; raw_dir.mkdir(exist_ok=True)
    results = {"_meta": {"n_items": len(work), "n_scorable": n_scorable,
                         "recall_at_k": round(recall, 1), "topk": args.topk}}

    for V in args.variants:
        kf_hit = defaultdict(int); kf_n = defaultdict(int)
        refuse = defaultdict(int); refuse_n = defaultdict(int)
        dump = []
        for it, ctx, gfacts, _ in work:
            cat = it["category"]
            ans = qwen(args.url, SYSTEM[V], USER.format(ctx=ctx[:6000], q=it["question"]))
            refused = bool(REFUSAL.search(ans)) or not ans
            refuse[cat] += refused; refuse_n[cat] += 1
            hit = None
            if gfacts is not None:
                afacts = {tuple(f) for f in facts.key_facts(kind_by_cat[cat], ans)}
                hit = bool(afacts & gfacts)
                kf_hit[cat] += hit; kf_n[cat] += 1
            dump.append({"qa_id": it["qa_id"], "category": cat, "answer": ans,
                         "refused": refused, "key_fact_hit": hit})
        (raw_dir / f"variant-{V}-answers.jsonl").write_text("\n".join(json.dumps(d) for d in dump) + "\n")

        kf_acc = 100 * sum(kf_hit.values()) / max(sum(kf_n.values()), 1)
        ref_rate = 100 * sum(refuse.values()) / max(sum(refuse_n.values()), 1)
        hard_ref = 100 * sum(refuse[c] for c in HARD) / max(sum(refuse_n[c] for c in HARD), 1)
        results[V] = {
            "key_fact_accuracy": kf_acc,
            "refusal_rate": ref_rate,
            "hard_cat_refusal_rate": hard_ref,
            "per_category": {c: {"refusal_rate": 100 * refuse[c] / refuse_n[c],
                                 "key_fact_acc": (100 * kf_hit[c] / kf_n[c]) if kf_n[c] else None,
                                 "n": refuse_n[c]}
                             for c in sorted(refuse_n)},
        }
        print(f"[{V}] key-fact acc {kf_acc:5.1f}%  refusal {ref_rate:5.1f}%  "
              f"hard-cat refusal {hard_ref:5.1f}%")

    (OUT / "authority-overrefusal.json").write_text(json.dumps(results, indent=2))

    if "A" in results:
        print("\nΔ vs authority baseline (A):")
        for V in [v for v in args.variants if v != "A"]:
            dk = results[V]["key_fact_accuracy"] - results["A"]["key_fact_accuracy"]
            dr = results[V]["refusal_rate"] - results["A"]["refusal_rate"]
            print(f"  {V}-A: key-fact {dk:+.1f} pts  ·  refusal {dr:+.1f} pts  "
                  f"[adopt {V} if key-fact >= +3 and recall@3 unchanged]")


if __name__ == "__main__":
    main()
