#!/usr/bin/env python3
"""PoC 016 — compare the 4 conditions against the registered decision rule."""
from __future__ import annotations
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]
EASY = ["Governing Law", "Insurance"]


def load(c, q): return json.loads((OUT / f"recall-{c}-{q}.json").read_text())


def main():
    base = load("page", "raw")
    xref = load("xref", "raw")
    decomp = load("page", "decomp")
    both = load("xref", "decomp")
    lines = []
    def p(s): lines.append(s); print(s)

    p("== PoC 016: cross-reference resolution + question decomposition ==")
    p(f"baseline (page/raw): overall {base['recall']:.1f}% | hard-cat mean {base['hard_mean']:.1f}%")
    p("")
    p(f"{'condition':16} {'overall':>8} {'Δover':>7} {'hard-mean':>10} {'Δhard':>7}")
    for name, r in [("page/raw", base), ("xref/raw", xref), ("page/decomp", decomp), ("xref/decomp", both)]:
        p(f"{name:16} {r['recall']:>7.1f}% {r['recall']-base['recall']:>+6.1f} "
          f"{r['hard_mean']:>9.1f}% {r['hard_mean']-base['hard_mean']:>+6.1f}")
    p("")
    p("Hard categories, per condition (recall@3):")
    p(f"  {'category':22} {'page/raw':>9} {'xref':>7} {'decomp':>7} {'both':>7}")
    for c in HARD:
        g = lambda r: r["per_category"].get(c, {}).get("recall", float("nan"))
        p(f"  {c:22} {g(base):>8.1f}% {g(xref):>6.1f}% {g(decomp):>6.1f}% {g(both):>6.1f}%")
    p("")
    h1 = xref["hard_mean"] - base["hard_mean"]
    h2 = decomp["hard_mean"] - base["hard_mean"]
    best_single = max(xref["hard_mean"], decomp["hard_mean"])
    h3 = both["hard_mean"] - best_single
    h4_overall = min(xref["recall"], decomp["recall"], both["recall"]) - base["recall"]
    p("DECISION RULE read-out:")
    p(f"  H1 xref hard-mean +>=10:        {'PASS' if h1>=10 else 'no'} ({h1:+.1f})")
    p(f"  H2 decomp hard-mean +>=10:      {'PASS' if h2>=10 else 'no'} ({h2:+.1f})")
    p(f"  H3 combo beats best single +>=3:{'PASS' if h3>=3 else 'no'} ({h3:+.1f})")
    p(f"  H4 no overall regression >1pt:  {'PASS' if h4_overall>=-1 else 'no'} (worst Δ {h4_overall:+.1f})")
    adopt = []
    if h1 >= 10 and (xref['recall']-base['recall']) >= -1: adopt.append("xref")
    if h2 >= 10 and (decomp['recall']-base['recall']) >= -1: adopt.append("decomp")
    if h3 >= 3 and (both['recall']-base['recall']) >= -1: adopt.append("combination")
    p(f"  -> ADOPT: {adopt or 'none (reject/inconclusive; see per-category deltas)'}")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
