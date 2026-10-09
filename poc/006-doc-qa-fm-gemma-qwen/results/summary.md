# PoC 006 summary

986 items (504 answerable, 482 unanswerable) from 392 contracts. Run 1 of each arm.

| Arm | Answers answerable | Says absent on unanswerable | Balanced | Key fact right (n) | Any unsupported number | Unsupported, unanswerable | Hit cap | Errors | Median words | Median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| fm | 86% | 39% | **62%** | 85% (181) | 4% | 5% | 1% | 0 | 17.0 | 803 |
| gemma-e2b | 88% | 65% | **77%** | 90% (181) | 0% | 0% | 0% | 0 | 19.0 | 1143 |
| qwen-1.5b | 82% | 33% | **57%** | 77% (181) | 3% | 5% | 1% | 0 | 6.0 | 694 |

Contract-level bootstrap (10,000 resamples, seed 0):

- balanced gemma minus fm: +14.5 points, 95% CI [+11.3, +17.6]
- key fact gemma minus fm: +5.0 points, 95% CI [+0.5, +9.8]
- unsupported gemma minus fm: -4.3 points, 95% CI [-5.5, -3.1]
- absent rate qwen minus fm: -6.0 points, 95% CI [-11.5, -0.6]
- absent rate qwen minus gemma: -32.4 points, 95% CI [-37.4, -27.3]
- unsupported qwen minus fm: -1.4 points, 95% CI [-3.1, +0.2]
- unsupported qwen minus gemma: +2.8 points, 95% CI [+1.8, +4.0]

## Run-to-run agreement (same call in run 1 and run 2)

- fm: 94% of 986 items
- gemma-e2b: 95% of 986 items
- qwen-1.5b: 74% of 986 items

## Detector audit

- agreement: 96% of 120 labelled outputs fm 100%, gemma-e2b 98%, qwen-1.5b 90%

## Per category (answers answerable / says absent on unanswerable / key fact)

| Category | fm | gemma-e2b | qwen-1.5b |
|---|---|---|---|
| Agreement Date | 100% / 17% / 100% | 100% / 55% / 100% | 100% / 3% / 94% |
| Audit Rights | 83% / 100% / n/a | 92% / 89% / n/a | 67% / 39% / n/a |
| Cap On Liability | 81% / 50% / n/a | 64% / 75% / n/a | 64% / 53% / n/a |
| Change Of Control | 100% / 3% / n/a | 100% / 67% / n/a | 100% / 11% / n/a |
| Exclusivity | 11% / 100% / n/a | 72% / 83% / n/a | 58% / 50% / n/a |
| Expiration Date | 100% / 0% / 70% | 100% / 56% / 93% | 100% / 6% / 81% |
| Governing Law | 100% / 5% / 100% | 100% / 62% / 100% | 94% / 52% / 86% |
| Insurance | 100% / 28% / n/a | 97% / 81% / n/a | 94% / 50% / n/a |
| Liquidated Damages | 78% / 86% / n/a | 75% / 86% / n/a | 61% / 81% / n/a |
| Non-Compete | 100% / 14% / n/a | 81% / 92% / n/a | 64% / 36% / n/a |
| Notice Period To Terminate Renewal | 100% / 3% / 79% | 97% / 33% / 91% | 100% / 8% / 68% |
| Renewal Term | 92% / 19% / 91% | 100% / 44% / 97% | 94% / 31% / 69% |
| Termination For Convenience | 56% / 75% / n/a | 94% / 31% / n/a | 58% / 31% / n/a |
| Warranty Duration | 97% / 22% / 59% | 61% / 53% / 45% | 94% / 8% / 64% |

## Hypotheses

- H1_qwen_absent_rate_15_below_fm_and_gemma: does not hold
- H2_qwen_unsupported_5_above_fm_and_gemma: does not hold
- H3_fm_gemma_balanced_within_10: does not hold

## Decision rule (gemma-e2b vs fm)

- c0_detector_agreement_at_least_90: pass
- c1_balanced_gain_at_least_10_ci_above_0: pass
- c2_key_fact_not_worse_than_minus_5: pass
- c3_unsupported_not_worse_than_plus_5: pass

Verdict: **adopt (host stage)**
