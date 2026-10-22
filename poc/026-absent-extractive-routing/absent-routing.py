#!/usr/bin/env python3
"""PoC 026 — cosine-gated abstention for absent hard-category clauses vs the Qwen stack (OP-4).

Targeted follow-up to PoC-021: on the HARD categories only (Exclusivity, Non-Compete,
Change-of-Control), does a cosine-threshold abstention gate (max top-1 semantic cosine < τ →
abstain) give a higher Correct Abstention Rate (CAR) on absent-clause items than the current
hybrid+Qwen stack's own abstention — without regressing answerable hard-category recall@3 > 2pp?

Arms (hard-category items only):
  - Qwen baseline CAR: run Qwen2.5-1.5B on hybrid top-3 context for each ABSENT item; CAR = share it
    declines (refusal/"not stated", frozen regex from PoC-020).
  - Gate CAR(τ): share of ABSENT items with top-1 semantic cosine < τ.
  - answerable regression(τ): share of ANSWERABLE hard items wrongly gated out (cosine < τ AND the
    hybrid top-3 would have covered the gold) — the recall@3 lost to over-abstention.

Absent items: PoC-008 answerable=False, hard categories. Answerable items: PoC-007, hard categories
(committed query vectors). Calibration = seeded 50% of absent items; pick τ maximising held-out CAR
subject to answerable regression ≤ 2pp; compare to the Qwen baseline on the held-out absent split.

Servers: EmbeddingGemma (:8090, absent-item question embeddings) + Qwen (:8091, baseline CAR).
Run: python3 absent-routing.py
"""
from __future__ import annotations
import argparse, json, math, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P006 = HERE.parent / "006-doc-qa-fm-gemma-qwen"
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P008 = HERE.parent / "008-absence-instruction-doc-qa" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = {"Exclusivity", "Non-Compete", "Change Of Control"}
TAUS = [0.30, 0.35, 0.40, 0.45, 0.50]
QRY_PREFIX = "task: search result | query: {t}"

REFUSAL = re.compile(
    r"\b(not stated|not specified|not mentioned|not provided|not found|does not (?:contain|mention|specify)|"
    r"no (?:information|mention|such)|cannot (?:find|determine|be determined|provide|answer)|"
    r"could not find|unable to|i(?:'m| am)? not able|as an ai|i am not a lawyer|"
    r"consult (?:a|an|your)|i apologize|unfortunately|insufficient (?:information|context))\b", re.I)

PROMPT = ("Answer the question using ONLY the contract sections below. Be concise. If it is not in "
          "the sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")


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
    if not span or not gold:
        return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def embed_batch(url, texts, batch=16):
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


def qwen(url, q, ctx, n=80):
    body = json.dumps({"messages": [{"role": "user", "content": PROMPT.format(ctx=ctx[:6000], q=q)}],
                       "n_predict": n, "temperature": 0.0, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception:
            time.sleep(1.0 * (a + 1))
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090")
    ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    def top1_cos(qv, idxs): return max((cosine(qv, cvec[i]) for i in idxs), default=-1.0)
    def hybrid_top(qv, qt, idxs, k):
        sem = [cosine(qv, cvec[i]) for i in idxs]
        bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        h = [0.9 * s + 0.1 * b for s, b in zip(sem, bm)]
        return sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:k]

    # ABSENT hard-category items (PoC-008), embed questions fresh
    absent = [json.loads(l) for l in open(P008 / "items.jsonl")
              if not json.loads(l)["answerable"] and json.loads(l)["category"] in HARD
              and json.loads(l)["contract"] in by_contract]
    print(f"embedding {len(absent)} absent hard-cat questions ...")
    av = embed_batch(args.emb_url, [it["question"] for it in absent])
    for it, v in zip(absent, av):
        it["_cos"] = top1_cos(v, by_contract[it["contract"]])
        it["_ctx"] = "\n\n".join(rows[by_contract[it["contract"]][j]]["chunk"]
                                 for j in hybrid_top(v, terms(it["question"]), by_contract[it["contract"]], args.topk))

    # ANSWERABLE hard-category items (PoC-007) for the regression constraint — committed query vecs
    qv007 = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    answerable = []
    for it in (json.loads(l) for l in open(P007 / "items.jsonl")):
        if it["category"] not in HARD or not it.get("gold_words") or it["contract"] not in by_contract \
           or it["qa_id"] not in qv007:
            continue
        idxs = by_contract[it["contract"]]; qv = qv007[it["qa_id"]]
        top = hybrid_top(qv, terms(it["question"]), idxs, args.topk)
        answerable.append({"cos": top1_cos(qv, idxs),
                           "covered": any(covers(spans[idxs[j]], tuple(it["gold_words"])) for j in top)})
    base_recall = 100 * sum(a["covered"] for a in answerable) / len(answerable)

    # Qwen baseline CAR on absent items
    print(f"running Qwen on {len(absent)} absent items ...")
    for it in absent:
        ans = qwen(args.qwen_url, it["question"], it["_ctx"])
        it["_qwen_abstain"] = bool(REFUSAL.search(ans)) or not ans

    # 50/50 split of absent items; calibrate tau on the calib half
    rng = random.Random(args.seed); order = list(range(len(absent))); rng.shuffle(order)
    half = len(order) // 2
    calib = [absent[i] for i in order[:half]]; held = [absent[i] for i in order[half:]]

    def gate_car(items, tau): return 100 * sum(it["_cos"] < tau for it in items) / len(items) if items else 0.0
    def answ_regression(tau):  # recall@3 lost to over-abstention on answerable hard items
        lost = sum(1 for a in answerable if a["covered"] and a["cos"] < tau)
        return 100 * lost / len(answerable)

    # pick tau: maximise calib CAR subject to answerable regression <= 2pp
    feasible = [t for t in TAUS if answ_regression(t) <= 2.0]
    tau_star = max(feasible, key=lambda t: gate_car(calib, t)) if feasible else min(TAUS)

    qwen_car_held = 100 * sum(it["_qwen_abstain"] for it in held) / len(held)
    gate_car_held = gate_car(held, tau_star)
    sweep = {t: {"gate_car_held": gate_car(held, t), "answ_regression": answ_regression(t)} for t in TAUS}

    OUT.mkdir(parents=True, exist_ok=True)
    res = {"n_absent": len(absent), "n_answerable": len(answerable), "base_recall": base_recall,
           "tau_star": tau_star, "tau_feasible_le2pp": feasible,
           "qwen_car_held": qwen_car_held, "gate_car_held": gate_car_held,
           "car_delta": gate_car_held - qwen_car_held,
           "answ_regression_at_tau_star": answ_regression(tau_star), "sweep": sweep}
    (OUT / "absent-routing.json").write_text(json.dumps(res, indent=2))

    print(f"\nabsent hard-cat items: {len(absent)}  (calib {len(calib)} / held {len(held)})")
    print(f"answerable hard-cat items: {len(answerable)}  baseline recall@3 {base_recall:.1f}%\n")
    print(f"{'tau':>5} {'gate_CAR(held)':>14} {'answ_regression':>16}")
    for t in TAUS:
        print(f"{t:>5.2f} {sweep[t]['gate_car_held']:>13.1f}% {sweep[t]['answ_regression']:>15.1f}pp")
    print(f"\nQwen baseline CAR (held) = {qwen_car_held:.1f}%")
    print(f"chosen tau* = {tau_star} (feasible @<=2pp regression: {feasible})")
    print(f"gate CAR (held) @tau* = {gate_car_held:.1f}%   ->  Δ vs Qwen = {gate_car_held-qwen_car_held:+.1f}pp")
    print(f"answerable regression @tau* = {answ_regression(tau_star):.1f}pp")
    print("Decision: adopt if Δ>=+10 AND regression<=2; reject if Δ<+5; else inconclusive.")


if __name__ == "__main__":
    main()
