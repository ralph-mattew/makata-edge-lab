#!/usr/bin/env python3
"""PoC 034 — Qwen entailment self-check gate for absent clauses (OP-7).

Two-stage prompt: Stage 1 asks Qwen a binary "does the top retrieved chunk explicitly contain a
[CATEGORY] clause? YES/NO"; Stage 2 answers only if YES, else abstains. Tests whether this raises
Correct Abstention Rate on absent hard clauses vs the single-step baseline (PoC-026, 86.3% CAR),
without wrongly gating out answerable items (hard-cat retrieval is weak, so the top-1 chunk may not
"contain" the clause even when answerable — the key risk).

Absent: PoC-008 answerable=False hard-cat (embed questions fresh for retrieval). Answerable: PoC-007
hard-cat (committed query vectors). Servers: Qwen :8091 (gate + answer), EmbeddingGemma :8090 (absent
question embeddings). Run: python3 entailment-selfcheck.py
"""
from __future__ import annotations
import argparse, json, math, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P008 = HERE.parent / "008-absence-instruction-doc-qa" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
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


def is_refusal(ans): return bool(REFUSAL.search(ans)) or not ans.strip()
def gate_no(ans): return ans.strip().upper().startswith("N")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3); args = ap.parse_args()

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
    print(f"absent {len(absent)}  answerable {len(answ)}  (Qwen gate + answer)")
    abs_q = embed(args.emb_url, [it["question"] for it in absent])

    def run(it, qv):
        idxs = by_contract[it["contract"]]
        top = top_chunks(qv, terms(it["question"]), idxs)
        ctx = "\n\n".join(rows[j]["chunk"] for j in top)
        base = qwen(args.qwen_url, ANSWER_PROMPT.format(ctx=ctx[:6000], q=it["question"]))
        gate = qwen(args.qwen_url, GATE_PROMPT.format(cat=it["category"], ctx=rows[top[0]]["chunk"][:3000]))
        return base, gate

    # absent: correct behaviour = abstain
    abs_base_car = abs_gate_car = 0
    for it, qv in zip(absent, abs_q):
        base, gate = run(it, qv)
        abs_base_car += is_refusal(base)                      # single-step CAR (PoC-026 style)
        abs_gate_car += (gate_no(gate) or is_refusal(base))   # self-check: abstain if gate=NO OR base refuses
    na = len(absent)
    # answerable: correct behaviour = answer (not abstain). gate=NO wrongly abstains.
    ans_base_abst = ans_gate_abst = 0
    for it in answ:
        base, gate = run(it, qv007[it["qa_id"]])
        ans_base_abst += is_refusal(base)
        ans_gate_abst += (gate_no(gate) or is_refusal(base))
    nn = len(answ)

    base_car = 100 * abs_base_car / na; gate_car = 100 * abs_gate_car / na
    base_ans_loss = 100 * ans_base_abst / nn; gate_ans_loss = 100 * ans_gate_abst / nn
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"n_absent": na, "n_answerable": nn,
           "absent_CAR_baseline": base_car, "absent_CAR_selfcheck": gate_car, "CAR_gain": gate_car - base_car,
           "answerable_abstain_baseline": base_ans_loss, "answerable_abstain_selfcheck": gate_ans_loss,
           "answerable_recall_loss": gate_ans_loss - base_ans_loss}
    (OUT / "entailment-selfcheck.json").write_text(json.dumps(res, indent=2))
    print(f"\nabsent CAR:      baseline {base_car:.1f}%  ->  self-check {gate_car:.1f}%   (Δ {gate_car-base_car:+.1f}pp)  [H1 >=+10]")
    print(f"answerable abstain(=loss): baseline {base_ans_loss:.1f}%  ->  self-check {gate_ans_loss:.1f}%   (Δ {gate_ans_loss-base_ans_loss:+.1f}pp)  [H2 <=3pp]")
    h1 = (gate_car - base_car) >= 10; h2 = (gate_ans_loss - base_ans_loss) <= 3
    print(f"\n-> {'ADOPT' if h1 and h2 else ('REJECT' if (gate_car-base_car) < 5 else 'INCONCLUSIVE')}  (H1 {h1}, H2 {h2})")


if __name__ == "__main__":
    main()
