# PoC 008 summary

986 items (504 answerable, 482 unanswerable) from 392 contracts, one run per arm. Detector v2.

| Backend | Variant | Answers answerable | Says absent on unanswerable | Balanced | Key fact right (n) | Any unsupported number | Fixed phrase, all | Fixed phrase, answerable | Hit cap | Errors | Median words | Median ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fm | base | 86% | 39% | **63%** | 82% (181) | 4% | 0% | 0% | 1% | 0 | 18.0 | 815 |
| fm | rule | 91% | 39% | **65%** | 87% (181) | 3% | 2% | 0% | 1% | 0 | 21.0 | 889 |
| fm | rule-q | 83% | 57% | **70%** | 75% (181) | 2% | 24% | 9% | 1% | 0 | 12.0 | 747 |
| gemma-e2b | base | 88% | 65% | **77%** | 90% (181) | 0% | 0% | 0% | 0% | 0 | 19.0 | 1371 |
| gemma-e2b | rule | 85% | 80% | **83%** | 88% (181) | 0% | 0% | 0% | 1% | 0 | 19.0 | 1376 |
| gemma-e2b | rule-q | 82% | 83% | **82%** | 88% (181) | 0% | 6% | 1% | 0% | 0 | 19.0 | 1447 |
| qwen-1.5b | base | 79% | 45% | **62%** | 77% (181) | 3% | 0% | 0% | 1% | 0 | 6.0 | 856 |
| qwen-1.5b | rule | 75% | 60% | **67%** | 72% (181) | 1% | 16% | 8% | 0% | 0 | 8.0 | 910 |
| qwen-1.5b | rule-q | 31% | 90% | **60%** | 27% (181) | 0% | 53% | 49% | 0% | 0 | 7.0 | 878 |

## Detector v1 (PoC 006's, frozen), for comparison

| Backend | Variant | Answers answerable | Says absent on unanswerable | Balanced |
|---|---|---|---|---|
| fm | base | 86% | 39% | 63% |
| fm | rule | 91% | 39% | 65% |
| fm | rule-q | 83% | 57% | 70% |
| gemma-e2b | base | 88% | 65% | 77% |
| gemma-e2b | rule | 85% | 80% | 82% |
| gemma-e2b | rule-q | 82% | 83% | 82% |
| qwen-1.5b | base | 82% | 33% | 57% |
| qwen-1.5b | rule | 76% | 59% | 68% |
| qwen-1.5b | rule-q | 32% | 88% | 60% |

## Changes against base (contract-level bootstrap, 10,000 resamples, seed 0)

**fm, rule minus base**
- balanced: +1.9 points, 95% CI [-0.2, +4.0]
- absent rate: -0.6 points, 95% CI [-4.1, +2.8]
- answer rate: +4.4 points, 95% CI [+2.3, +6.6]
- key fact: +4.4 points, 95% CI [+0.6, +8.5]
- any unsupported: -1.3 points, 95% CI [-2.5, -0.1]

**fm, rule-q minus base**
- balanced: +7.6 points, 95% CI [+4.9, +10.4]
- absent rate: +18.3 points, 95% CI [+13.8, +22.6]
- answer rate: -3.0 points, 95% CI [-6.2, +0.4]
- key fact: -7.2 points, 95% CI [-13.1, -1.6]
- any unsupported: -2.2 points, 95% CI [-3.5, -1.0]

**gemma-e2b, rule minus base**
- balanced: +5.8 points, 95% CI [+3.7, +8.0]
- absent rate: +15.1 points, 95% CI [+12.0, +18.5]
- answer rate: -3.6 points, 95% CI [-6.1, -1.0]
- key fact: -2.2 points, 95% CI [-4.4, -0.5]
- any unsupported: -0.1 points, 95% CI [-0.5, +0.2]

**gemma-e2b, rule-q minus base**
- balanced: +5.6 points, 95% CI [+3.5, +7.8]
- absent rate: +17.8 points, 95% CI [+14.6, +21.4]
- answer rate: -6.5 points, 95% CI [-9.3, -3.9]
- key fact: -1.7 points, 95% CI [-4.6, +1.1]
- any unsupported: -0.1 points, 95% CI [-0.3, +0.0]

**qwen-1.5b, rule minus base**
- balanced: +5.5 points, 95% CI [+2.5, +8.4]
- absent rate: +14.5 points, 95% CI [+10.1, +19.0]
- answer rate: -3.6 points, 95% CI [-7.6, +0.4]
- key fact: -5.5 points, 95% CI [-13.0, +2.3]
- any unsupported: -1.8 points, 95% CI [-3.0, -0.7]

**qwen-1.5b, rule-q minus base**
- balanced: -1.5 points, 95% CI [-4.7, +1.7]
- absent rate: +44.6 points, 95% CI [+40.3, +48.9]
- answer rate: -47.6 points, 95% CI [-52.1, -43.0]
- key fact: -50.3 points, 95% CI [-58.1, -42.5]
- any unsupported: -2.9 points, 95% CI [-4.1, -1.9]

**Placement and the Qwen-against-FoundationModels contrast**
- fm:rule-q_minus_rule:absent_rate: +18.9 points, 95% CI [+14.4, +23.2]
- qwen-1.5b:rule-q_minus_rule:absent_rate: +30.1 points, 95% CI [+25.9, +34.2]
- qwen_gain_minus_fm_gain:rule:absent_rate: +15.1 points, 95% CI [+9.5, +20.8]

## Does base reproduce PoC 006 run 1? (same answer-or-absent call on the same item, detector v1)

- fm: 92%
- gemma-e2b: 100%
- qwen-1.5b: 100%

## Detector audit

- agreement: v2 98%, v1 97% of 120 labelled outputs; by backend (v2): fm 100%, gemma-e2b 100%, qwen-1.5b 92%; without the 13 fixed-phrase outputs: 97%

## Per category, answers answerable / says absent on unanswerable

| Category | fm:base | fm:rule | fm:rule-q | gemma-e2b:base | gemma-e2b:rule | gemma-e2b:rule-q | qwen-1.5b:base | qwen-1.5b:rule | qwen-1.5b:rule-q |
|---|---|---|---|---|---|---|---|---|---|
| Agreement Date | 100% / 21% | 100% / 28% | 75% / 76% | 100% / 55% | 100% / 62% | 97% / 76% | 100% / 3% | 86% / 28% | 22% / 93% |
| Audit Rights | 86% / 97% | 89% / 94% | 97% / 89% | 94% / 89% | 92% / 97% | 89% / 94% | 61% / 81% | 75% / 86% | 47% / 97% |
| Cap On Liability | 89% / 53% | 97% / 39% | 83% / 64% | 64% / 75% | 56% / 92% | 58% / 92% | 61% / 61% | 53% / 81% | 22% / 97% |
| Change Of Control | 100% / 6% | 100% / 17% | 94% / 53% | 100% / 67% | 97% / 89% | 97% / 89% | 100% / 11% | 92% / 28% | 39% / 89% |
| Exclusivity | 6% / 100% | 22% / 97% | 31% / 92% | 72% / 83% | 58% / 92% | 44% / 94% | 44% / 81% | 33% / 86% | 8% / 100% |
| Expiration Date | 100% / 0% | 97% / 0% | 94% / 22% | 100% / 56% | 97% / 72% | 94% / 81% | 100% / 6% | 100% / 25% | 33% / 83% |
| Governing Law | 100% / 10% | 100% / 19% | 89% / 57% | 100% / 62% | 100% / 81% | 100% / 81% | 94% / 52% | 69% / 81% | 8% / 100% |
| Insurance | 100% / 31% | 100% / 67% | 94% / 69% | 97% / 81% | 97% / 83% | 97% / 83% | 94% / 61% | 100% / 67% | 58% / 97% |
| Liquidated Damages | 83% / 86% | 89% / 67% | 78% / 86% | 75% / 86% | 67% / 92% | 67% / 97% | 56% / 86% | 42% / 94% | 8% / 100% |
| Non-Compete | 100% / 17% | 100% / 3% | 100% / 25% | 81% / 92% | 78% / 97% | 58% / 100% | 47% / 81% | 61% / 83% | 11% / 89% |
| Notice Period To Terminate Renewal | 100% / 8% | 100% / 11% | 83% / 53% | 100% / 33% | 94% / 67% | 92% / 75% | 100% / 11% | 92% / 33% | 56% / 75% |
| Renewal Term | 94% / 25% | 100% / 3% | 97% / 11% | 100% / 44% | 100% / 53% | 100% / 53% | 94% / 39% | 89% / 61% | 36% / 94% |
| Termination For Convenience | 53% / 61% | 75% / 72% | 75% / 64% | 94% / 31% | 89% / 64% | 89% / 53% | 53% / 42% | 75% / 50% | 36% / 89% |
| Warranty Duration | 97% / 19% | 100% / 14% | 75% / 47% | 61% / 53% | 64% / 78% | 64% / 89% | 94% / 11% | 83% / 33% | 47% / 56% |

## Hypotheses

- H1_fm_rule_absent_up_15_answer_down_at_most_5: does not hold
- H2_qwen_absent_gain_10_below_fm_gain: does not hold
- H3_reminder_adds_5_absent_for_fm_and_qwen: holds

## Decision rule (treated variant against base, per backend)

- fm, rule: reject: no gain (c1 fail, c2 pass, c3 pass)
- fm, rule-q: reject: trade-off (c1 pass, c2 pass, c3 fail)
- gemma-e2b, rule: adopt (host stage) (c1 pass, c2 pass, c3 pass)
- gemma-e2b, rule-q: reject: trade-off (c1 pass, c2 fail, c3 pass)
- qwen-1.5b, rule: reject: trade-off (c1 pass, c2 pass, c3 fail)
- qwen-1.5b, rule-q: reject: no gain (c1 fail, c2 fail, c3 fail)

- fm: **reject: no gain**
- gemma-e2b: **adopt (host stage): rule**
- qwen-1.5b: **reject: trade-off**

Headline verdict (FoundationModels): **reject: no gain**
