#!/usr/bin/env python3
"""PoC 041 — calibrated entailment gate for absent clauses (OP-7/OP-4).

Forks PoC-034: same data, retrieval, absent/answerable framing, and refusal detection. The ONLY change
is the gate: instead of a binary YES/NO string, read Qwen's first-token P(YES) (from logprobs) on the
top-1 chunk and sweep a threshold tau. This traces the whole CAR-gain vs answerable-loss curve and asks
the question 034's single binary point could not: is there a tau with absent CAR +>=5pp at <=3pp
answerable-recall loss?

Absent: PoC-008 answerable=False hard-cat (questions embedded fresh). Answerable: PoC-007 hard-cat
(committed query vectors). Servers: Qwen :8091 (gate logprobs + base answer), EmbeddingGemma :8090.
Run: LAB_POC_ROOT=/path/to/clone/poc python3 calibrated-gate.py
"""
from __future__ import annotations
import argparse, json, math, os, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Gitignored committed vectors live in the lab clone's working tree; default to the sibling poc/ dir and
# allow LAB_POC_ROOT to point at the clone's poc/ dir when running from a detached worktree.
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P008 = _base / "008-absence-instruction-doc-qa" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
QRY_PREFIX = "task: search result | query: {t}"

REFUSAL = re.compile(r"\b(not stated|not specified|not mentioned|not provided|not found|does not "
                     r"(?:contain|mention|specify)|no (?:information|mention|such)|cannot|could not find|"
                     r"unable to|n/?a)\b", re.I)
ANSWER_PROMPT = ("Answer the question using ONLY the contract sections below. Be concise. If it is not "
                 "in the sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")
GATE_PROMPT = ("Does the following contract passage explicitly contain a {cat} clause? "
               "Answer YES or NO only.\n\nPASSAGE:\n{ctx}\n\nANSWER (YES/NO):")


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


def qwen(url, prompt, n=64):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "n_predict": n,
                       "temperature": 0.0, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception:
            time.sleep(1.0 * (a + 1))
    return ""


def qwen_pyes(url, prompt):
    """Calibrated gate score: normalised P(YES) from the first-token logprobs."""
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "max_tokens": 1,
                       "temperature": 0.0, "logprobs": True, "top_logprobs": 20, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]
            lp = (d.get("logprobs") or {}).get("content") or []
            yes = no = 0.0
            if lp:
                for t in lp[0].get("top_logprobs", []):
                    tok = t["token"].strip().lower(); p = math.exp(t["logprob"])
                    if tok.startswith("y"): yes += p
                    elif tok.startswith("n"): no += p
            if yes + no > 0:
                return yes / (yes + no)
            return 1.0 if d["message"]["content"].strip().upper().startswith("Y") else 0.0
        except Exception:
            time.sleep(1.0 * (a + 1))
    return 0.5


def is_refusal(ans): return bool(REFUSAL.search(ans)) or not ans.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3); ap.add_argument("--limit", type=int, default=0); args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qv007 = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]

    def top_chunks(qv, qt, idxs):
        sem = [cosine(qv, cvec[i]) for i in idxs]; bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        h = [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]
        order = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
        return [idxs[j] for j in order]

    absent = [json.loads(l) for l in open(P008 / "items.jsonl")
              if not json.loads(l)["answerable"] and json.loads(l)["category"] in HARD
              and json.loads(l)["contract"] in by_contract]
    answ = [it for it in (json.loads(l) for l in open(P007 / "items.jsonl"))
            if it["category"] in HARD and it.get("gold_words") and it["contract"] in by_contract
            and it["qa_id"] in qv007]
    if args.limit:
        absent = absent[:args.limit]; answ = answ[:args.limit]
    print(f"absent {len(absent)}  answerable {len(answ)}  (calibrated gate: P(YES) + tau-sweep)")
    abs_q = embed(args.emb_url, [it["question"] for it in absent])

    def probe(it, qv):
        idxs = by_contract[it["contract"]]
        top = top_chunks(qv, terms(it["question"]), idxs)
        base = qwen(args.qwen_url, ANSWER_PROMPT.format(ctx="\n\n".join(rows[j]["chunk"] for j in top)[:6000], q=it["question"]))
        pyes = qwen_pyes(args.qwen_url, GATE_PROMPT.format(cat=it["category"], ctx=rows[top[0]]["chunk"][:3000]))
        return {"qa_id": it["qa_id"], "category": it["category"], "base_refusal": is_refusal(base), "p_yes": round(pyes, 4)}

    OUT.mkdir(parents=True, exist_ok=True); raw = OUT / "raw"; raw.mkdir(exist_ok=True)
    abs_rec = [probe(it, qv) for it, qv in zip(absent, abs_q)]
    ans_rec = [probe(it, qv007[it["qa_id"]]) for it in answ]
    (raw / "absent-probes.jsonl").write_text("\n".join(json.dumps(r) for r in abs_rec) + "\n")
    (raw / "answerable-probes.jsonl").write_text("\n".join(json.dumps(r) for r in ans_rec) + "\n")
    na, nn = len(abs_rec), len(ans_rec)

    # baseline (no gate): abstain iff base refuses
    base_car = 100 * sum(r["base_refusal"] for r in abs_rec) / na
    base_ans_loss = 100 * sum(r["base_refusal"] for r in ans_rec) / nn  # answerable baseline refusal rate

    def at_tau(tau):
        # gate abstains iff P(YES) < tau OR base refuses
        car = 100 * sum(r["base_refusal"] or r["p_yes"] < tau for r in abs_rec) / na
        ans_abst = 100 * sum(r["base_refusal"] or r["p_yes"] < tau for r in ans_rec) / nn
        return car, ans_abst

    taus = [round(t / 100, 2) for t in range(0, 101, 1)]
    curve = []
    for tau in taus:
        car, ans_abst = at_tau(tau)
        curve.append({"tau": tau, "absent_CAR": round(car, 1), "CAR_gain": round(car - base_car, 1),
                      "answerable_abstain": round(ans_abst, 1), "answerable_recall_loss": round(ans_abst - base_ans_loss, 1)})

    # best feasible operating point: max CAR gain subject to answerable loss <= 3pp
    feasible = [c for c in curve if c["answerable_recall_loss"] <= 3.0]
    best = max(feasible, key=lambda c: c["CAR_gain"]) if feasible else None
    # 034 binary point: decision YES/NO == P(YES) > 0.5  <=> tau = 0.5
    binary = next(c for c in curve if c["tau"] == 0.5)

    h1 = best is not None and best["CAR_gain"] >= 5.0
    h2 = best is not None and best["answerable_recall_loss"] <= 3.0
    # H3: calibrated dominates 034 binary — reach H1&H2 where binary (at its CAR gain) had loss >3
    verdict = ("ADOPT" if (h1 and h2) else
               ("REJECT" if not any(c["CAR_gain"] >= 5.0 and c["answerable_recall_loss"] <= 5.0 for c in curve)
                else "INCONCLUSIVE"))

    res = {"n_absent": na, "n_answerable": nn, "baseline_absent_CAR": round(base_car, 1),
           "baseline_answerable_refusal": round(base_ans_loss, 1),
           "best_feasible_point": best, "binary_034_point": binary, "verdict": verdict,
           "H1_car_gain_ge5": h1, "H2_loss_le3": h2, "curve": curve}
    (OUT / "calibrated-gate.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"baseline absent CAR (base refusal only): {base_car:.1f}%   answerable baseline refusal: {base_ans_loss:.1f}%")
    L(f"\n034 binary point (tau=0.5):  CAR {binary['absent_CAR']:.1f}% (gain {binary['CAR_gain']:+.1f})  "
      f"answerable loss {binary['answerable_recall_loss']:+.1f}pp  [034 ref: +10.9 CAR / +21.7 loss]")
    L("\ncurve (selected tau):")
    for c in curve:
        if c["tau"] in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
            L(f"  tau={c['tau']:.2f}  CAR {c['absent_CAR']:5.1f}% (gain {c['CAR_gain']:+5.1f})  "
              f"answerable loss {c['answerable_recall_loss']:+5.1f}pp")
    if best:
        L(f"\nbest feasible (loss<=3pp): tau={best['tau']:.2f}  CAR gain {best['CAR_gain']:+.1f}pp  "
          f"loss {best['answerable_recall_loss']:+.1f}pp")
    else:
        L("\nno tau achieves answerable loss <= 3pp with any CAR gain")
    L(f"\nH1 (CAR gain >=+5): {h1}   H2 (loss <=3pp): {h2}   ->  {verdict}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
