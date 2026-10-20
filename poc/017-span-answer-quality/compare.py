#!/usr/bin/env python3
"""PoC 017 — decision-rule read-out from span-quality.json (raw vs keywords)."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"
HARD = ["Exclusivity", "Non-Compete", "Change Of Control"]


def main():
    d = json.loads((OUT / "span-quality.json").read_text())
    raw, kw = d["raw"], d["keywords"]
    lines = []
    def p(s): lines.append(s); print(s)
    p("== PoC 017: span-level answer quality (span-F1, raw vs keywords) ==")
    p("NOTE: absolute F1 is a low proxy for long clause answers; the DELTA is what's interpreted.")
    p("")
    p(f"{'category':22} {'raw':>7} {'keywords':>9} {'Δ':>7}")
    for c in HARD:
        ra = raw["per_category"].get(c, 0.0); rb = kw["per_category"].get(c, 0.0)
        p(f"{c:22} {ra:>7.1f} {rb:>9.1f} {rb-ra:>+6.1f}")
    hard_d = kw["hard_mean_f1"] - raw["hard_mean_f1"]
    excl_d = kw["per_category"].get("Exclusivity", 0) - raw["per_category"].get("Exclusivity", 0)
    coc_d = kw["per_category"].get("Change Of Control", 0) - raw["per_category"].get("Change Of Control", 0)
    p("")
    p(f"hard-category mean span-F1: raw {raw['hard_mean_f1']:.1f} -> keywords {kw['hard_mean_f1']:.1f} ({hard_d:+.1f})")
    p("")
    p("DECISION RULE:")
    p(f"  H1 hard-mean F1 +>=2:          {'PASS' if hard_d >= 2 else 'no'} ({hard_d:+.1f})")
    p(f"  H2 Exclusivity delta positive: {'PASS' if excl_d > 0 else 'no'} ({excl_d:+.1f})")
    p(f"  H3 Change-of-Control no regress >2: {'PASS' if coc_d >= -2 else 'no'} ({coc_d:+.1f})")
    if hard_d >= 2 and excl_d > 0:
        p("  -> CONVERSION CONFIRMED: keyword expansion's Exclusivity recall win shows up in answers.")
    elif hard_d <= 0:
        p("  -> GAP REMAINS: recall gain did not produce better answers on the hard categories.")
    else:
        p("  -> INCONCLUSIVE (small / CI-overlapping delta).")
    (OUT / "comparison.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
