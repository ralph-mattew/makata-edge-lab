# PoC 009 summary

1325 items, run 1. Verdict (EmbeddingGemma retrieval): **reject: no gain**. With NLEmbedding retrieval: **adopt (host stage)**.

## Run 1, by condition (percent of items)

| Condition | Recall | Key fact right | Answers | Says absent | Any unsupported number | Hit budget | Median prompt tokens | p95 | Max | Median prefill ms | Median total ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| eg-k1 | 44.5 | 55.4 (n=464) | 73.5 | 26.5 | 4.1 | 0.1 | 335 | 467 | 886 | 286 | 593 |
| eg-k3 | 61.4 | 67.9 (n=464) | 78.6 | 21.4 | 1.4 | 0.3 | 625 | 965 | 1503 | 583 | 979 |
| eg-k5 | 67.2 | 68.3 (n=464) | 79.5 | 20.5 | 1.9 | 0.8 | 925 | 1415 | 1604 | 840 | 1204 |
| nl-k3 | 35.2 | 45.9 (n=464) | 70.3 | 29.7 | 3.1 | 0.5 | 555 | 928 | 1296 | 422 | 731 |
| nl-k5 | 42.3 | 50.4 (n=464) | 73.9 | 26.1 | 2.6 | 0.6 | 812 | 1367 | 1570 | 672 | 1021 |

Recall = the chunks cover at least half of CUAD's answer span (PoC 007's measure, with the word cap applied). An item is an answer or absent by detector v2; the verdict does not use it.

## Split by whether the chunks cover the answer

| Condition | Key fact, covered | Key fact, not covered | Answers, covered | Answers, not covered | Items with chunks dropped by the cap | Budget below 200 |
|---|---|---|---|---|---|---|
| eg-k1 | 81.9 | 14.8 | 89.7 | 60.5 | 0 | 0 |
| eg-k3 | 83.3 | 14.4 | 90.0 | 60.5 | 1 | 0 |
| eg-k5 | 79.0 | 16.5 | 88.8 | 60.4 | 32 | 0 |
| nl-k3 | 81.4 | 12.2 | 91.4 | 58.9 | 0 | 0 |
| nl-k5 | 80.1 | 13.9 | 90.7 | 61.5 | 25 | 0 |

## Comparisons (points, 95% CI from a contract-level bootstrap)

| Comparison | Difference | 95% CI |
|---|---|---|
| eg5_minus_eg3:key_fact | +0.4 | [-3.7, +4.4] |
| eg5_minus_eg3:answer_rate | +0.8 | [-1.2, +2.9] |
| eg5_minus_eg3:any_unsupported | +0.5 | [-0.4, +1.4] |
| eg5_minus_eg3:key_fact_covered3 | -5.0 | [-9.3, -0.8] |
| eg3_minus_eg1:key_fact | +12.5 | [+7.7, +17.4] |
| eg3_minus_eg1:answer_rate | +5.1 | [+2.8, +7.5] |
| nl5_minus_nl3:key_fact | +4.5 | [+0.5, +8.4] |
| nl5_minus_nl3:answer_rate | +3.5 | [+1.3, +5.8] |
| nl5_minus_nl3:any_unsupported | -0.5 | [-1.7, +0.7] |

## Decision

**EmbeddingGemma retrieval (the headline)**

- eg-k5 minus eg-k3, key fact right: +0.4 points, 95% CI [-3.7, +4.4].
- c1 (gain >= 3 points, CI above 0): no.
- c2 (any unsupported number rises by at most 3 points): yes.
- c3 (median prefill time at most 2.0 times eg-k3's): yes (1.44x).
- Verdict: reject: no gain.

**NLEmbedding retrieval (the fallback)**

- nl-k5 minus nl-k3, key fact right: +4.5 points, 95% CI [+0.5, +8.4].
- c1 (gain >= 3 points, CI above 0): yes.
- c2 (any unsupported number rises by at most 3 points): yes.
- c3 (median prefill time at most 2.0 times nl-k3's): yes (1.59x).
- Verdict: adopt (host stage).


## Hypotheses

- H1: +0.4 points, 95% CI [-3.7, +4.4]. Holds.
- H2: -5.0 points, 95% CI [-9.3, -0.8]. Holds.
- H3: +12.5 points, 95% CI [+7.7, +17.4]. Holds.

## Run 2 (seed 2; not used in the verdict)

- eg-k5 minus eg-k3, key fact right: +3.7 points.
- eg-k3: key fact right 65.9; same answer-or-absent call as run 1 on 81.4% of items.
- eg-k5: key fact right 69.6; same answer-or-absent call as run 1 on 82.3% of items.

## Per category, key fact right (percent; categories with parsable key facts)

| Category | n | eg-k3 | eg-k5 |
|---|---|---|---|
| Agreement Date | 84 | 32.1 | 45.2 |
| Expiration Date | 61 | 80.3 | 78.7 |
| Governing Law | 93 | 91.4 | 91.4 |
| Notice Period To Terminate Renewal | 95 | 74.7 | 68.4 |
| Renewal Term | 91 | 69.2 | 67.0 |
| Warranty Duration | 40 | 50.0 | 50.0 |
