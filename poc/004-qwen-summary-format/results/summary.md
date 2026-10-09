# PoC 004 summary

600 generations, 20 documents. Rates are shares of generations per arm.

| Arm | n | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Exemplar leak | Loop | END line | Headings found (1/2/3/4) | Median tokens | Median decode tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a-near-greedy | 100 | 95% | 5% | 3% | 3% | 12% | 1% | 0% | 45% | 0 / 86 / 11 / 3 | 101.0 | 93.4 |
| a-repeat-1.05 | 100 | 99% | 1% | 42% | 42% | 0% | 0% | 3% | 0% | 0 / 31 / 27 / 42 | 131.5 | 90.3 |
| b-qwen-recipe | 100 | 98% | 2% | 39% | 39% | 3% | 0% | 1% | 4% | 0 / 39 / 22 / 39 | 131.5 | 90.6 |
| b-repeat-1.15 | 100 | 98% | 2% | 15% | 14% | 12% | 0% | 0% | 29% | 0 / 70 / 15 / 15 | 112.0 | 94.2 |
| b-repeat-1.3 | 100 | 91% | 9% | 4% | 4% | 21% | 2% | 0% | 24% | 2 / 86 / 8 / 4 | 128.0 | 96.1 |
| b-no-end-line | 100 | 100% | 0% | 36% | 36% | 3% | 0% | 0% | 0% | 0 / 47 / 17 / 36 | 115.0 | 62.0 |

Document-level bootstrap (10,000 resamples, seed 0):

- Complete, b-no-end-line minus b-qwen-recipe: -3.0 points, 95% CI [-13.0, +7.0]
- Four sections, b-no-end-line minus b-qwen-recipe: -3.0 points, 95% CI [-13.0, +7.0]
- Four sections, b-repeat-1.3 minus b-qwen-recipe: -35.0 points, 95% CI [-45.0, -25.0]
- Four sections, a-repeat-1.05 minus a-near-greedy: +39.0 points, 95% CI [+24.0, +54.0]

## Hypotheses

- H1_b_side_repeat_lowers_four: holds
- H2_a_side_repeat_raises_four: holds
- H3_no_end_line_raises_four: does not hold

## Decision rule (b-no-end-line vs b-qwen-recipe, first match wins)

- c1_complete_gain: fail
- c2_clean_at_least_90pct: pass
- c3_unsupported_within_5pts: pass
- c4_leak_at_most_5pct: pass

Verdict: **reject: no gain**

## Reproducibility check against PoC 003

- a-near-greedy: 100 of 100 generations token-identical to PoC 003
- b-qwen-recipe: 100 of 100 generations token-identical to PoC 003

## Exploratory (added after the run; not part of the decision rule)

Documents by complete rate (of 20):

- b-no-end-line vs b-qwen-recipe: higher 4, equal 10, lower 6
- a-repeat-1.05 vs a-near-greedy: higher 15, equal 5, lower 0
- a-repeat-1.05 vs b-qwen-recipe: higher 8, equal 5, lower 7

Documents where none of the 5 seeds gave a complete output: a-near-greedy 18, a-repeat-1.05 5, b-qwen-recipe 2, b-repeat-1.15 9, b-repeat-1.3 16, b-no-end-line 2
