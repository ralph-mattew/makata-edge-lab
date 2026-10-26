#!/usr/bin/env python3
"""PoC 045 — GreenLeaf-Tiny binary-quantized first-stage index (OP-1/OP-8).

Embeds the committed PoC-014 page chunks + PoC-007 queries with the legal-domain embedder GreenLeaf-Tiny
(HF judicialmind/greenleaf-law-embed-tiny, loaded via transformers AutoModel + mean-pool + L2, MPS),
sign-binarizes the stored chunk vectors, retrieves per-contract top-50 by Hamming, re-ranks by exact float
dot product, takes top-3, and scores recall@3 (top-3 covers >=50% of gold span). Compares to the committed
EmbeddingGemma pure-semantic baseline. Isolates the EMBEDDER lever (vs PoC-035's quantization lever).

Metric matches PoC-007/037. Pure semantic (no BM25), per PoC-035's setup.
Run: LAB_POC_ROOT=/path/to/clone/poc python3 greenleaf-index.py
"""
from __future__ import annotations
import argparse, json, os, time
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
OUT = HERE / "results"; RAW = OUT / "raw"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
MODEL = "judicialmind/greenleaf-law-embed-tiny"
EG_BASELINE_HYBRID = 61.4          # PoC-037 EmbeddingGemma hybrid baseline (reference)
POC035 = "EmbeddingGemma 1-bit + float re-rank: 61.0 recall@3 (−1.6 vs float 62.6)"


def covers(span, gold, frac=0.5):
    if not span or not gold: return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def greenleaf_encoder():
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    mdl = AutoModel.from_pretrained(MODEL, trust_remote_code=True).to("mps").eval()

    def emb(texts, batch=160, max_length=128):
        # length-sorted batching: process similar-length texts together to minimise padding waste,
        # then restore original order. Huge speedup when lengths vary (CUAD page chunks do).
        import time as _t
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = [None] * len(texts); t0 = _t.time()
        for b0 in range(0, len(order), batch):
            idx = order[b0:b0 + batch]
            b = tok([texts[i] for i in idx], padding=True, truncation=True, max_length=max_length, return_tensors="pt").to("mps")
            with torch.no_grad():
                o = mdl(**b)
            h = o.last_hidden_state if hasattr(o, "last_hidden_state") else o[0]
            m = b["attention_mask"].unsqueeze(-1).float()
            v = torch.nn.functional.normalize((h * m).sum(1) / m.sum(1).clamp(min=1e-9), dim=1).cpu().numpy().astype(np.float32)
            for k, i in enumerate(idx):
                out[i] = v[k]
            if (b0 // batch) % 50 == 0:
                done = b0 + len(idx)
                print(f"    embedded {done}/{len(texts)} ({done/(_t.time()-t0+1e-9):.0f}/s)", flush=True)
        return np.asarray(out, dtype=np.float32)
    return emb


def main():
    import random
    ap = argparse.ArgumentParser(); ap.add_argument("--topk", type=int, default=3); ap.add_argument("--pool", type=int, default=50)
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--contracts", type=int, default=160)
    ap.add_argument("--seed", type=int, default=0); args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    egc = np.array([json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")], dtype=np.float32)
    egq = {d["key"]: np.array(d["vec"], dtype=np.float32) for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_c = defaultdict(list)
    for i, r in enumerate(rows): by_c[r["contract"]].append(i)
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]
    items = [json.loads(l) for l in open(P007 / "items.jsonl")
             if json.loads(l).get("gold_words") and json.loads(l)["contract"] in by_c and json.loads(l)["qa_id"] in egq]

    # Stratified contract sample: keep ALL contracts that carry a hard-category item (so H3 is on the full
    # hard set), then top up with random other contracts to reach --contracts. Embedding the full 79k-chunk
    # CUAD corpus with GreenLeaf on MPS is prohibitively slow (~11 docs/s on the long-chunk tail), so we
    # evaluate on a contract sample — a valid recall@3 estimate (see README Deviations).
    random.seed(args.seed)
    hard_contracts = sorted({it["contract"] for it in items if it["category"] in HARD})
    others = sorted(set(by_c) - set(hard_contracts))
    random.shuffle(others)
    keep = set(hard_contracts) | set(others[:max(0, args.contracts - len(hard_contracts))])
    items = [it for it in items if it["contract"] in keep]
    if args.limit: items = items[:args.limit]
    needed = sorted({i for c in keep for i in by_c[c]})
    print(f"sampled contracts {len(keep)}/{len(by_c)} (all {len(hard_contracts)} hard + random)  "
          f"items {len(items)}  chunks-to-embed {len(needed)}/{len(rows)}", flush=True)

    # ---- GreenLeaf embeddings (only sampled contracts' chunks) ----
    enc = greenleaf_encoder()
    dim = 1024
    t0 = time.time(); vecs = enc([rows[i]["chunk"] for i in needed]); print(f"embedded {len(needed)} chunks in {(time.time()-t0)/60:.1f} min", flush=True)
    glc = np.zeros((len(rows), vecs.shape[1]), dtype=np.float32); glc[needed] = vecs
    uniqq = {it["qa_id"]: it["question"] for it in items}
    qv = enc(list(uniqq.values())); glq = {k: qv[i] for i, k in enumerate(uniqq)}
    np.save(RAW / "gl-chunks.npy", glc[needed]); np.savez(RAW / "gl-queries.npz", **glq)
    glc_sign = (glc >= 0)  # bool sign bits

    def recall(score_fn):
        per_cat, allh = defaultdict(list), []
        for it in items:
            idxs = by_c[it["contract"]]; gold = tuple(it["gold_words"])
            top = score_fn(it, idxs)
            hit = any(covers(spans[j], gold) for j in top[:args.topk])
            per_cat[it["category"]].append(hit); allh.append(hit)
        overall = 100 * sum(allh) / len(allh)
        cats = {c: 100 * sum(per_cat[c]) / len(per_cat[c]) for c in HARD if per_cat[c]}
        return round(overall, 1), {c: round(v, 1) for c, v in cats.items()}, round(sum(cats.values()) / len(cats), 1)

    def eg_semantic(it, idxs):
        q = egq[it["qa_id"]]; s = egc[idxs] @ q
        return [idxs[j] for j in np.argsort(-s)[:args.topk]]

    def gl_float(it, idxs):
        q = glq[it["qa_id"]]; s = glc[idxs] @ q
        return [idxs[j] for j in np.argsort(-s)[:args.topk]]

    def gl_binary_rerank(it, idxs):
        q = glq[it["qa_id"]]; qsign = (q >= 0)
        # Hamming similarity (agreeing bits) between query sign and each chunk sign
        agree = (glc_sign[idxs] == qsign).sum(1)
        pool = [idxs[j] for j in np.argsort(-agree)[:args.pool]]       # binary first stage top-50
        s = glc[pool] @ q                                              # exact float re-rank
        return [pool[j] for j in np.argsort(-s)[:args.topk]]

    eg = recall(eg_semantic); glf = recall(gl_float); glb = recall(gl_binary_rerank)

    # index size: 1024 sign bits/chunk vs float32
    n = len(rows); dim = glc.shape[1]
    bin_mb = n * dim / 8 / 1e6; f32_mb = n * dim * 4 / 1e6

    res = {"n_items": len(items), "topk": args.topk, "pool": args.pool, "dim": dim,
           "eg_semantic": {"overall": eg[0], "per_hard": eg[1], "hard_mean": eg[2]},
           "greenleaf_float": {"overall": glf[0], "per_hard": glf[1], "hard_mean": glf[2]},
           "greenleaf_binary_rerank": {"overall": glb[0], "per_hard": glb[1], "hard_mean": glb[2]},
           "index_binary_mb": round(bin_mb, 1), "index_float32_mb": round(f32_mb, 1),
           "eg_hybrid_baseline_ref": EG_BASELINE_HYBRID, "poc035_ref": POC035}
    h1 = glb[0] >= EG_BASELINE_HYBRID
    h2 = bin_mb <= 300
    h3 = (glb[2] - eg[2]) >= 5.0
    res["H1_overall_ge_61_4"] = h1; res["H2_index_le_300mb"] = h2; res["H3_hardmean_ge_plus5"] = h3
    res["delta_hardmean_vs_eg"] = round(glb[2] - eg[2], 1); res["delta_overall_vs_eg"] = round(glb[0] - eg[0], 1)
    res["verdict"] = ("ADOPT" if (h1 and h2 and h3) else
                      ("REJECT" if (glb[0] < eg[0] - 2.0 or not h2) else "INCONCLUSIVE"))
    (OUT / "greenleaf-index.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"recall@3 (pure semantic, {len(items)} items):")
    L(f"  EmbeddingGemma float   overall {eg[0]:.1f}  hard-mean {eg[2]:.1f}  {eg[1]}")
    L(f"  GreenLeaf    float     overall {glf[0]:.1f}  hard-mean {glf[2]:.1f}  {glf[1]}")
    L(f"  GreenLeaf    bin+rerank overall {glb[0]:.1f}  hard-mean {glb[2]:.1f}  {glb[1]}")
    L(f"index size: GreenLeaf binary {bin_mb:.1f} MB (vs float32 {f32_mb:.1f} MB)")
    L(f"refs: EG hybrid baseline {EG_BASELINE_HYBRID}; {POC035}")
    L(f"\nH1 overall>=61.4: {h1} ({glb[0]})   H2 index<=300MB: {h2} ({bin_mb:.0f})   "
      f"H3 hard-mean +>=5: {h3} (Δ {res['delta_hardmean_vs_eg']:+.1f})   -> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
