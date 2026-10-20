#!/usr/bin/env python3
"""PoC 014 — compare page vs clause: overall, span-integrity, and per-category deltas.

Reads results/recall-page.json and results/recall-clause.json (written by score.py).
Prints the H1 (overall), H2 (hard categories), H3 (span integrity) and H4 (chunk count)
read-outs against the registered decision rule. Writes results/comparison.txt.
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
EASY = ["Insurance", "Governing Law"]


def main():
    page = json.loads((OUT / "recall-page.json").read_text())
    clause = json.loads((OUT / "recall-clause.json").read_text())
    lines = []

    def p(s): lines.append(s); print(s)

    p("== PoC 014: clause-aware vs page-based chunking ==")
    p(f"items: {page['n_items']} | chunks: page {page['n_chunks']} / clause {clause['n_chunks']} "
      f"({clause['n_chunks']/max(page['n_chunks'],1):.2f}x)")
    p("")
    p("H1 (overall recall@3):")
    p(f"  page   = {page['recall']:.1f}% (CI {page['ci'][0]:.1f}–{page['ci'][1]:.1f})")
    p(f"  clause = {clause['recall']:.1f}% (CI {clause['ci'][0]:.1f}–{clause['ci'][1]:.1f})")
    p(f"  Δ = {clause['recall']-page['recall']:+.1f} pts   (adopt threshold: +>=3)")
    p("")
    p("H3 (span-integrity: gold span fully inside one chunk):")
    p(f"  page   = {page['span_integrity']:.1f}%")
    p(f"  clause = {clause['span_integrity']:.1f}%")
    p(f"  Δ = {clause['span_integrity']-page['span_integrity']:+.1f} pts   (adopt needs: improves)")
    p("")
    p("H2 (per-category recall Δ; HARD = weight-invariant targets):")
    p(f"  {'category':28} {'n':>4} {'page':>7} {'clause':>7} {'Δ':>7}  class")
    pc, cc = page["per_category"], clause["per_category"]
    for cat in sorted(set(pc) | set(cc), key=lambda c: -(cc.get(c, {}).get("n", 0))):
        pr, cr = pc.get(cat, {}), cc.get(cat, {})
        n = cr.get("n", pr.get("n", 0))
        a, b = pr.get("recall"), cr.get("recall")
        if a is None or b is None:
            continue
        cls = "HARD" if cat in HARD else ("easy" if cat in EASY else "")
        p(f"  {cat[:28]:28} {n:>4} {a:>6.1f}% {b:>6.1f}% {b-a:>+6.1f}  {cls}")
    p("")
    hard_ok = all((cc.get(c, {}).get("recall", 0) - pc.get(c, {}).get("recall", 0)) >= 5
                  for c in HARD if c in cc and c in pc)
    overall_d = clause["recall"] - page["recall"]
    si_ok = clause["span_integrity"] > page["span_integrity"]
    p("VERDICT read-out (apply the registered decision rule):")
    p(f"  H1 overall +>=3 pts: {'PASS' if overall_d>=3 else 'no'} ({overall_d:+.1f})")
    p(f"  H2 hard cats each +>=5 pts: {'PASS' if hard_ok else 'no'}")
    p(f"  H3 span-integrity improves: {'PASS' if si_ok else 'no'}")
    p(f"  -> ADOPT needs H1 AND H3 (and H4 chunk-ratio <=1.3x). "
      f"{'LIKELY ADOPT' if overall_d>=3 and si_ok else ('REJECT' if overall_d<1 else 'INCONCLUSIVE')}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
