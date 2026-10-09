# PoC 003 summary

400 generations, 20 documents. Rates are shares of generations per arm.

| Arm | n | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Exemplar leak | Loop | Median tokens | Median decode tok/s |
|---|---|---|---|---|---|---|---|---|---|---|
| a-near-greedy | 100 | 95% | 5% | 3% | 3% | 12% | 1% | 0% | 101.0 | 99.2 |
| b-qwen-recipe | 100 | 98% | 2% | 39% | 39% | 3% | 0% | 1% | 131.5 | 109.3 |
| c-near-greedy-presence | 100 | 91% | 9% | 0% | 0% | 26% | 1% | 0% | 128.5 | 100.5 |
| d-qwen-recipe-no-presence | 100 | 100% | 0% | 41% | 41% | 0% | 0% | 2% | 126.5 | 108.3 |

Document-level bootstrap of B minus A (10,000 resamples, seed 0):

- Clean stop: +3.0 points, 95% CI [-1.0, +8.0]
- Complete: +36.0 points, 95% CI [+26.0, +47.0]

## Hypotheses

- H1_a_hits_cap_at_least_50pct: does not hold
- H2_b_clean_90_and_four_80: does not hold
- H3_presence_carries_effect: does not hold
- H4_b_unsupported_within_10pts_of_a: holds
- H5_b_median_tokens_at_most_220: holds

## Decision rule (A vs B, first match wins)

- c1_clean_gain: fail
- c2_complete_not_worse: pass
- c3_unsupported_within_10pts: pass
- c4_leak_at_most_5pct: pass

Verdict: **reject: does not reproduce**

## Exploratory (added after the run; not part of the decision rule)

| Arm | Generations by number of distinct section headings found | Output contains an END block line |
|---|---|---|
| a-near-greedy | 2: 86, 3: 11, 4: 3 | 45% |
| b-qwen-recipe | 2: 39, 3: 22, 4: 39 | 4% |
| c-near-greedy-presence | 1: 4, 2: 84, 3: 12 | 15% |
| d-qwen-recipe-no-presence | 2: 36, 3: 23, 4: 41 | 0% |

Documents by complete rate, B against A: b higher 17, equal 3
