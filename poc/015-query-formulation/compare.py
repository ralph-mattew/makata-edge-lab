#!/usr/bin/env python3
"""PoC 015 — compare query transforms; apply the registered decision rule (Arm A)."""
from __future__ import annotations
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"
WEAK = ["Exclusivity", "Non-Compete", "Agreement Date", "Warranty Duration",
        "Liquidated Damages", "Cap On Liability"]
EASY = ["Governing Law", "Insurance"]
CONDS = ["raw", "gloss", "keywords", "decomp"]


def main():
    R = {c: json.loads((OUT / f"recall-{c}.json").read_text()) for c in CONDS}
    base = R["raw"]; lines = []
    def p(s): lines.append(s); print(s)

    p("== PoC 015: query formulation (chunks fixed = PoC 014 page) ==")
    p(f"baseline raw: overall {base['recall']:.1f}% | weak-cat mean {base['weak_mean']:.1f}%")
    p("")
    p(f"{'cond':10} {'overall':>8} {'Δover':>7} {'weak-mean':>10} {'Δweak':>7}")
    for c in CONDS:
        r = R[c]
        p(f"{c:10} {r['recall']:>7.1f}% {r['recall']-base['recall']:>+6.1f} "
          f"{r['weak_mean']:>9.1f}% {r['weak_mean']-base['weak_mean']:>+6.1f}")
    p("")
    p("Per-category recall@3 (weak categories):")
    p(f"  {'category':30} " + " ".join(f"{c:>8}" for c in CONDS) + "   best")
    for cat in WEAK:
        vals = {c: R[c]["per_category"].get(cat, {}).get("recall") for c in CONDS}
        if any(v is None for v in vals.values()):
            continue
        best = max(CONDS, key=lambda c: vals[c])
        p(f"  {cat:30} " + " ".join(f"{vals[c]:>7.1f}%" for c in CONDS) + f"   {best}")
    p("")
    # H1: decomp lifts >=10 on >= half of weak cats, weak-mean >= +6
    dgains = {cat: R["decomp"]["per_category"].get(cat, {}).get("recall", 0)
                   - base["per_category"].get(cat, {}).get("recall", 0) for cat in WEAK}
    n_big = sum(1 for g in dgains.values() if g >= 10)
    weak_d = R["decomp"]["weak_mean"] - base["weak_mean"]
    h1 = n_big >= len(WEAK) / 2 and weak_d >= 6
    h3 = min(R[c]["recall"] for c in CONDS) - base["recall"] >= -1
    p("DECISION RULE (Arm A — recall@3):")
    p(f"  H1 decomp generalizes (>=10 on >=half weak AND weak-mean +>=6): "
      f"{'PASS' if h1 else 'no'} ({n_big}/{len(WEAK)} cats >=+10, weak-mean {weak_d:+.1f})")
    p(f"  H3 no overall regression >1pt: {'PASS' if h3 else 'no'}")
    # H2 cheapest-within-top-CI per category is reported qualitatively above (best col)
    p("  H2 (cheapest within top CI per category): see 'best' column")
    p("  H4 (end-to-end key-fact conversion): Arm B — pending (recall@3 is a proxy)")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
