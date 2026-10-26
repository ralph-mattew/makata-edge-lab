#!/usr/bin/env python3
"""PoC 050 — clause-phrase-template query transform (engine-discovered mechanism).

Provenance: this mechanism was INVENTED and statistically confirmed by the ideation engine's
`evolve_query_ops` search on the powered cuad_hard substrate (+26pp hard-category recall@3 out-of-
sample, per-query CI[0.177,0.343], frac+ 1.0). This PoC re-validates it on the lab's CANONICAL
full-corpus harness (emb-page chunks, covers>=50% recall@3, production 0.9/0.1 hybrid) — the test
that turns the within-substrate lead into a lab result.

Mechanism: the raw CUAD question ("Highlight the parts related to '<Category>' …") is replaced by a
small set of per-category EXEMPLAR CLAUSE PHRASINGS (a template-based HyDE-without-a-generator), each
embedded in-space and hybrid-scored; the union (max over sub-queries) ranks the chunks. No generator,
no re-chunking — only the query is reformulated.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from auto_experiment import harness

CACHE = Path(__file__).resolve().parent / "results" / "raw" / "emb-cache.jsonl"

# The confirmed operator's per-category exemplar clause phrasings (evolve_query_ops: clause_phrase_templates).
TEMPLATES = {
    "exclusivity": ["grants the exclusive right to", "shall be the sole and exclusive provider",
                    "exclusive distributor during the term"],
    "non-compete": ["shall not directly or indirectly engage in any competing business",
                    "covenant not to compete during the term and thereafter",
                    "restriction on engaging in a competing business"],
    "change of control": ["in the event of a merger, acquisition or change of control",
                          "upon a sale of all or substantially all assets",
                          "assignment upon change in ownership or control"],
    "non-solicitation": ["shall not solicit or hire employees of the other party",
                         "agrees not to induce or divert customers",
                         "non-solicitation of employees and customers"],
    "governing law": ["this agreement shall be governed by and construed under the laws of",
                      "the laws of the state shall govern without regard to conflicts",
                      "jurisdiction and venue shall lie exclusively in"],
    "cap on liability": ["total aggregate liability shall not exceed the amounts paid",
                         "in no event shall either party be liable for amounts exceeding",
                         "limitation of liability caps damages at"],
    "audit rights": ["shall have the right to audit and inspect the books and records",
                     "right to examine records upon reasonable notice",
                     "audit of financial records and compliance"],
    "insurance": ["shall maintain insurance coverage in amounts not less than",
                  "commercial general liability insurance policy",
                  "maintain policies of insurance during the term"],
    "minimum commitment": ["agrees to purchase a minimum quantity of", "minimum annual purchase commitment",
                           "required minimum volume or spend"],
}


def _subqueries(category: str):
    cl = (category or "").strip().lower()
    out = [category.strip()] if category else []
    for k, v in TEMPLATES.items():
        if k in cl or cl in k:
            out.extend(v); break
    else:
        out.append(f"{category.strip()} provision setting forth obligations")
    return out[:6] or [category or ""]


def candidate_scores(ctx, item, idxs):
    """Union-by-max hybrid score over the category's exemplar clause phrasings (embedded in-space)."""
    subs = _subqueries(item.get("category", ""))
    vecs = ctx.embed_queries(subs, cache=CACHE)
    best = [-1e9] * len(idxs)
    for sv, st in zip(vecs, subs):
        sc = ctx.hybrid_scores(sv, harness.terms(st), idxs)
        best = [max(b, s) for b, s in zip(best, sc)]
    return best


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--category", default="Exclusivity")
    if ap.parse_args().smoke:
        print("sub-queries for", "Exclusivity", "->", _subqueries("Exclusivity"))
        print("sub-queries for", "Governing Law", "->", _subqueries("Governing Law"))
