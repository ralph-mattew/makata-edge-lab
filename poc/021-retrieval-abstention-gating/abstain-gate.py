#!/usr/bin/env python3
"""PoC 021 — retrieval-confidence abstention gating for absent clauses (OP-4).

Transfers DeclineCraft's abstention idea to the retrieval layer: use the top-1 RAW semantic
cosine (query vs chunk) as a "is any relevant clause here?" signal. If top-1 cosine < T, abstain
(predict "clause absent") instead of surfacing a chunk. We sweep T and measure, on the same
embedding space:

  - absent items  (PoC-008 `answerable=False`): false-positive rate = fraction with top-1 cos >= T
    (the system wrongly surfaces a clause that does not exist).
  - answerable items (PoC-007, aligned with the PoC-014 chunk spans): gated recall@3 = fraction
    where top-1 cos >= T AND the hybrid top-3 covers >= 50% of the gold span.

Design: answerable recall reuses the committed 007 query vectors + 014 page vectors + spans (the
validated recall path, no re-embedding, no gold-alignment risk). Only the 482 absent-item
questions are embedded fresh via EmbeddingGemma. The gate uses RAW semantic cosine (absolute,
cross-item comparable) — NOT the per-set-normalized hybrid score.

Server (reproduces committed vectors at cosine 1.0 — see repo memory):
  llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
    -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

Run:
  python3 abstain-gate.py
"""
from __future__ import annotations
import argparse, json, math, re, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P008 = HERE.parent / "008-absence-instruction-doc-qa" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"
HARD = {"Exclusivity", "Non-Compete", "Change Of Control"}
THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
QRY_PREFIX = "task: search result | query: {t}"  # same query prefix as PoC 014/016


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
        req = urllib.request.Request(url + "/v1/embeddings", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            out.extend(d["embedding"] for d in json.load(urllib.request.urlopen(req, timeout=600))["data"]); i += batch
        except Exception:
            if batch == 1:
                out.append([0.0] * (len(out[-1]) if out else 768)); i += 1
            else:
                batch = max(1, batch // 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090")
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    assert len(rows) == len(cvec)
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    def top1_cos(qvec, idxs):
        return max((cosine(qvec, cvec[i]) for i in idxs), default=-1.0)

    def hybrid_top(qvec, qt, idxs, k):
        sem = [cosine(qvec, cvec[i]) for i in idxs]
        bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        h = [0.9 * s + 0.1 * b for s, b in zip(sem, bm)]
        return sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:k]

    # --- answerable side: PoC-007 items, committed query vectors (no re-embedding) ---
    ans_items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    qvec007 = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    answerable = []  # (category, top1cos, covered)
    for it in ans_items:
        idxs = by_contract.get(it["contract"]); g = it.get("gold_words")
        if not idxs or it["qa_id"] not in qvec007 or not g:
            continue
        q = qvec007[it["qa_id"]]
        t1 = top1_cos(q, idxs)
        top = hybrid_top(q, terms(it["question"]), idxs, args.topk)
        covered = any(covers(spans[idxs[j]], tuple(g)) for j in top)
        answerable.append((it["category"], t1, covered))

    # --- absent side: PoC-008 answerable=False items, questions embedded fresh ---
    abs_items = [json.loads(l) for l in open(P008 / "items.jsonl") if not json.loads(l)["answerable"]]
    abs_items = [it for it in abs_items if it["contract"] in by_contract]
    print(f"embedding {len(abs_items)} absent-item questions via EmbeddingGemma ...")
    qa = embed_batch(args.emb_url, [it["question"] for it in abs_items])
    absent = []  # (category, top1cos)
    for it, q in zip(abs_items, qa):
        absent.append((it["category"], top1_cos(q, by_contract[it["contract"]])))

    ungated_recall = 100 * sum(c for _, _, c in answerable) / len(answerable)
    fp_at_050 = 100 * sum(t1 >= 0.50 for _, t1 in absent) / len(absent)
    print(f"answerable items: {len(answerable)}  absent items: {len(absent)}")
    print(f"ungated recall@{args.topk} = {ungated_recall:.1f}%   baseline FP(absent, cos>=0.50) = {fp_at_050:.1f}%\n")

    sweep = []
    print(f"{'T':>5} {'FP_absent':>10} {'CAR':>7} {'recall@3':>9} {'rec_drop':>9} {'abst_F1':>8}")
    for T in THRESHOLDS:
        fp = sum(t1 >= T for _, t1 in absent)
        fp_rate = 100 * fp / len(absent)
        car = 100 - fp_rate
        rec = 100 * sum((t1 >= T) and c for _, t1, c in answerable) / len(answerable)
        drop = ungated_recall - rec
        # abstention detection F1 (positive = absent; predicted-abstain = top1 < T)
        tp = sum(t1 < T for _, t1 in absent)
        fp_ab = sum(t1 < T for _, t1, _ in answerable)   # wrongly abstained on an answerable item
        fn = len(absent) - tp
        prec = tp / (tp + fp_ab) if (tp + fp_ab) else 0.0
        reca = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 100 * 2 * prec * reca / (prec + reca) if (prec + reca) else 0.0
        row = {"T": T, "fp_absent": fp_rate, "car": car, "recall_at_k": rec,
               "recall_drop": drop, "abstention_f1": f1}
        sweep.append(row)
        print(f"{T:>5.2f} {fp_rate:>9.1f}% {car:>6.1f}% {rec:>8.1f}% {drop:>+8.1f} {f1:>7.1f}")

    best = max(sweep, key=lambda r: r["abstention_f1"])
    # per-category FP on absent at the best-F1 T, hard categories called out
    percat = defaultdict(lambda: [0, 0])
    for cat, t1 in absent:
        percat[cat][1] += 1; percat[cat][0] += (t1 >= best["T"])
    percat_fp = {c: 100 * n_fp / n for c, (n_fp, n) in sorted(percat.items())}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "abstention-sweep.json").write_text(json.dumps(
        {"_meta": {"n_answerable": len(answerable), "n_absent": len(absent),
                   "ungated_recall_at_k": ungated_recall, "baseline_fp_cos050": fp_at_050,
                   "topk": args.topk},
         "sweep": sweep, "best_f1": best, "per_category_fp_at_best": percat_fp}, indent=2))
    print(f"\nbest abstention-F1 at T={best['T']:.2f}: "
          f"FP {best['fp_absent']:.1f}% (CAR {best['car']:.1f}%), recall {best['recall_at_k']:.1f}% "
          f"(drop {best['recall_drop']:+.1f})")
    print("per-category FP on absent at best T (hard categories *):")
    for c, v in percat_fp.items():
        print(f"  {'*' if c in HARD else ' '} {c:28} {v:5.1f}%")


if __name__ == "__main__":
    main()
