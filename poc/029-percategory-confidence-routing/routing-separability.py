#!/usr/bin/env python3
"""PoC 029 — per-category retrieval-confidence routing: is the top-1 cosine separable (OP-4)?

The whole proposal hinges on H3: do absent vs answerable items have separable top-1 cosine
distributions PER hard category (so a category-specific threshold can route absent items to a
zero-context path)? If the distributions overlap (AUC ~0.5), no threshold — global (PoC-021) or
per-category — can work, and the mechanism is dead regardless of what the zero-context prompt does.

This computes, per hard category: the top-1 semantic cosine for absent items (PoC-008 answerable=False,
questions embedded fresh) and answerable items (PoC-007, committed query vectors); the absent-vs-
answerable separability AUC; the Youden-J cosine threshold; and the resulting CAR (correctly routed
absent) vs answerable recall@3 loss (covered answerable items wrongly routed to zero-context) at that
threshold. No Qwen needed — the decision gate (H3) is purely the cosine separability.

Server: EmbeddingGemma on :8090 (for the 101 absent-item questions).
Run: python3 routing-separability.py
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


def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())


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


def auc(pos, neg):
    """AUC that score ranks pos above neg (Mann-Whitney). pos/neg are score lists."""
    if not pos or not neg:
        return float("nan")
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n: wins += 1
            elif p == n: ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-url", default="http://127.0.0.1:8090")
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]

    def top1(qv, idxs): return max((cosine(qv, cvec[i]) for i in idxs), default=-1.0)
    def covered_top3(qv, it, idxs):
        import math as _m
        sem = [cosine(qv, cvec[i]) for i in idxs]
        top = sorted(range(len(idxs)), key=lambda j: sem[j], reverse=True)[:args.topk]
        return any(covers(spans[idxs[j]], tuple(it["gold_words"])) for j in top)

    # absent hard-cat items (embed questions fresh)
    absent = [json.loads(l) for l in open(P008 / "items.jsonl")
              if not json.loads(l)["answerable"] and json.loads(l)["category"] in HARD
              and json.loads(l)["contract"] in by_contract]
    print(f"embedding {len(absent)} absent hard-cat questions ...")
    av = embed_batch(args.emb_url, [it["question"] for it in absent])
    abs_cos = defaultdict(list)
    for it, v in zip(absent, av):
        abs_cos[it["category"]].append(top1(v, by_contract[it["contract"]]))

    # answerable hard-cat items (committed query vectors); keep (cos, covered)
    qv007 = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    ans = defaultdict(list)
    for it in (json.loads(l) for l in open(P007 / "items.jsonl")):
        if it["category"] not in HARD or not it.get("gold_words") or it["contract"] not in by_contract \
           or it["qa_id"] not in qv007:
            continue
        qv = qv007[it["qa_id"]]; idxs = by_contract[it["contract"]]
        ans[it["category"]].append((top1(qv, idxs), covered_top3(qv, it, idxs)))

    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    print(f"\n{'category':20} {'AUC':>6} {'abs_med':>8} {'ans_med':>8} {'youden_thr':>11} "
          f"{'CAR@thr':>8} {'ans_recall_loss':>16}")
    any_separable = False
    for c in HARD:
        a = sorted(abs_cos.get(c, []))
        anc = ans.get(c, [])
        ans_cos = [x for x, _ in anc]
        # separability: predict "absent" when cosine is LOW -> score = -cosine, positive=absent
        au = auc([-x for x in a], [-x for x in ans_cos])
        # Youden-J over candidate thresholds (route if cosine < thr)
        cand = sorted(set([round(x, 3) for x in (a + ans_cos)]))
        best = None
        for thr in cand:
            tpr = sum(x < thr for x in a) / len(a) if a else 0            # CAR: absent correctly routed
            fpr = sum(x < thr for x in ans_cos) / len(ans_cos) if ans_cos else 0  # answerable wrongly routed
            J = tpr - fpr
            if best is None or J > best[0]:
                best = (J, thr, tpr, fpr)
        J, thr, tpr, fpr = best
        # answerable recall@3 LOSS = covered answerable items that would be routed away (cosine<thr)
        covered = [cos for cos, cov in anc if cov]
        def rloss(t): return 100 * sum(cos < t for cos in covered) / len(anc) if anc else 0.0
        rec_loss = rloss(thr)
        # H2-respecting operating point: highest threshold whose answerable recall loss <= 3pp,
        # and the CAR (absent correctly routed) achievable there.
        thr_h2 = min(cand); car_h2 = 0.0
        for t in cand:
            if rloss(t) <= 3.0:
                thr_h2 = t; car_h2 = 100 * (sum(x < t for x in a) / len(a) if a else 0)
        amed = a[len(a)//2] if a else float("nan"); nmed = sorted(ans_cos)[len(ans_cos)//2] if ans_cos else float("nan")
        any_separable = any_separable or (au > 0.65)
        report[c] = {"auc": au, "absent_median_cos": amed, "answerable_median_cos": nmed,
                     "youden_threshold": thr, "car_at_youden": 100*tpr, "recall_loss_at_youden_pp": rec_loss,
                     "car_at_3pp_recall_cap": car_h2, "n_absent": len(a), "n_answerable": len(anc)}
        print(f"{c:20} {au:6.2f} {amed:8.3f} {nmed:8.3f} {thr:11.3f} {100*tpr:7.1f}% {rec_loss:13.1f}pp   {car_h2:9.1f}%")

    (OUT / "routing-separability.json").write_text(json.dumps(report, indent=2))
    print(f"\nH3 (any hard category with absent/answerable AUC > 0.65): "
          f"{'PASS' if any_separable else 'FAIL'}")
    print("If FAIL, no per-category cosine threshold can separate absent from answerable -> the routing")
    print("mechanism cannot work (confirms PoC-021/026); reject without needing the zero-context Qwen arm.")


if __name__ == "__main__":
    main()
