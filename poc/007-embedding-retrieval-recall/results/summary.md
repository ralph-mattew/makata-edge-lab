# PoC 007 summary

1325 items, 397 contracts, 79037 chunks. Verdict: **adopt (host stage)**.

## Recall of the answer-bearing text (percent of items)

| Arm | recall@1 | recall@3 | recall@5 | full@3 | any overlap@3 | mean coverage@3 | median words read@3 |
|---|---|---|---|---|---|---|---|
| nl-hybrid | 21.7 | 35.2 | 42.4 | 33.4 | 37.9 | 35.4 | 279 |
| eg-hybrid | 44.5 | 61.4 | 67.5 | 60.1 | 62.8 | 61.4 | 331 |
| nl-only | 3.9 | 9.7 | 15.3 | 8.5 | 11.0 | 9.8 | 156 |
| eg-only | 42.0 | 60.6 | 69.1 | 58.3 | 62.2 | 60.4 | 292 |
| kw-only | 32.2 | 46.6 | 52.9 | 44.9 | 47.8 | 46.2 | 358 |
| bm25 | 32.5 | 46.4 | 54.6 | 44.9 | 48.4 | 46.5 | 263 |
| oracle (best 3 chunks) | | 100.0 | | 99.8 | | | |

recall = the retrieved chunks, overlap included, cover at least 50% of the gold span's words. full = at least 90%. bm25 is a reference outside Xylo's pipeline (raw top-k, no re-ranking).

## Decision

- eg-hybrid minus nl-hybrid, recall@3: +26.2 points, 95% CI [+23.8, +28.5] (contract-level paired bootstrap).
- c1 (gain >= 5 points, CI above 0): yes.
- c2 (median EmbeddingGemma embed time <= 50 ms per chunk on the host): yes (8.9 ms).
- Verdict: adopt (host stage).

## Hypotheses

- H1, eg-hybrid recall@3 >= nl-hybrid + 5 points: +26.2 points, 95% CI [+23.8, +28.5]. Holds.
- H2, eg-only recall@3 >= nl-only + 10 points: +50.9 points, 95% CI [+48.3, +53.5]. Holds.
- H3, nl-hybrid recall@3 no more than 5 points above kw-only: -11.3 points, 95% CI [-13.7, -8.9]. Holds.

## Per category, recall@3 (percent)

| Category | n | nl-hybrid | eg-hybrid | nl-only | eg-only | kw-only | bm25 |
|---|---|---|---|---|---|---|---|
| Agreement Date | 100 | 6.0 | 28.0 | 3.0 | 22.0 | 37.0 | 12.0 |
| Audit Rights | 100 | 27.0 | 62.0 | 5.0 | 62.0 | 46.0 | 70.0 |
| Cap On Liability | 100 | 35.0 | 55.0 | 4.0 | 48.0 | 40.0 | 29.0 |
| Change Of Control | 100 | 30.0 | 54.0 | 7.0 | 56.0 | 45.0 | 46.0 |
| Exclusivity | 100 | 1.0 | 5.0 | 0.0 | 6.0 | 5.0 | 11.0 |
| Expiration Date | 100 | 54.0 | 86.0 | 24.0 | 87.0 | 41.0 | 66.0 |
| Governing Law | 100 | 81.0 | 96.0 | 18.0 | 96.0 | 79.0 | 69.0 |
| Insurance | 100 | 45.0 | 81.0 | 8.0 | 83.0 | 65.0 | 82.0 |
| Liquidated Damages | 54 | 31.5 | 53.7 | 11.1 | 42.6 | 44.4 | 51.9 |
| Non-Compete | 100 | 0.0 | 25.0 | 3.0 | 38.0 | 6.0 | 16.0 |
| Notice Period To Terminate Renewal | 100 | 30.0 | 89.0 | 4.0 | 84.0 | 72.0 | 24.0 |
| Renewal Term | 100 | 77.0 | 92.0 | 26.0 | 95.0 | 79.0 | 76.0 |
| Termination For Convenience | 100 | 46.0 | 71.0 | 21.0 | 66.0 | 50.0 | 56.0 |
| Warranty Duration | 71 | 25.4 | 57.7 | 0.0 | 52.1 | 39.4 | 42.3 |
| macro average | | 34.9 | 61.1 | 9.6 | 59.8 | 46.3 | 46.5 |

## Embedding cost on the host

| Backend | chunks | median ms | mean ms | p95 ms | median seconds per contract |
|---|---|---|---|---|---|
| nl | 79037 | 14.5 | 20.2 | 51.8 | 2.7 |
| eg | 79037 | 8.9 | 10.6 | 19.1 | 1.4 |

EmbeddingGemma tokens embedded: 7998925, chunks truncated at 2048 tokens: 3. NLEmbedding chunks with no vector: 0.

## Score spread (per item, over all chunks of the contract)

| Backend | median (top minus median score) | median (max minus min) |
|---|---|---|
| nl | 0.230 | 0.507 |
| eg | 0.236 | 0.446 |

## Detected languages (NLEmbedding path)

- doc=ca query=en: 8 items
- doc=de query=en: 3 items
- doc=en query=en: 1298 items
- doc=id query=en: 11 items
- doc=nl query=en: 3 items
- doc=ro query=en: 2 items

## Semantic-weight sweep, recall@3 (exploratory, not registered)

| Setting | recall@3 |
|---|---|
| nl semantic weight 0.5 | 42.6 |
| nl semantic weight 0.7 | 35.2 |
| nl semantic weight 0.9 | 18.6 |
| nl semantic weight 1.0 | 9.7 |
| eg semantic weight 0.5 | 57.2 |
| eg semantic weight 0.7 | 61.4 |
| eg semantic weight 0.9 | 62.5 |
| eg semantic weight 1.0 | 60.6 |
