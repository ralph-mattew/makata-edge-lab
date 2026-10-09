# PoC 005 summary

300 generations, 20 documents. Rates are shares of generations per arm.

| Arm | n | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Thin section | Exemplar leak | Loop | END line | Headings inserted (0/1/2/3) | Median tokens | Median decode tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b-shipped | 100 | 98% | 2% | 39% | 39% | 3% | 1% | 0% | 1% | 4% | 100 / 0 / 0 / 0 | 131.5 | 92.7 |
| b-insert-heading | 100 | 94% | 6% | 96% | 93% | 5% | 3% | 0% | 1% | 7% | 41 / 52 / 7 / 0 | 166.5 | 93.8 |
| b-suppress-end | 100 | 78% | 22% | 76% | 76% | 4% | 1% | 1% | 2% | 15% | 100 / 0 / 0 / 0 | 179.5 | 90.0 |

Document-level bootstrap (10,000 resamples, seed 0):

- Complete, b-insert-heading minus b-shipped: +54.0 points, 95% CI [+44.0, +64.0]
- Complete, b-suppress-end minus b-shipped: +37.0 points, 95% CI [+27.0, +46.0]
- Any unsupported number, b-insert-heading minus b-shipped: +2.0 points, 95% CI [+0.0, +5.0]
- Any unsupported number, b-suppress-end minus b-shipped: +1.0 points, 95% CI [+0.0, +3.0]

## Hypotheses

- H1_insert_complete_80: holds
- H2_suppress_complete_80: does not hold
- H3_unsupported_within_5pts: holds

## Decision rule (b-insert-heading vs b-shipped, first match wins)

- c1_complete_gain_30: pass
- c2_clean_at_least_90pct: pass
- c3_unsupported_within_5pts: pass
- c4_thin_at_most_10pct: pass
- c5_leak_at_most_5pct: pass

Verdict: **adopt**

## Reproducibility check against PoC 003

- b-shipped: 100 of 100 generations token-identical to PoC 003's b-qwen-recipe

## Exploratory (added after the run, not registered; does not affect the verdict)

- Documents, b-insert-heading vs b-shipped on complete count (higher/equal/lower): 19 / 1 / 0
- Documents, b-suppress-end vs b-shipped on complete count (higher/equal/lower): 17 / 3 / 0
- Documents with no complete output in 5 seeds: b-shipped 2, b-insert-heading 0, b-suppress-end 1
- Headings inserted by b-insert-heading: Action Items 30, Key Points 36
- b-suppress-end outputs that hit the cap, by sections found: 2: 17, 3: 5
- Action-item lines starting with a generic verb (ensure, review, confirm, verify, monitor, maintain, comply, coordinate, check): inserted heading 48 of 75, model-written heading 149 of 238
