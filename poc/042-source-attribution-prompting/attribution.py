#!/usr/bin/env python3
"""PoC 042 — source-attribution prompting for RAG generation (OP-2/OP-7).

Tests whether instructing Qwen2.5-1.5B to answer from NUMBERED sections, cite the supporting section,
and say ABSENT if none supports improves key-fact accuracy vs a plain non-attribution prompt — on
identical retrieval (hybrid 0.9/0.1 top-3 over committed PoC-014 chunks).

Metric: key-fact accuracy (PoC-006 facts.py typed-fact set-overlap) on the 464 answerable typed-fact
items (categories that carry key_facts gold). NOTE: the hard categories (Exclusivity / Non-Compete /
Change-of-Control) carry NO key_facts (clause-presence, not typed facts), so the proposal's H2
(hard-cat key-fact) is undefined; see the README Deviations. H4 guards answerable refusal inflation.

Servers: Qwen :8091 (generation). Committed vectors read via LAB_POC_ROOT (default: sibling poc/).
Run: LAB_POC_ROOT=/path/to/clone/poc python3 attribution.py
"""
from __future__ import annotations
import argparse, importlib.util, json, math, os, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P009 = _base / "009-retrieval-depth-qwen" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
FACTS_PY = _base / "006-doc-qa-fm-gemma-qwen" / "facts.py"
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]

# reuse PoC-006's typed-fact extractor verbatim
_spec = importlib.util.spec_from_file_location("facts", FACTS_PY)
facts = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(facts)

REFUSAL = re.compile(r"\b(not stated|not specified|not mentioned|not provided|not found|does not "
                     r"(?:contain|mention|specify)|no (?:information|mention|such)|cannot|could not find|"
                     r"unable to|n/?a|absent)\b", re.I)
BASE_PROMPT = ("Answer the question using ONLY the contract sections below. Be concise. If it is not "
               "in the sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")
ATTR_PROMPT = ("Answer the question using ONLY the numbered contract sections below. Be concise. After "
               "your answer, cite the section number(s) you used, e.g. [S2]. If no section supports a "
               "definitive answer, say ABSENT.\n\n{ctx}\n\nQUESTION: {q}\nANSWER:")
CITE = re.compile(r"\[\s*s?\d+\s*\]", re.I)


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


def qwen(url, prompt, n=160):
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
def strip_cites(ans): return CITE.sub("", ans).strip()


def key_fact_hit(kind, gold, text):
    if not gold:
        return None
    goldset = {tuple(f) for f in gold}
    got = {tuple(f) for f in facts.key_facts(kind, text)}
    return bool(goldset & got)


def bootstrap(per_contract, n=10000, seed=0):
    random.seed(seed); groups = list(per_contract.values()); boot = []
    for _ in range(n):
        xs = [v for g in (random.choice(groups) for _ in groups) for v in g]
        boot.append(100 * sum(xs) / len(xs) if xs else 0.0)
    boot.sort(); return boot[int(0.025 * n)], boot[int(0.975 * n)]


def norm_bool(v): return v if isinstance(v, bool) else (str(v).lower() == "true")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qwen-url", default="http://127.0.0.1:8091")
    ap.add_argument("--topk", type=int, default=3); ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    cvec = [json.loads(l)["vec"] for l in open(P014 / "emb-page.jsonl")]
    qvec = {d["key"]: d["vec"] for d in map(json.loads, open(P014 / "emb-queries.jsonl"))}
    by_contract = defaultdict(list)
    for i, r in enumerate(rows):
        by_contract[r["contract"]].append(i)
    dterms = [terms(r["chunk"]) for r in rows]

    items = [json.loads(l) for l in open(P009 / "items.jsonl")]
    work = [it for it in items if it.get("key_facts") and norm_bool(it["answerable"])
            and it["contract"] in by_contract and it["qa_id"] in qvec]
    if args.limit:
        work = work[:args.limit]
    print(f"typed-fact answerable items: {len(work)}  (key-fact accuracy; attribution vs baseline)")

    def top_chunks(it):
        idxs = by_contract[it["contract"]]; qv = qvec[it["qa_id"]]; qt = terms(it["question"])
        sem = [cosine(qv, cvec[i]) for i in idxs]; bm = norm01(bm25(qt, [dterms[i] for i in idxs]))
        h = [0.9 * s + 0.1 * b for s, b in zip(norm01(sem), bm)]
        order = sorted(range(len(idxs)), key=lambda j: h[j], reverse=True)[:args.topk]
        return [rows[idxs[j]]["chunk"] for j in order]

    OUT.mkdir(parents=True, exist_ok=True); raw = OUT / "raw"; raw.mkdir(exist_ok=True)

    def run(arm):
        per_cat, per_contract, refus = defaultdict(list), defaultdict(list), []
        cited = 0; dump = []
        for it in work:
            chunks = top_chunks(it)
            if arm == "base":
                ctx = "\n\n".join(chunks)[:6000]
                ans = qwen(args.qwen_url, BASE_PROMPT.format(ctx=ctx, q=it["question"]))
            else:
                ctx = "\n\n".join(f"[S{i+1}] {c}" for i, c in enumerate(chunks))[:6000]
                ans = qwen(args.qwen_url, ATTR_PROMPT.format(ctx=ctx, q=it["question"]))
                cited += bool(CITE.search(ans))
            scored = strip_cites(ans) if arm == "attr" else ans
            hit = key_fact_hit(it["key_fact_kind"], it["key_facts"], scored)
            per_cat[it["category"]].append(hit); per_contract[it["contract"]].append(hit)
            refus.append(is_refusal(scored))
            dump.append({"qa_id": it["qa_id"], "category": it["category"], "key_fact": hit,
                         "refusal": is_refusal(scored), "answer": ans[:400]})
        (raw / f"{arm}-answers.jsonl").write_text("\n".join(json.dumps(d) for d in dump) + "\n")
        flat = [h for g in per_contract.values() for h in g]
        overall = 100 * sum(flat) / len(flat)
        cats = {c: round(100 * sum(v) / len(v), 1) for c, v in per_cat.items() if v}
        lo, hi = bootstrap(per_contract)
        return {"arm": arm, "overall_key_fact": round(overall, 1), "ci": [round(lo, 1), round(hi, 1)],
                "per_category": cats, "answerable_refusal": round(100 * sum(refus) / len(refus), 1),
                "citation_rate": round(100 * cited / len(work), 1) if arm == "attr" else None,
                "n": len(flat)}

    base = run("base"); attr = run("attr")
    res = {"baseline": base, "attribution": attr,
           "delta_overall": round(attr["overall_key_fact"] - base["overall_key_fact"], 1),
           "delta_refusal": round(attr["answerable_refusal"] - base["answerable_refusal"], 1),
           "per_category_delta": {c: round(attr["per_category"].get(c, 0) - base["per_category"].get(c, 0), 1)
                                  for c in base["per_category"]},
           "hard_cat_key_fact": "N/A — hard categories carry no typed key_facts (clause-presence)"}
    h1 = res["delta_overall"] >= 3.0
    h4 = res["delta_refusal"] <= 3.0
    res["H1_overall_ge3"] = h1; res["H4_refusal_le3"] = h4
    pos2 = sum(1 for d in res["per_category_delta"].values() if d >= 5.0)
    res["H2_status"] = f"N/A (no hard-cat key_facts); fact-category cats with +>=5pp: {pos2}"
    res["verdict"] = ("ADOPT" if (h1 and h4) else ("REJECT" if res["delta_overall"] < 1.0 else "INCONCLUSIVE"))
    (OUT / "attribution.json").write_text(json.dumps(res, indent=2))

    lines = []
    def L(s): lines.append(s); print(s)
    L(f"baseline key-fact:    {base['overall_key_fact']:.1f}%  (CI {base['ci'][0]}-{base['ci'][1]})  "
      f"answerable refusal {base['answerable_refusal']:.1f}%   [009 ref ~67.9%]")
    L(f"attribution key-fact: {attr['overall_key_fact']:.1f}%  (CI {attr['ci'][0]}-{attr['ci'][1]})  "
      f"answerable refusal {attr['answerable_refusal']:.1f}%   citation-rate {attr['citation_rate']}%")
    L(f"\nΔ overall key-fact: {res['delta_overall']:+.1f}pp  [H1 >=+3 -> {h1}]")
    L(f"Δ answerable refusal: {res['delta_refusal']:+.1f}pp  [H4 <=+3 -> {h4}]")
    L(f"H2 (hard-cat key-fact): N/A — hard cats have no typed key_facts")
    L("\nper fact-category Δ (attr - base):")
    for c, d in sorted(res["per_category_delta"].items(), key=lambda x: x[1]):
        L(f"  {c:28} base {base['per_category'].get(c,0):5.1f} -> attr {attr['per_category'].get(c,0):5.1f}  ({d:+.1f})")
    L(f"\n-> {res['verdict']}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
