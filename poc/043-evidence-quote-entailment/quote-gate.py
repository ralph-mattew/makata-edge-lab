#!/usr/bin/env python3
"""PoC 043 — evidence-quote entailment gate for absent clauses (OP-7).

Forks PoC-041/034. The gate asks Qwen to QUOTE the exact sentence proving the clause exists on the top-1
chunk (or write ABSENT), then VERIFIES the quote is actually a substring of the chunk (grounding). Abstain
iff ABSENT/empty OR the quote is not grounded (hallucinated). Tests whether grounding — not calibration
(041) — opens a usable CAR/answerable-loss operating point.

Absent: PoC-008 answerable=False hard-cat. Answerable: PoC-007 hard-cat. Servers: Qwen :8091, EmbeddingGemma
:8090. Run: LAB_POC_ROOT=/path/to/clone/poc python3 quote-gate.py
"""
from __future__ import annotations
import argparse, json, math, os, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
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
QUOTE_PROMPT = ("Quote the exact sentence from the passage that confirms a {cat} clause exists in this "
                "contract. Copy it verbatim. If no such sentence exists, write ABSENT.\n\n"
                "PASSAGE:\n{ctx}\n\nQUOTE:")


def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())
def content(s): return [t for t in terms(s) if len(t) > 2]
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
def nrm(s): return re.sub(r"\s+", " ", s.lower()).strip()


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


def qwen(url, prompt, n=96):
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


def quote_grounded(reply, chunk, min_words=6):
    """Return (abstain, grounded_bool). Abstain if ABSENT/empty or the quote isn't grounded in the chunk.
    Grounding = a contiguous run of >=min_words content-words from the quote appears contiguously in the
    chunk's content-word sequence (robust to whitespace/case/punctuation; still verifies a real quote)."""
    r = reply.strip()
    if not r or re.search(r"\babsent\b", r, re.I):
        return True, False
    q = re.sub(r"^(quote|answer|sentence)\s*[:\-]\s*", "", r.strip().strip('"').strip("'"), flags=re.I)
    qt, ct = content(q), content(chunk)
    if len(qt) < min_words:
        return True, False                      # too short to be a real sentence quote
    cset = " " + " ".join(ct) + " "
    grounded = any((" " + " ".join(qt[i:i + min_words]) + " ") in cset for i in range(0, len(qt) - min_words + 1))
    return (not grounded), grounded             # abstain iff NOT grounded


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
    if args.limit: absent = absent[:args.limit]; answ = answ[:args.limit]
    print(f"absent {len(absent)}  answerable {len(answ)}  (evidence-quote gate + substring grounding)")
    abs_q = embed(args.emb_url, [it["question"] for it in absent])

    def probe(it, qv):
        idxs = by_contract[it["contract"]]; top = top_chunks(qv, terms(it["question"]), idxs)
        base = qwen(args.qwen_url, ANSWER_PROMPT.format(ctx="\n\n".join(rows[j]["chunk"] for j in top)[:6000], q=it["question"]))
        reply = qwen(args.qwen_url, QUOTE_PROMPT.format(cat=it["category"], ctx=rows[top[0]]["chunk"][:3000]))
        gate_abstain, grounded = quote_grounded(reply, rows[top[0]]["chunk"])
        return {"qa_id": it["qa_id"], "category": it["category"], "base_refusal": is_refusal(base),
                "gate_abstain": gate_abstain, "grounded": grounded, "quote": reply[:200]}

    OUT.mkdir(parents=True, exist_ok=True); raw = OUT / "raw"; raw.mkdir(exist_ok=True)
    abs_rec = [probe(it, qv) for it, qv in zip(absent, abs_q)]
    ans_rec = [probe(it, qv007[it["qa_id"]]) for it in answ]
    (raw / "absent-probes.jsonl").write_text("\n".join(json.dumps(r) for r in abs_rec) + "\n")
    (raw / "answerable-probes.jsonl").write_text("\n".join(json.dumps(r) for r in ans_rec) + "\n")
    na, nn = len(abs_rec), len(ans_rec)

    base_car = 100 * sum(r["base_refusal"] for r in abs_rec) / na
    gate_car = 100 * sum(r["base_refusal"] or r["gate_abstain"] for r in abs_rec) / na
    base_loss = 100 * sum(r["base_refusal"] for r in ans_rec) / nn
    gate_loss = 100 * sum(r["base_refusal"] or r["gate_abstain"] for r in ans_rec) / nn
    car_gain = gate_car - base_car; ans_loss = gate_loss - base_loss
    abs_ground_fail = 100 * sum(r["gate_abstain"] and not r["grounded"] for r in abs_rec) / na
    ans_ground_fail = 100 * sum(r["gate_abstain"] and not r["grounded"] for r in ans_rec) / nn

    h1 = car_gain >= 5.0; h2 = ans_loss <= 3.0
    verdict = ("ADOPT" if (h1 and h2) else ("REJECT" if (car_gain < 2.0 or ans_loss > 5.0) else "INCONCLUSIVE"))
    res = {"n_absent": na, "n_answerable": nn, "baseline_absent_CAR": round(base_car, 1),
           "quote_gate_absent_CAR": round(gate_car, 1), "CAR_gain": round(car_gain, 1),
           "baseline_answerable_refusal": round(base_loss, 1), "quote_gate_answerable_refusal": round(gate_loss, 1),
           "answerable_recall_loss": round(ans_loss, 1),
           "absent_gate_abstain_from_quotefail_pp": round(abs_ground_fail, 1),
           "answerable_gate_abstain_from_quotefail_pp": round(ans_ground_fail, 1),
           "H1_car_ge5": h1, "H2_loss_le3": h2, "verdict": verdict,
           "ref_034_binary": {"CAR_gain": 10.9, "loss": 21.7}, "ref_041_calibrated": "frontier dominated; max CAR gain at <=3pp loss = 0.0"}
    (OUT / "quote-gate.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"baseline absent CAR {base_car:.1f}%  answerable baseline refusal {base_loss:.1f}%")
    L(f"quote-gate  absent CAR {gate_car:.1f}% (gain {car_gain:+.1f})  answerable refusal {gate_loss:.1f}% (loss {ans_loss:+.1f}pp)")
    L(f"  gate abstentions from quote-grounding failure: absent {abs_ground_fail:.1f}pp / answerable {ans_ground_fail:.1f}pp")
    L(f"refs: 034 binary +10.9 CAR/+21.7 loss ; 041 calibrated frontier dominated (max CAR gain @<=3pp loss = 0.0)")
    L(f"\nH1 (CAR gain >=+5): {h1}   H2 (loss <=3pp): {h2}   ->  {verdict}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
