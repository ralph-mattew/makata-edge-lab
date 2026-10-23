#!/usr/bin/env python3
"""PoC 031 — zero-parameter entailment proxy (weakest-link sub-phrase coverage) for absent clauses (OP-7).

PoC-029 showed per-category top-1 cosine separates absent vs answerable (AUC 0.73) but with a thin
ceiling. This tests a stronger *zero-parameter* signal: decompose the question into sub-phrases
(split on AND / OR / comma), embed each with EmbeddingGemma, score the TOP-1 retrieved chunk against
each sub-phrase, and take the MINIMUM sub-phrase cosine (weakest-link JCA coverage) as the abstention
signal. An absent clause should satisfy fewer sub-constraints → lower min → easier to gate out.

Compares, on the same hard-category absent (PoC-008) + answerable (PoC-007) items, the separability
(AUC) and CAR-at-≤3pp-recall of TWO signals:
  - baseline (PoC-029): cosine(full query, top-1 chunk)
  - proxy  (this PoC): min_k cosine(sub-phrase_k, top-1 chunk)

Both score the SAME top-1 retrieved chunk, so the only change is the signal. Committed chunk vectors;
EmbeddingGemma server embeds the query + sub-phrases. Run: python3 entailment-proxy.py
"""
from __future__ import annotations
import argparse, json, math, re, urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P008 = HERE.parent / "008-absence-instruction-doc-qa" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
QRY_PREFIX = "task: search result | query: {t}"


def dot(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())


def covers(span, gold, frac=0.5):
    if not span or not gold:
        return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def subphrases(q):
    """Split a question into sub-constraints on AND / OR / commas / semicolons."""
    parts = re.split(r"\s+(?:and|or)\s+|[,;]", q, flags=re.I)
    out = [p.strip(" .?") for p in parts if len(p.strip().split()) >= 2]
    return out or [q.strip()]


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


def auc(pos, neg):
    if not pos or not neg: return float("nan")
    w = t = 0
    for p in pos:
        for n in neg:
            if p > n: w += 1
            elif p == n: t += 1
    return (w + 0.5 * t) / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--emb-url", default="http://127.0.0.1:8090"); args = ap.parse_args()
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qv007 = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    def top1_idx(qv, idxs):  # top-1 retrieved chunk (by semantic cosine)
        return max(idxs, key=lambda i: dot(qv, cvec[i]))

    # build item lists
    absent = [json.loads(l) for l in open(P008 / "items.jsonl")
              if not json.loads(l)["answerable"] and json.loads(l)["category"] in HARD
              and json.loads(l)["contract"] in by_contract]
    answ = [it for it in (json.loads(l) for l in open(P007 / "items.jsonl"))
            if it["category"] in HARD and it.get("gold_words") and it["contract"] in by_contract
            and it["qa_id"] in qv007]

    # embed absent questions (fresh) + all sub-phrases (fresh)
    print(f"embedding {len(absent)} absent questions + sub-phrases for {len(absent)+len(answ)} items ...")
    abs_q = embed(args.emb_url, [it["question"] for it in absent])
    # sub-phrase embeddings cached by text
    allsubs = sorted({s for it in (absent + answ) for s in subphrases(it["question"])})
    sub_emb = dict(zip(allsubs, embed(args.emb_url, allsubs)))

    def signals(it, qv):
        idxs = by_contract[it["contract"]]
        t1 = top1_idx(qv, idxs); ch = cvec[t1]
        base = dot(qv, ch)                                   # PoC-029 signal
        subs = subphrases(it["question"])
        proxy = min(dot(sub_emb[s], ch) for s in subs)       # weakest-link coverage
        return base, proxy, t1, idxs

    # absent: want LOW signal (predict absent). answerable: compute signal + whether top-3 covers gold.
    abs_base, abs_proxy = defaultdict(list), defaultdict(list)
    for it, qv in zip(absent, abs_q):
        b, p, _, _ = signals(it, qv)
        abs_base[it["category"]].append(b); abs_proxy[it["category"]].append(p)
    ans_base, ans_proxy, ans_cov = defaultdict(list), defaultdict(list), defaultdict(list)
    for it in answ:
        qv = qv007[it["qa_id"]]; b, p, t1, idxs = signals(it, qv)
        sem = sorted(idxs, key=lambda i: dot(qv, cvec[i]), reverse=True)[:3]
        ans_base[it["category"]].append(b); ans_proxy[it["category"]].append(p)
        ans_cov[it["category"]].append(any(covers(spans[j], tuple(it["gold_words"])) for j in sem))

    def analyze(name, absd, ansd):
        rows_out = {}
        for c in HARD:
            a = absd[c]; n = ansd[c]
            au = auc([-x for x in a], [-x for x in n])  # low signal -> absent(positive)
            cand = sorted(set(round(x, 3) for x in a + n))
            # CAR at <=3pp answerable-recall loss: route (abstain) if signal < thr
            covered = [sig for sig, cov in zip(n, ans_cov[c]) if cov]
            best_car = 0.0
            for thr in cand:
                rloss = 100 * sum(s < thr for s in covered) / len(n) if n else 0
                if rloss <= 3.0:
                    best_car = max(best_car, 100 * sum(s < thr for s in a) / len(a) if a else 0)
            rows_out[c] = {"auc": au, "car_at_3pp": best_car}
        return rows_out

    base_r = analyze("base", abs_base, ans_base)
    proxy_r = analyze("proxy", abs_proxy, ans_proxy)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "entailment-proxy.json").write_text(json.dumps({"top1_cosine": base_r, "minsub_proxy": proxy_r}, indent=2))
    print(f"\n{'category':20} {'AUC base':>9} {'AUC proxy':>10}   {'CAR@3pp base':>13} {'CAR@3pp proxy':>14}  {'ΔCAR':>6}")
    dmax = -1e9
    for c in HARD:
        b = base_r[c]; p = proxy_r[c]; d = p["car_at_3pp"] - b["car_at_3pp"]; dmax = max(dmax, d)
        print(f"{c:20} {b['auc']:9.2f} {p['auc']:10.2f}   {b['car_at_3pp']:12.1f}% {p['car_at_3pp']:13.1f}% {d:+6.1f}")
    print(f"\nH1 (min-subphrase CAR +>=8pp over top-1 cosine, at <=3pp recall): best ΔCAR = {dmax:+.1f}pp "
          f"-> {'PASS' if dmax >= 8 else ('REJECT (<+3)' if dmax < 3 else 'INCONCLUSIVE (+3..+8)')}")
    print("Ceiling caveat: PoC-026 measured Qwen already abstains at 86.3% CAR with context; this signal-vs-")
    print("signal CAR is the routable fraction, whose end-to-end value is capped by that ~14% headroom.")


if __name__ == "__main__":
    main()
