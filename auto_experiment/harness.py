#!/usr/bin/env python3
"""Deterministic CUAD recall@3 harness — the TRUSTED CORE of the auto-experiment loop.

Integrity seam
--------------
An auto-generated experiment supplies only a *mechanism* (how to pick top-k candidate
chunks for a query). This module owns everything that decides adopt/reject:

  * the gold spans and the recall definition (top-k covers >=50% of a gold span),
  * the contract-level bootstrap CI,
  * the per-category / hard / weak aggregates,
  * the verdict: a pre-registered `decision.json` applied by a no-eval comparator.

The experiment never scores itself and never writes the verdict. That is what keeps the
lab's ground truth independent even though a model wrote the mechanism. See README.md.

Data (local, gitignored — regenerate via each PoC's embed step; a local job has them):
  items    : poc/007-embedding-retrieval-recall/results/raw/items.jsonl
  chunks   : poc/014-clause-aware-chunking/results/raw/chunks-page.jsonl
  emb-page : poc/014-clause-aware-chunking/results/raw/emb-page.jsonl
  emb-query: poc/014-clause-aware-chunking/results/raw/emb-queries.jsonl

Recall, hybrid weights, and the bootstrap mirror PoC 007/014/015 exactly, so the
built-in hybrid baseline reproduces the known page-chunk number (~61.8%).

Mechanism contract (what an experiment provides)
------------------------------------------------
    topk(ctx, item, idxs, k) -> list[int]      # choose k GLOBAL row indices from idxs
or, more commonly, a per-candidate score:
    candidate_scores(ctx, item, idxs) -> list[float]   # aligned to idxs
wrapped via `evaluate_scores`. `ctx` is the Corpus (chunk text, vectors, query text,
and the shared primitives) so a mechanism can also build its own embeddings.
"""
from __future__ import annotations
import argparse, json, math, random, re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
P007 = LAB / "poc" / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = LAB / "poc" / "014-clause-aware-chunking" / "results" / "raw"

# Category groupings used for pre-registered rules (from PoC 013/015).
HARD = {"Exclusivity", "Non-Compete", "Change Of Control"}
WEAK = {"Exclusivity", "Non-Compete", "Agreement Date", "Warranty Duration",
        "Liquidated Damages", "Cap On Liability"}

# The known page-chunk hybrid baseline this harness must reproduce (PoC 014/016).
RAW_BASELINE_RECALL = 61.8


# --- shared primitives (identical math to PoC 015) ---------------------------------
def cosine(a, b): return sum(x * y for x, y in zip(a, b))
def terms(s): return re.findall(r"[a-z0-9]+", s.lower())


def bm25(qt, docs, k1=1.5, b=0.75):
    N = len(docs); avgdl = sum(len(d) for d in docs) / max(N, 1)
    df = Counter(t for d in docs for t in set(d))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    out = []
    for d in docs:
        c = Counter(d)
        out.append(sum(idf.get(t, 0) * (c[t] * (k1 + 1)) /
                       (c[t] + k1 * (1 - b + b * len(d) / avgdl)) for t in qt))
    return out


def norm01(xs):
    lo, hi = min(xs, default=0), max(xs, default=0)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def covers(span, gold, frac=0.5):
    """Recall hit definition: candidate span covers >=frac of the gold word span."""
    if not span or not gold: return False
    s0, s1 = span; g0, g1 = gold
    return max(0, min(s1, g1) - max(s0, g0) + 1) >= frac * (g1 - g0 + 1)


def bootstrap(per_contract, n=10000, seed=0):
    """Contract-level bootstrap 95% CI on overall recall (percent)."""
    random.seed(seed); groups = list(per_contract.values()); boot = []
    if not groups: return (0.0, 0.0)
    for _ in range(n):
        xs = [h for g in (random.choice(groups) for _ in groups) for h in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


# --- corpus ------------------------------------------------------------------------
@dataclass
class Corpus:
    items: list          # QUERY-ONLY: [{category, contract, qa_id, question}] — NO gold
    rows: list           # [{contract, chunk, span}]
    cvec: list           # chunk vectors, aligned to rows
    qvec: dict           # qa_id -> query vector
    by_contract: dict    # contract -> [global row idx]
    dterms: list         # tokenized chunk text, aligned to rows
    spans: list          # (start,end) word span per row (or None)
    gold: dict           # qa_id -> gold word span; read ONLY by evaluate(), never a mechanism

    # expose primitives so a mechanism can reuse the exact same math
    cosine = staticmethod(cosine)
    terms = staticmethod(terms)
    bm25 = staticmethod(bm25)
    norm01 = staticmethod(norm01)

    def hybrid_scores(self, qvec, qterms, idxs, sw=0.9):
        """Baseline hybrid: sw*semantic + (1-sw)*normalized-BM25 over candidates."""
        sem = [cosine(qvec, self.cvec[i]) for i in idxs]
        bm = norm01(bm25(qterms, [self.dterms[i] for i in idxs]))
        return [sw * s + (1 - sw) * b for s, b in zip(sem, bm)]


def load() -> Corpus:
    raw_items = [json.loads(l) for l in open(P007 / "items.jsonl")]
    # Split gold out of the items so it lives only in `gold`, never in the mechanism's reach.
    gold = {it["qa_id"]: (tuple(it["gold_words"]) if it.get("gold_words") else None)
            for it in raw_items}
    items = [{"category": it["category"], "contract": it["contract"],
              "qa_id": it["qa_id"], "question": it["question"]} for it in raw_items]
    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]
    spans = [tuple(r["span"]) if r.get("span") else None for r in rows]
    return Corpus(items, rows, cvec, dict(qvec), dict(by_contract), dterms, spans, gold)


# --- evaluation --------------------------------------------------------------------
def evaluate(ctx: Corpus, topk_fn, k=3) -> dict:
    """Run a mechanism `topk_fn(ctx, item, idxs, k) -> [global row idx]` and score it.

    Only items whose contract has candidates and whose query vector exists are scored
    (identical skip rule to PoC 015, so numbers compare directly)."""
    per_contract, per_cat = defaultdict(list), defaultdict(list)
    for it in ctx.items:
        idxs = ctx.by_contract.get(it["contract"], [])
        if not idxs or it["qa_id"] not in ctx.qvec:
            continue
        gold = ctx.gold.get(it["qa_id"])
        # `it` is already a query-only view (no gold); the mechanism cannot see the answer.
        top = topk_fn(ctx, it, idxs, k)
        hit = any(covers(ctx.spans[j], gold) for j in top)
        per_contract[it["contract"]].append(1 if hit else 0)
        per_cat[it["category"]].append(1 if hit else 0)

    flat = [h for g in per_contract.values() for h in g]
    recall = 100 * sum(flat) / len(flat) if flat else 0.0
    lo, hi = bootstrap(per_contract)
    cats = {c: (100 * sum(v) / len(v), len(v)) for c, v in per_cat.items()}

    def group_mean(group):
        present = [c for c in group if c in cats]
        return sum(cats[c][0] for c in present) / max(len(present), 1)

    return {
        "recall_at_3": round(recall, 2),
        "ci95": [round(lo, 2), round(hi, 2)],
        "n_items": len(flat),
        "hard_mean": round(group_mean(HARD), 2),
        "weak_mean": round(group_mean(WEAK), 2),
        "per_category": {c: {"recall": round(r, 2), "n": n} for c, (r, n) in sorted(cats.items())},
    }


def evaluate_scores(ctx: Corpus, score_fn, k=3) -> dict:
    """Convenience seam: `score_fn(ctx, item, idxs) -> [float aligned to idxs]`.
    The harness turns scores into top-k GLOBAL indices itself (the experiment cannot
    reorder or hand-pick the final set outside of its declared scores)."""
    def topk_fn(c, it, idxs, kk):
        s = score_fn(c, it, idxs)
        order = sorted(range(len(idxs)), key=lambda j: s[j], reverse=True)[:kk]
        return [idxs[j] for j in order]
    return evaluate(ctx, topk_fn, k)


def baseline_metrics(ctx: Corpus, k=3) -> dict:
    """The built-in hybrid baseline (the number a PoC is measured against)."""
    def score_fn(c, it, idxs):
        return c.hybrid_scores(c.qvec[it["qa_id"]], terms(it["question"]), idxs)
    return evaluate_scores(ctx, score_fn, k)


# --- verdict (pre-registered, no eval) ---------------------------------------------
_OPS = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
        "<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def _derive(metrics: dict, baseline: dict | None) -> dict:
    """Flatten metrics + measurements into a numeric namespace, adding deltas vs
    the pre-registered baseline (e.g. recall_at_3_delta, hard_mean_delta)."""
    ns = {k: v for k, v in metrics.items() if isinstance(v, (int, float))}
    for cat, d in (metrics.get("per_category") or {}).items():
        ns[f"cat::{cat}"] = d["recall"]
    if baseline:
        for k, v in baseline.items():
            if isinstance(v, (int, float)) and k in ns:
                ns[f"{k}_delta"] = round(ns[k] - v, 2)
    return ns


def verdict(metrics: dict, decision: dict) -> dict:
    """Apply a pre-registered decision.json deterministically.

    decision.json schema:
      { "baseline": { "<var>": <num>, ... },        # optional; enables *_delta vars
        "adopt_if_all": [ {"var","op","value","note"?}, ... ],
        "reject_if_any": [ {"var","op","value","note"?}, ... ] }

    Rule: ADOPT if every adopt_if_all holds; else REJECT if any reject_if_any holds;
    else INCONCLUSIVE. A condition whose `var` is missing from the namespace makes the
    verdict INCONCLUSIVE with a `needs-human` reason (never silently passes)."""
    ns = _derive(metrics, decision.get("baseline"))
    missing, adopt_checks, reject_checks = [], [], []

    def check(cond):
        var, op, val = cond["var"], cond["op"], cond["value"]
        if var not in ns:
            missing.append(var); return None
        ok = _OPS[op](ns[var], val)
        return {"var": var, "op": op, "value": val, "actual": ns[var],
                "pass": ok, "note": cond.get("note", "")}

    for c in decision.get("adopt_if_all", []):
        r = check(c);  adopt_checks.append(r) if r else None
    for c in decision.get("reject_if_any", []):
        r = check(c); reject_checks.append(r) if r else None

    if missing:
        return {"verdict": "inconclusive", "reason": "needs-human",
                "missing_vars": sorted(set(missing)),
                "adopt_checks": adopt_checks, "reject_checks": reject_checks}
    adopt = bool(adopt_checks) and all(c["pass"] for c in adopt_checks)
    reject = any(c["pass"] for c in reject_checks)
    v = "adopt" if adopt else ("reject" if reject else "inconclusive")
    return {"verdict": v, "reason": "pre-registered rule",
            "adopt_checks": adopt_checks, "reject_checks": reject_checks}


# --- self-test ---------------------------------------------------------------------
def _self_test():
    ctx = load()
    m = baseline_metrics(ctx)
    delta = m["recall_at_3"] - RAW_BASELINE_RECALL
    ok = abs(delta) <= 1.0
    print(f"baseline recall@3 = {m['recall_at_3']}% (CI {m['ci95'][0]}-{m['ci95'][1]}), "
          f"expected ~{RAW_BASELINE_RECALL}%  ->  {'OK' if ok else 'MISMATCH'} (Δ{delta:+.2f})")
    print(f"  hard_mean={m['hard_mean']}  weak_mean={m['weak_mean']}  n={m['n_items']}")
    # exercise the verdict comparator on a synthetic metrics bundle
    demo = verdict({**m, "ram_saved_mb": 210},
                   {"baseline": {"recall_at_3": RAW_BASELINE_RECALL},
                    "adopt_if_all": [{"var": "recall_at_3", "op": ">=", "value": 61.4},
                                     {"var": "ram_saved_mb", "op": ">=", "value": 200}],
                    "reject_if_any": [{"var": "recall_at_3_delta", "op": "<", "value": -2.0}]})
    print(f"  verdict self-check: {demo['verdict']} ({demo['reason']})")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Deterministic CUAD recall@3 harness.")
    ap.add_argument("--self-test", action="store_true",
                    help="reproduce the hybrid baseline and exercise the verdict comparator")
    args = ap.parse_args()
    if args.self_test:
        raise SystemExit(_self_test())
    print("import this module, or run with --self-test")
