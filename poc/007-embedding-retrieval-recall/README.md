# PoC 007: Retrieval recall of EmbeddingGemma and NLEmbedding on contract chunks

| | |
|---|---|
| Status | Written up (host stage) |
| Verdict | Adopt (host stage): EmbeddingGemma raises recall@3 from 35% to 61% over NLEmbedding at Xylo's weights, at 8.9 ms per chunk |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet (founding reviewers being invited) |
| Source idea | Xylo's v1.2 notes (private app): EmbeddingGemma retrieval ships on, chosen after a spot-check of 19 chunks, where its scores separated the chunks more clearly than NLEmbedding's did |
| Registered | 2026-10-09, in the commit that adds this file, before the first run |

## Question

On contracts too long to be read whole, does Xylo's retrieval find the text that answers a question
more often with EmbeddingGemma 300M embeddings than with Apple's NLEmbedding, at Xylo's chunking,
score weights and re-ranking?

## Why it matters here

Xylo splits a long document into chunks, scores each against the question, and gives the top 3 to the
chat model. The score is 0.7 times the cosine similarity of embeddings plus 0.3 times a keyword
score. The embeddings come from one of two places:

- **NLEmbedding**, Apple's sentence embedding, built into the OS. No download.
- **EmbeddingGemma 300M**, a 334 MB download. Xylo v1.2 ships it on by flag (`embeddingGemmaRetrieval`),
  also on 8 GB devices that have FoundationModels, and keeps NLEmbedding as the fallback.

The choice of EmbeddingGemma rests on a spot-check of 19 chunks. Whether it finds more of the right
text is not measured anywhere. The answer decides whether the 334 MB download, the extra memory while
it is loaded and the extra time at ingest are paying for themselves.

PoC 006 holds retrieval fixed and measures the chat models. This PoC measures retrieval, the part
PoC 006 leaves out.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items. Recall is defined under
Measurements.

1. **H1.** At Xylo's weights, `eg-hybrid` recall@3 is at least 5 points above `nl-hybrid`'s.
2. **H2.** On the embedding alone, `eg-only` recall@3 is at least 10 points above `nl-only`'s.
3. **H3.** NLEmbedding adds little to the keyword score: `nl-hybrid` recall@3 is no more than 5 points
   above `kw-only`'s.

Also descriptive: whether the score ranges match the spot-check's account (EmbeddingGemma separating
the best chunk from the rest, NLEmbedding clustered).

## Method

**Host.** MacBook Pro (Mac16,8), Apple M4 Pro, 24 GB, macOS 26.5.1 (25F80), on AC power.

**Models.**

| Backend | Model | File and SHA-256 | License |
|---|---|---|---|
| `nl` | Apple NLEmbedding, sentence embedding | Ships with macOS 26.5.1 (25F80); no file | Apple SDK terms |
| `eg` | EmbeddingGemma 300M, Q8_0 | `embeddinggemma-300M-Q8_0.gguf` from [ggml-org/embeddinggemma-300M-GGUF](https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF) at revision `0f741b5`, 333,590,944 bytes, SHA-256 `b5ce9d77a3fc4b3b39ccb5643c36777911cc4eb46a66962eadfa3f5f60490d63` | Gemma Terms of Use, as the [base model's card](https://huggingface.co/google/embeddinggemma-300m) states (`license: gemma`); the GGUF repository's own card does not restate it |

**Tooling.** llama.swift 2.8901.0 (llama.cpp b8901, Metal), the build Xylo ships; Swift 6.3.3.

**Items.** From CUAD v1 (CC BY 4.0, the zip PoCs 003 and 006 use, SHA-256 `88b694d9…d18e`).
[`prepare.py`](prepare.py) builds them; the same zip always gives the same files.

- **Contracts.** The 427 of 510 contracts with at least 1,800 words. Above Xylo's whole-document
  limits on the tiers below 11.5 GB (800 words on 6 GB, 1,100 on 8 GB), so these tiers retrieve
  chunks for these contracts, and EmbeddingGemma embeds them. Tiers at 11.5 GB and above chunk
  differently and are not covered.
- **Questions.** The 14 plain questions of PoC 006, one per CUAD category ([`questions.json`](questions.json),
  a byte-for-byte copy).
- **Answerable items only.** An item is a (contract, category) pair where CUAD gives an answer span
  and the span is at most 150 words. Retrieval cannot be right or wrong when there is no answer.
  The span is the first one CUAD lists. For each category, 100 items are drawn at random (seed 7), or
  all of them if fewer exist: Warranty Duration has 71 and Liquidated Damages 54. That makes
  **1,325 items from 397 contracts.** [`items.jsonl`](results/raw/items.jsonl) is committed.

**Chunks.** [`harness/Sources/Chunker`](harness/Sources/Chunker) follows Xylo's chunker for the 6 and
8 GB tiers, from reading its source:

- Each page is split on blank lines. A paragraph of at most 175 words is one chunk. A longer one is
  cut at sentence boundaries (Apple's `NLTokenizer`), adding sentences up to 175 words.
- Each chunk after the first starts with the last 30 words of the previous chunk's own text.
- CUAD's text has no page breaks, so each contract is cut into pages of about 500 words at paragraph
  boundaries. Xylo's page-diversity penalty needs pages to be meaningful.

CUAD paragraphs are short, so chunks are mostly short too, not 175-word tiles. Median chunk: 25 words
of its own text, 90th percentile 142 (MEASURED in a dry run of the chunker: 79,037 chunks over the
397 contracts; no retrieval was run).

**Scores.** [`harness/Sources/Scores`](harness/Sources/Scores) scores every chunk against the question
of each item:

- **`kw`**: Xylo's keyword score, the share of the question's keywords found in the chunk. Keywords are
  lowercased words of three or more letters or digits that are not stopwords, with simple suffix stripping.
  The stopword and suffix lists are Xylo's, so the scores match the app's. They are not published; they are loaded from a private overlay (see Errata).
- **`nl`**: cosine similarity of NLEmbedding sentence vectors. Chunks use the language detected from the
  start of the contract, and each question uses its own detected language, as in the app. A chunk with
  no vector gets a null score, counted as 0. The app would substitute a hashed keyword vector, which
  matters only when both sides fail.
- **`eg`**: cosine similarity of EmbeddingGemma vectors, as `EmbeddingEngine` makes them: context 2,048,
  mean pooling, 2 threads, all layers on the GPU, flash attention off, chunks prefixed
  `title: none | text: `, questions prefixed `task: search result | query: `, vectors L2-normalized,
  768 dimensions. A chunk over 2,048 tokens is truncated, and the count is reported.
- **`bm25`**: BM25 over chunk text (k1 1.2, b 0.75), as in PoC 006, with its own stopword list. A reference
  outside Xylo's pipeline.

**Arms.** All use the same chunks and questions. The first five go through Xylo's retriever as the app
runs it: score every chunk, keep the top K + 4, add 0.05 to a chunk whose neighbour is also kept, subtract
0.03 times (count - 1) from the third and later chunks of a page, keep the top K. Ties keep document
order.

| Arm | Score |
|---|---|
| `nl-hybrid` | 0.7 × NL cosine + 0.3 × keyword. The app's fallback, the control |
| `eg-hybrid` | 0.7 × EG cosine + 0.3 × keyword. The app as shipped |
| `nl-only` | NL cosine |
| `eg-only` | EG cosine |
| `kw-only` | keyword score |
| `bm25` | BM25, raw top K, no re-ranking. Reference |

K is 3 for the verdict, as Xylo's chat path takes at most 3 chunks. Recall at K of 1 and 5 is
reported too.

**Harness.** [`harness/`](harness) has two programs, `Chunker` and `Scores`. Both come from reading
Xylo's source. Apart from the data lists above (stopwords, suffixes) and the task prefixes, which are
the model card's, no Xylo code is in this repository.
[`index.py`](index.py) places each chunk in the contract's words and computes `bm25`;
[`summarize.py`](summarize.py) re-implements the retriever and scores the arms.

**Order.** [`run.sh`](run.sh) checks hashes and runs `prepare.py`, `Chunker`, then `Scores` in `kw`,
`nl` and `eg` modes, then `index.py`. Scores are deterministic, so there is one pass. Per-chunk embed
times come from the same pass. The host is kept awake with `caffeinate`, and the script warns if the
host is not on AC power.

**Smoke test before registration.** The three score modes ran on the first five contracts (13 items)
to check output shape, dimensions and timing, and `summarize.py` ran on that output. Those contracts are
in the final set. Their recall figures were seen, were not used to choose any threshold, and do not
enter the results except as part of the full run.

**Measurements.** [`summarize.py`](summarize.py).

- **Recall@K** (the verdict's measure). The chunks the retriever returns, with the 30 overlap words each
  begins with, cover at least 50% of the words of CUAD's answer span. Chunk text is placed in the
  contract by counting characters that are not whitespace, since the sentence splitter sometimes cuts
  inside a word.
- **Descriptive:**
  - recall@1 and recall@5;
  - the share of items where the span is covered at least 90% (full) or at all (any overlap);
  - mean coverage and the words the model would read (median over items);
  - an oracle: the best 3 chunks by overlap with the span, an upper bound for any ranker at this chunking;
  - recall per category and macro-averaged over categories;
  - per-chunk embed time for `nl` and `eg` (median, mean, 95th percentile) and seconds per contract;
  - `eg` tokens and truncated chunks; `nl` chunks with no vector; detected languages;
  - score spread per item: top score minus median, and maximum minus minimum.
- **Not registered, labelled so in the write-up:** the semantic weight swept over 0.5, 0.7, 0.9 and 1.0
  for each backend.

## Decision rule

The idea under test is **keeping EmbeddingGemma retrieval on in Xylo**. The rule compares `eg-hybrid` with
`nl-hybrid` on recall@3. Apply the steps in order; the first match wins.

1. If the gain is less than 3 points, the verdict is **reject: no gain**. The 334 MB download is not paying
   for itself, and the lab recommends turning the flag off.
2. Check two criteria:
   - **c1:** the gain is at least 5 points, and the lower bound of the 95% confidence interval is above 0.
     The interval comes from a contract-level paired bootstrap with 10,000 resamples and seed 0: contracts
     are resampled with all their items.
   - **c2:** the median EmbeddingGemma embed time is at most 50 ms per chunk on the host.
3. If c1 and c2 hold, the verdict is **adopt (host stage)**. The lab recommends keeping the shipped
   default. Xylo would confirm it on a phone, where memory and time differ, before treating it as settled.
4. If c1 holds and c2 fails, the verdict is **reject: cost**.
5. Otherwise the verdict is **inconclusive**, naming the failing criteria.

H2 and H3 never change the verdict. They say where a gain comes from, or whether NLEmbedding adds anything.

## Results

Run 2026-10-08 (UTC) on the host above, on AC power, from commit `b70b3e3` with no tracked file
changed. Scoring took about 41 minutes: keyword scores under a minute, NLEmbedding about 27 minutes,
EmbeddingGemma about 14. Every number here is MEASURED on the host unless tagged otherwise. Raw files
are in [`results/raw`](results/raw):

- `items.jsonl`: the 1,325 items;
- `scores-kw.jsonl`, `scores-nl.jsonl`, `scores-eg.jsonl`: every chunk's score for every item;
- `scores-bm25.jsonl` and `chunks-index.jsonl`: written by `index.py`;
- `timing-nl.jsonl` and `timing-eg.jsonl`: per-chunk embed times;
- `conditions.txt` and the three `harness-*.log` files.

The tables below come from [`results/summary.md`](results/summary.md), which `summarize.py` generates
along with [`results/summary.json`](results/summary.json). The run covered 1,325 items, 397 contracts
and 79,037 chunks. EmbeddingGemma embedded 7,998,925 tokens; 3 chunks were over 2,048 tokens and were
truncated. NLEmbedding returned a vector for every chunk.

**Recall of the answer-bearing text** (percent of items; recall = the retrieved chunks, overlap
included, cover at least 50% of the answer span's words):

| Arm | recall@1 | recall@3 | recall@5 | full@3 | any overlap@3 | mean coverage@3 | median words read@3 |
|---|---|---|---|---|---|---|---|
| `nl-hybrid` (control) | 21.7 | 35.2 | 42.4 | 33.4 | 37.9 | 35.4 | 279 |
| `eg-hybrid` | 44.5 | **61.4** | 67.5 | 60.1 | 62.8 | 61.4 | 331 |
| `nl-only` | 3.9 | 9.7 | 15.3 | 8.5 | 11.0 | 9.8 | 156 |
| `eg-only` | 42.0 | 60.6 | 69.1 | 58.3 | 62.2 | 60.4 | 292 |
| `kw-only` | 32.2 | 46.6 | 52.9 | 44.9 | 47.8 | 46.2 | 358 |
| `bm25` (reference) | 32.5 | 46.4 | 54.6 | 44.9 | 48.4 | 46.5 | 263 |
| oracle (best 3 chunks) | | 100.0 | | 99.8 | | | |

The oracle shows that, at this chunking, three chunks can hold the answer span for every item. The
best arm reaches 61% of that.

**Decision rule.** `eg-hybrid` minus `nl-hybrid`, recall@3: **+26.2 points, 95% CI [+23.8, +28.5]**
(contract-level paired bootstrap, 10,000 resamples, seed 0). Step 1 passed (the gain is above 3
points). c1 holds (gain at least 5 points, lower bound above 0). c2 holds: the median EmbeddingGemma
embed time is 8.9 ms per chunk, against a limit of 50 ms.

**Hypotheses.**

1. **H1, held.** `eg-hybrid` is 26.2 points above `nl-hybrid` (threshold 5), CI [+23.8, +28.5].
2. **H2, held.** `eg-only` is 50.9 points above `nl-only` (threshold 10), CI [+48.3, +53.5].
3. **H3, held, and more than the threshold needs.** `nl-hybrid` is not within 5 points above
   `kw-only`: it is 11.3 points below it, CI [-13.7, -8.9]. At Xylo's weights, adding the NLEmbedding
   score to the keyword score makes retrieval worse than the keyword score alone.

**Per category, recall@3** (percent; `n` items each, 100 unless shown):

| Category | n | `nl-hybrid` | `eg-hybrid` | `nl-only` | `eg-only` | `kw-only` | `bm25` |
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

`eg-hybrid` is above `nl-hybrid` in all 14 categories, by 4 points (Exclusivity) to 59 points (Notice
Period To Terminate Renewal). It is not the best arm everywhere: `kw-only` is higher on Agreement Date
(37 against 28), `bm25` on Audit Rights (70 against 62) and Exclusivity (11 against 5), and `eg-only`
is higher on Non-Compete (38 against 25). Exclusivity is low for every arm (at most 11%), and
Agreement Date and Non-Compete are the other weak ones for `eg-hybrid`. Each category has at most 100
items, so differences of a few points inside one category are within noise (no per-category interval
was computed).

**Embedding cost on the host.**

| Backend | chunks | median ms | mean ms | p95 ms | median seconds per contract |
|---|---|---|---|---|---|
| `nl` | 79,037 | 14.5 | 20.2 | 51.8 | 2.7 |
| `eg` | 79,037 | 8.9 | 10.6 | 19.1 | 1.4 |

On this host EmbeddingGemma embeds a chunk faster than NLEmbedding does, not slower. The harness
logged its own peak resident memory: 181 MB for the keyword pass, 672 MB for `nl` and 1,822 MB for
`eg` (OBSERVED; not a registered measure, and the process also holds the contracts and chunks, so
it is not the app's footprint). EmbeddingGemma loaded in 333 ms.

**Score spread** (per item, over all chunks of the contract; median over items):

| Backend | top score minus median score | maximum minus minimum |
|---|---|---|
| `nl` | 0.230 | 0.507 |
| `eg` | 0.236 | 0.446 |

By this measure the two backends are alike: the best chunk stands out from the median by the same
amount, and `nl`'s overall range is if anything wider. The spot-check's account (EmbeddingGemma
separating the best chunk, NLEmbedding clustered) is not visible here. That account was about
absolute score levels on 19 chunks of dense documents, which this table does not compare, and the
recall gain comes from ranking, which a spread cannot show.

**Languages.** NLEmbedding's detection called 1,298 of the 1,325 items English and 27 other (Indonesian
11, Catalan 8, German 3, Dutch 3, Romanian 2). The questions are English throughout.

**Exploratory: semantic weight** (added to `summarize.py` before the run and listed under Measurements
as not registered; recall@3 in percent, one run, no intervals):

| Semantic weight | 0.5 | 0.7 (Xylo) | 0.9 | 1.0 |
|---|---|---|---|---|
| `nl` | 42.6 | 35.2 | 18.6 | 9.7 |
| `eg` | 57.2 | 61.4 | 62.5 | 60.6 |

- `nl` improves as its weight falls, and at 0.5 is still below `kw-only` (46.6). The NLEmbedding
  score does not add to the keyword score at any weight tried.
- `eg` is flat near its top: 0.9 is 1.1 points above 0.7, which this run does not separate from noise.
  `eg-only` (60.6) is within a point of `eg-hybrid` (61.4), so the keyword score adds little on top
  of EmbeddingGemma, and in some categories (Non-Compete) it takes away.

## Verdict

**Adopt (host stage)** (decision rule, step 3). On 1,325 answerable contract questions over 397
contracts, Xylo's retrieval with EmbeddingGemma puts at least half of the answer text in the top 3
chunks for 61% of items, against 35% with NLEmbedding, a gain of 26 points (CI +24 to +29). The gain
holds in every category. EmbeddingGemma's median embed time on the host, 8.9 ms per chunk, is below
NLEmbedding's.

The lab recommends keeping Xylo's shipped default, `embeddingGemmaRetrieval` on. No change to Xylo
follows from this PoC. Under the rule, a phone run confirms it before it is treated as settled.

Two findings go beyond the registered question (MEASURED, with the reading INFERRED):

- **NLEmbedding, as the fallback, is worse than no embedding in this harness.** `nl-hybrid` (35%) is
  below `kw-only` (47%) and `nl-only` finds the answer text in 10% of items. A device that falls back
  to NLEmbedding may retrieve less well than one that used the keyword score alone. Whether the
  fallback should drop the embedding term, or use a lower weight, is untested on the device and is a
  Xylo question (see Limits: the fallback here is simplified).
- **The remaining misses are not explained here.** The oracle reaches 100%, and `eg-hybrid` 61%.
  Exclusivity, Agreement Date and Non-Compete stay low for every arm. Whether that is the question
  wording, the chunking or the approach is not tested (HYPOTHESIS).

This verdict is for the host. On an iPhone it is INFERRED: the weights, chunker and embeddings are the
same code, but time and memory differ, and the 1.8 GB peak above is a figure for the Mac harness.

**What this points to next** (HYPOTHESIS).

- **A phone run** of the `eg` and `nl` embed times and memory with the chat model loaded.
- **A fallback check.** Compare `nl-hybrid` with `kw-only` on a device with the Xylo app's real
  fallback, which is not the simplified one used here.
- **The weight.** A registered sweep of the semantic weight with held-out categories, if the
  exploratory table is to guide a change. The 0.9 gain above is within noise.
- **Question wording.** Several questions per category, as the Limits note.

## Deviations

- **`index.py` did not run inside `run.sh`.** The last line of the script failed with "Fatal Python
  error: init_sys_streams ... Bad file descriptor" after both `Scores` passes had completed and the
  outputs were intact. The script had been started as a background job from a terminal, and the
  likely cause is that its standard input was no longer valid by then (INFERRED; not reproduced).
  `python3 index.py results/raw` was then run by hand, exactly as the script calls it, followed by
  `python3 summarize.py`. Nothing in the data changed. The script now starts with `exec </dev/null`
  so a background run does not depend on its terminal; that edit was made after the run and was
  checked with `bash -n` only.
- **Memory figures** (peak resident size per pass) are reported although they are not in the
  registered measurements. They come from the harness logs and did not affect the verdict.

## Errata

- **2026-10-09: Xylo's keyword tables moved to a private overlay.** The stopword and suffix tables are confidential and are no longer in the harness source. `Scores --mode kw` loads them from the JSON file given by `--keywords`; `run.sh` passes `private/keywords.json`, which is gitignored, or the generic stand-in `generic/keywords.json` with a warning. The registered table has SHA-256 `8a94c8b3aa13937c7bf4c98c5c0f4670cad6141946f55c9fb25c99ac425b0e8d`. Re-running `--mode kw` with it on 2026-10-09 gave a `scores-kw.jsonl` byte-identical to the committed one. A different table changes the keyword scores, so a replication with the stand-in tests a similar keyword scorer, not Xylo's. Whether the original tables can be shared with a reviewer is the author's decision. The verdict and results are unchanged.

## Limits

- **Mac, not iPhone.** Time and memory on an A-series chip, with a 6 GB or 8 GB budget shared with the
  chat model, may differ. c2 is a host criterion only. Recall should carry over, as the same weights and
  the same OS embedding run on both (INFERRED).
- **CUAD is flat text.** Pages are approximate (500 words), and the page-diversity penalty acts on them.
  Real PDFs have real pages, headings, tables and lists that Xylo's chunker treats specially.
- **Natural-language questions only,** one per category. A user's real questions vary more.
- **First answer span only.** Some contracts state the answer in several places, and retrieving another
  place also helps the model. This under-counts recall equally for both backends.
- **A span in the text is not an answer.** Recall measures whether the right words reach the model, not
  whether it uses them. PoC 006 takes up the model's side.
- **Language.** English contracts only. Detected languages are reported, but NLEmbedding's non-English
  models and EmbeddingGemma's multilingual strength are not tested.
- **NLEmbedding fallback simplified** (null score, see Scores).
- **Single turn.** No follow-up questions, so no exclusion of chunks already used.
- **Chunker and retriever are paraphrases** of the app's. A difference in a detail could shift recall for
  both backends. The same chunks and retriever are used for both, so the comparison is fair, but absolute
  recall is the harness's.
- **PoC 006 uses different sections.** It fixes them with BM25 windows so the model comparison is not
  retrieval-dependent. Recall here is not recall there.

## Reproduce

From a clean checkout on an Apple silicon Mac with macOS 26.4 or later and Xcode 26:

```sh
cd poc/007-embedding-retrieval-recall
./run.sh          # downloads the model if missing, verifies hashes, builds, runs
python3 summarize.py
```

`results/raw/contracts.jsonl` (26 MB) and `chunks.jsonl` (37 MB) hold contract text and are not
committed. `prepare.py` and `Chunker` rebuild them from the CUAD zip, and `conditions.txt` records their
hashes. `chunks-index.jsonl` carries every chunk's word range and page, which is all `summarize.py` needs.

## Replications

A replication needs an Apple silicon Mac and about 2 GB of free memory. Point the run at a replication
folder with `OUT=replications/<name>/results/raw ./run.sh`, and summarize with
`python3 summarize.py replications/<name>/results/raw`. An iPhone replication needs an app harness that is
not in this repository yet.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| | | | |
