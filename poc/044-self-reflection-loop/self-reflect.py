#!/usr/bin/env python3
"""PoC 044 — self-reflection / self-critique loop on Qwen generation (OP-7).

Two-pass generation: Pass 1 answers from top-3 chunks; Pass 2 critiques the draft against the same sections
and revises or retracts. Measures (a) key-fact accuracy on the 464 typed-fact items (PoC-042 metric; hard
categories carry no typed key_facts — see README Deviations), (b) CAR on absent hard clauses + answerable
refusal (PoC-041 metric), and (c) per-query latency. Single-pass baseline vs self-reflection, identical
retrieval.

Servers: Qwen :8091 (gen), EmbeddingGemma :8090 (absent-question embeddings). facts.py from PoC-006.
Run: LAB_POC_ROOT=/path/to/clone/poc python3 self-reflect.py
"""
from __future__ import annotations
import argparse, importlib.util, json, math, os, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P008 = _base / "008-absence-instruction-doc-qa" / "results" / "raw"
P009 = _base / "009-retrieval-depth-qwen" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
FACTS_PY = _base / "006-doc-qa-fm-gemma-qwen" / "facts.py"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
QRY_PREFIX = "task: search result | query: {t}"
_spec = importlib.util.spec_from_file_location("facts", FACTS_PY); facts = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(facts)

REFUSAL = re.compile(r"\b(not stated|not specified|not mentioned|not provided|not found|does not "
                     r"(?:contain|mention|specify)|no (?:information|mention|such)|cannot|could not find|"
                     r"unable to|n/?a)\b", re.I)
ANSWER_PROMPT = ("Answer the question using ONLY the contract sections below. Be concise. If it is not "
                 "in the sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")
CRITIQUE_PROMPT = ("Contract sections:\n{ctx}\n\nQuestion: {q}\n\nA draft answer was: \"{draft}\"\n\n"
                   "Review the draft against the sections. If any part is not supported by the sections, "
                   "correct it; if nothing in the sections supports an answer, reply \"not stated\". "
                   "Give ONLY the final answer.\nFINAL ANSWER:")


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
def is_refusal(a): return bool(REFUSAL.search(a)) or not a.strip()
def norm_bool(v): return v if isinstance(v, bool) else (str(v).lower() == "true")


def embed(url, texts, batch=16):
    out, i = [], 0
    while i < len(texts):
        chunk = [QRY_PREFIX.format(t=t) for t in texts[i:i + batch]]
        body = json.dumps({"input": chunk}).encode()
        req = urllib.request.Request(url + "/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
        try:
            out.extend(d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]); i += batch
        except Exception:
            if batch == 1: out.append([0.0] * (len(out[-1]) if out else 768)); i += 1
            else: batch = max(1, batch // 2)
    return out


def qwen(url, prompt, n=160):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "n_predict": n,
                       "temperature": 0.0, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            t0 = time.time(); r = json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
            return r, time.time() - t0
        except Exception:
            time.sleep(1.0 * (a + 1))
    return "", 0.0


def kf_hit(kind, gold, text):
    if not gold: return None
    return bool({tuple(f) for f in gold} & {tuple(f) for f in facts.key_facts(kind, text)})


def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed); groups = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for g in (random.choice(groups) for _ in groups) for v in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3); ap.add_argument("--limit", type=int, default=0); args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qv = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]

    def top(qvec, qt, idxs):
        sem = [cosine(qvec, cvec[i]) for i in idxs]; bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        h = [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]
        return [idxs[j] for j in sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]]

    def gen(it, qvec):
        idxs = by_c[it["contract"]]; ts = top(qvec, terms(it["question"]), idxs)
        ctx = "\n\n".join(rows[j]["chunk"] for j in ts)[:6000]
        draft, t1 = qwen(args.qwen_url, ANSWER_PROMPT.format(ctx=ctx, q=it["question"]))
        final, t2 = qwen(args.qwen_url, CRITIQUE_PROMPT.format(ctx=ctx, q=it["question"], draft=draft[:800]))
        return draft, final, t1, t2

    OUT.mkdir(parents=True, exist_ok=True); raw = OUT / "raw"; raw.mkdir(exist_ok=True)

    # ---- key-fact arm (464 typed-fact answerable items) ----
    kf_items = [it for it in (json.loads(l) for l in open(P009 / "items.jsonl"))
                if it.get("key_facts") and norm_bool(it["answerable"]) and it["contract"] in by_c and it["qa_id"] in qv]
    if args.limit: kf_items = kf_items[:args.limit]
    base_pc, refl_pc = defaultdict(list), defaultdict(list); base_cat, refl_cat = defaultdict(list), defaultdict(list)
    t_base = t_refl = 0.0; kf_dump = []
    for it in kf_items:
        draft, final, t1, t2 = gen(it, qv[it["qa_id"]])
        hb = kf_hit(it["key_fact_kind"], it["key_facts"], draft); hr = kf_hit(it["key_fact_kind"], it["key_facts"], final)
        base_pc[it["contract"]].append(hb); refl_pc[it["contract"]].append(hr)
        base_cat[it["category"]].append(hb); refl_cat[it["category"]].append(hr)
        t_base += t1; t_refl += t1 + t2
        kf_dump.append({"qa_id": it["qa_id"], "cat": it["category"], "base_kf": hb, "refl_kf": hr, "draft": draft[:200], "final": final[:200]})
    (raw / "keyfact.jsonl").write_text("\n".join(json.dumps(d) for d in kf_dump) + "\n")
    def ov(pc): flat = [h for g in pc.values() for h in g]; return 100 * sum(flat) / len(flat)
    kf_base, kf_refl = ov(base_pc), ov(refl_pc)

    # ---- CAR arm (absent + answerable hard) ----
    absent = [json.loads(l) for l in open(P008 / "items.jsonl")
              if not json.loads(l)["answerable"] and json.loads(l)["category"] in HARD and json.loads(l)["contract"] in by_c]
    answ = [it for it in (json.loads(l) for l in open(P007 / "items.jsonl"))
            if it["category"] in HARD and it.get("gold_words") and it["contract"] in by_c and it["qa_id"] in qv]
    if args.limit: absent = absent[:args.limit]; answ = answ[:args.limit]
    abs_q = embed(args.emb_url, [it["question"] for it in absent])
    ab = [gen(it, q) for it, q in zip(absent, abs_q)]
    an = [gen(it, qv[it["qa_id"]]) for it in answ]
    na, nn = len(ab), len(an)
    car_base = 100 * sum(is_refusal(d) for d, f, _, _ in ab) / na
    car_refl = 100 * sum(is_refusal(f) for d, f, _, _ in ab) / na
    loss_base = 100 * sum(is_refusal(d) for d, f, _, _ in an) / nn
    loss_refl = 100 * sum(is_refusal(f) for d, f, _, _ in an) / nn

    kf_delta = round(kf_refl - kf_base, 1); car_delta = round(car_refl - car_base, 1)
    ref_loss = round(loss_refl - loss_base, 1); latx = round(t_refl / t_base, 2) if t_base else 0.0
    h1 = kf_delta >= 3.0; h2 = car_delta >= 2.0; h3 = latx <= 2.0; h4 = ref_loss <= 3.0
    verdict = ("ADOPT" if (h1 and h3 and h4) else ("REJECT" if kf_delta < 1.0 else "INCONCLUSIVE"))
    res = {"n_keyfact": len(kf_items), "key_fact_base": round(kf_base, 1), "key_fact_reflect": round(kf_refl, 1),
           "key_fact_delta": kf_delta, "key_fact_ci_base": [round(x, 1) for x in bootstrap(base_pc)],
           "key_fact_ci_reflect": [round(x, 1) for x in bootstrap(refl_pc)],
           "per_category_delta": {c: round(100*sum(refl_cat[c])/len(refl_cat[c]) - 100*sum(base_cat[c])/len(base_cat[c]), 1) for c in base_cat},
           "n_absent": na, "CAR_base": round(car_base, 1), "CAR_reflect": round(car_refl, 1), "CAR_delta": car_delta,
           "n_answerable": nn, "answerable_refusal_base": round(loss_base, 1), "answerable_refusal_reflect": round(loss_refl, 1),
           "answerable_refusal_delta": ref_loss, "latency_multiplier": latx,
           "H1_keyfact_ge3": h1, "H2_car_ge2": h2, "H3_latency_le2x": h3, "H4_refusal_le3": h4, "verdict": verdict}
    (OUT / "self-reflect.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"key-fact (464 typed-fact): base {kf_base:.1f}% -> reflect {kf_refl:.1f}%  (Δ {kf_delta:+.1f}pp)  [H1 >=+3 -> {h1}]")
    L(f"absent CAR (hard):         base {car_base:.1f}% -> reflect {car_refl:.1f}%  (Δ {car_delta:+.1f}pp)  [H2 >=+2 -> {h2}]")
    L(f"answerable refusal (hard): base {loss_base:.1f}% -> reflect {loss_refl:.1f}%  (Δ {ref_loss:+.1f}pp)  [H4 <=+3 -> {h4}]")
    L(f"latency multiplier: {latx}x  [H3 <=2x -> {h3}]")
    L(f"per fact-category key-fact Δ: " + ", ".join(f"{c} {d:+.1f}" for c, d in res['per_category_delta'].items()))
    L(f"\n-> {verdict}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
