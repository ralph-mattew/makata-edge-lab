# PoC 009: How many retrieved sections Qwen2.5-1.5B should read

| | |
|---|---|
| Status | Planned |
| Verdict | None yet |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet (founding reviewers being invited) |
| Source idea | Two statements in Xylo's engineering notes (private app, v1.2.0): cutting the chat retrieval depth from 5 chunks to 3 lost little grounding and roughly halved prefill time, and for the quantized 1.5B model a focused context beats a maximal one. |
| Registered | 2026-10-09, in the commit that adds this file, before the first run |

## Question

On contracts too long to read whole, with the retrieval Xylo runs, does giving Qwen2.5-1.5B the 5
best chunks instead of the 3 it gets today raise how often its answer contains the right key fact,
and does the gain justify the longer prompt?

## Why it matters here

Xylo's 6 GB iPhones answer questions about a document with Qwen2.5-1.5B, in a 2,048-token context.
When a document is too long to read whole (above 800 words on Qwen), the app retrieves the best
chunks and puts them in the prompt. Its chat path takes 3.

Xylo's notes give two reasons for 3, both from device testing during development, with no
measurement published:

1. Going from 5 chunks to 3 cost little grounding, because the dropped chunks scored near zero, and
   roughly halved prefill, which is the app's latency bottleneck.
2. For the 1.5B model, a focused context beats a maximal one: handing it a much larger share of the
   document degraded its output, even when everything fit in the window.

[PoC 007](../007-embedding-retrieval-recall) measured how often those 3 chunks hold the answer
(MEASURED on the host: 61.4% of items with EmbeddingGemma, 35.2% with NLEmbedding) and found that
5 chunks hold it more often (67.5% and 42.4%). [PoC 006](../006-doc-qa-fm-gemma-qwen) measured
Qwen's answers when the answer is always in front of it. Nothing yet joins the two: whether the
extra chunks, once in the prompt, turn into more right answers from this model, or into noise.

The room for gain is small and known before any model runs. On the 464 items scored by key fact
below, 5 chunks hold the answer on 83.0% against 77.6% for 3 (MEASURED in a dry run of
`prepare.py`, no model run): at most 5.4 points more items can be answered from the text, and fewer
if the model does not use it. A prompt with 5 chunks is also longer, which Xylo's notes say it pays
for in prefill. So this PoC measures both sides of a trade the app already made once by feel.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items. "Key fact right" is defined
under Measurements. Depths are written `k1`, `k3` and `k5`; `eg` is EmbeddingGemma retrieval and
`nl` is NLEmbedding retrieval, each as in PoC 007's `eg-hybrid` and `nl-hybrid`.

1. **H1** (Xylo's first statement). Key fact right with `eg-k5` is less than 1.5 points above
   `eg-k3`'s: going back to 5 chunks gains almost nothing.
2. **H2** (Xylo's second statement). On the items where the 3 chunks already hold the answer,
   `eg-k5` has a key-fact rate at least 2 points below `eg-k3`'s: the extra text distracts.
3. **H3** (the other end). Key fact right with `eg-k1` is at least 10 points below `eg-k3`'s: a
   single chunk is too few, so "focused" has a limit.

Also descriptive: the same comparisons with NLEmbedding, the effect on prompt tokens and prefill
time, and what the model does when the answer is not in the chunks.

## Method

**Host.** MacBook Pro (Mac16,8), Apple M4 Pro, 24 GB, macOS 26.5.1 (25F80), on AC power.

**Model.** Qwen2.5-1.5B-Instruct, Q4_K_M, `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`, SHA-256
`1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370`, Apache-2.0. The file of PoCs 003
to 008. It is the only chat model on the 6 GB tier. Gemma and FoundationModels are not run: they
read 3 chunks on their tiers, and their prompts and contexts differ.

**Tooling.** llama.swift 2.8901.0 (llama.cpp b8901, Metal), the build Xylo ships; Swift 6.3.3. The
harness is PoC 006's `GGUFQA`, unchanged.

**Settings.** The `qwen-1.5b` arm of [`arms.json`](arms.json), a byte-for-byte copy of PoC 006's:
context 2,048, `n_ubatch` 128, 2 threads, all layers on the GPU, flash attention off, seed 1,
temperature 0.7, top_p 0.8, top_k 20, repeat penalty 1.05, presence penalty 1.5 over 256 tokens,
200 new tokens, stop on end-of-sequence or `<|im_end|>`.

**Items.** PoC 007's 1,325 items, from 397 CUAD v1 contracts of at least 1,800 words (CC BY 4.0, the
zip PoCs 003 and 006 to 008 use, SHA-256 `88b694d9…d18e`). Each is a plain question about one of 14
contract categories, and CUAD marks an answer span of at most 150 words in the contract. The items,
the questions and the chunk index are PoC 007's committed files; the SHA-256 of each is recorded in
`conditions.txt`. Only answerable items are used: retrieval can be right or wrong only when there is
an answer. What the model does when there is none is PoC 006's and PoC 008's question.

**Retrieval.** PoC 007's committed scores for every chunk of every contract, run through its
`retrieve`, which is Xylo's retriever as PoC 007 describes it: hybrid score (0.7 semantic, 0.3
keyword), the top K + 4, a proximity boost, a page-diversity penalty, the top K. The chunks are PoC
007's, with their 30-word overlap. This PoC does not rerun any embedding.

**Conditions.** One run of all 1,325 items each:

| Condition | Retrieval | Chunks in the prompt |
|---|---|---|
| `eg-k3` | EmbeddingGemma hybrid | 3. The control: Xylo's chat path |
| `eg-k5` | EmbeddingGemma hybrid | 5 |
| `eg-k1` | EmbeddingGemma hybrid | 1 |
| `nl-k3` | NLEmbedding hybrid | 3. The fallback path |
| `nl-k5` | NLEmbedding hybrid | 5 |

**Prompts.** PoC 006's Qwen chat prompt for a first turn, from `DocumentChatEngine` in Xylo v1.2.0:
ChatML, Xylo's system instruction with `/no_think`, a user turn holding the sections and the
question, then the assistant turn, built by 006's `prompts()`. The sections are listed in document
order, each under a `[Page N]` header with the chunk's page. A chunk's text is its words, in the
contract's order, joined with single spaces. The document summary and KEY DETAILS parts are left out,
as in PoC 006, so that the chunks are the only evidence. The instruction text is private; see PoC
006's Errata.

**Word cap.** A prompt's chunks may hold at most 1,000 words, overlap included. When the chunks
exceed it, the lowest-ranked chunks are dropped, whole, until they fit. A dry run of `prepare.py`
(no model run) shows the cap binds on 1 item of `eg-k3`, 32 of `eg-k5` (44 chunks), and 25 of
`nl-k5`. It exists so that a prompt always fits the 2,048-token context with the full 200-token
answer: a smoke test on the 40 largest `eg-k5` prompts (before registration) gave at most 1,604
prompt tokens and no shortened answer budget. Xylo's own limit for this is not published; the cap
is this PoC's.

**Order.** [`run.sh`](run.sh) checks the model and data hashes, builds 006's harness, rebuilds the
inputs, then runs the five conditions in the order `eg-k3`, `eg-k1`, `eg-k5`, `nl-k3`, `nl-k5` (run
1), and then `eg-k3` and `eg-k5` again with seed 2 (run 2). Run 1 is the result. Run 2 only shows how
much a gain moves between seeds. The host is kept awake with `caffeinate`, and the script warns if the
host is not on AC power. Nothing else is run on the host during the stages, because c3 compares
prefill times. A smoke test before registration ran the pipeline on 60 items per condition, with
other work running on the host; its numbers are not used, and its prefill times are not representative.

**Measurements.** [`summarize.py`](summarize.py) scores each output with PoC 008's scoring, which
is PoC 006's with the corrected detector, imported unchanged.

- **Key fact right** (the measure of the verdict). On items in six categories where CUAD's span has
  a parsable fact, whether the answer, after the app's clean-up, contains that fact: a date for
  Agreement Date, a jurisdiction for Governing Law, a duration for Renewal Term, Notice Period and
  Warranty Duration, and a date or duration for Expiration Date. The parsers are PoC 006's
  [`facts.py`](../006-doc-qa-fm-gemma-qwen/facts.py). **464 of the 1,325 items** have one (MEASURED
  in the dry run: Notice Period 95, Governing Law 93, Renewal Term 91, Agreement Date 84, Expiration
  Date 61, Warranty Duration 40), from 281 contracts. This is the only measure of correctness the
  lab has for these questions that does not depend on a reader.
- **Any unsupported number.** The share of outputs with a number of two or more digits that is not
  in the prompt's chunks or the question (PoC 003's measure).
- **Prefill time.** The harness's own timer for prefilling the prompt, in milliseconds, and the
  prompt's token count.
- **Recall** of a condition: the share of items where its chunks cover at least half of CUAD's span
  (PoC 007's measure, with the word cap applied).
- **Descriptive only:** the answer-or-absent call by detector v2 (answers, says absent), the split
  of key fact right by whether the chunks cover the answer, hitting the answer budget, median answer
  length and time, per-category rates, and run-to-run agreement. The verdict does not use the
  detector, so this PoC has no audit sheet.

**Intervals.** A contract-level bootstrap with 10,000 resamples and seed 0: contracts are resampled
with all their items, and every compared quantity is recomputed on each resample.

## Decision rule

The idea under test is **raising the number of chunks Xylo puts in Qwen2.5-1.5B's chat prompt from
3 to 5 for documents too long to read whole**. The rule compares `eg-k5` with `eg-k3` on run 1. Apply
the steps in order; the first match wins. The thresholds follow the room for gain described under
Why it matters here: key fact right cannot rise by more than the 5.4 points of extra recall.

1. If `eg-k5`'s key-fact rate is less than 1.5 points above `eg-k3`'s, the verdict is **reject: no
   gain**. Xylo keeps 3 chunks.
2. Check three criteria:
   - **c1:** `eg-k5`'s key-fact rate is at least 3 points above `eg-k3`'s, and the lower bound of
     the 95% confidence interval of the difference is above 0.
   - **c2:** the share of outputs with an unsupported number rises by no more than 3 points.
   - **c3:** the median prefill time of `eg-k5` is at most 2.0 times `eg-k3`'s.
3. If c1 to c3 all hold, the verdict is **adopt (host stage)**. The lab then recommends 5 chunks for
   Qwen where EmbeddingGemma retrieval runs. Xylo would make that change only after an iPhone run
   that measures prefill time, memory and heat on the device.
4. If c1 holds but c2 or c3 fails, the verdict is **reject: trade-off**.
5. Otherwise the verdict is **inconclusive**: the gain is between 1.5 and 3 points, or its interval
   includes zero.

The same rule, applied to `nl-k5` against `nl-k3`, gives a second verdict for the fallback path, which
runs when EmbeddingGemma is not loaded. It never changes the headline. H1 to H3 are reported as
holding or not, and do not change the verdict.

## Results

Not run yet.

## Verdict

Not run yet.

## Deviations

None yet.

## Limits

Written before the run.

- **Answerable items only.** The PoC says how much more of the right answer 5 chunks bring, not what
  they do to gap filling. More text means more material for a related but wrong answer when the
  clause is absent; [PoC 006](../006-doc-qa-fm-gemma-qwen) and [PoC 008](../008-absence-instruction-doc-qa)
  measure the absent side at 3 chunks only. An adopt here would still need that check.
- **The ceiling is low.** At most 5.4 points of key-fact items gain the answer. A real gain of 2 or
  3 points is within what one run and one sample of 464 items can show only loosely, and the interval
  is likely to be wide. Run 2 shows part of the seed noise.
- **Key fact is six categories.** The other eight categories are scored only as answered or absent,
  which does not separate right from wrong.
- **PoC 007's chunker, not the app's.** CUAD has no page breaks, so pages are cut at about 500 words,
  and chunk text is rejoined words, not the original paragraphs. Chunks are short (median 25 words of
  their own), so 5 chunks are often a small prompt.
- **The word cap is this PoC's.** It affects 32 of 1,325 `eg-k5` prompts; the app's own budget may
  differ.
- **Mac, not iPhone.** Prefill time on the host's Metal GPU is not an iPhone's. A ratio between
  conditions is more portable than a number of milliseconds, but is not the same either.
- **Not the app's full prompt, single turn, CUAD's labels.** As in PoC 006: no document summary or
  KEY DETAILS, one question per prompt, and CUAD's annotations as the gold spans.
- **One sampler seed in the verdict.** Run 2 repeats two conditions; it does not enter the rule.
- **The prompt may differ in a replication.** Without the private overlay, the system instruction is
  a generic stand-in with the same structure.

## Reproduce

From a clean checkout on an Apple silicon Mac with macOS 26.4 or later and Xcode 26:

```sh
cd poc/009-retrieval-depth-qwen
# the model and data: run.sh prints the download commands if they are missing;
# on APFS, cp -c from PoC 006's models/ and data/ clones them
./run.sh
python3 summarize.py
```

`results/raw/inputs-<condition>.jsonl` (the prompts) is not committed; `prepare.py` rebuilds it byte
for byte from the CUAD zip, PoC 007's committed files and the overlay or stand-in, and
`conditions.txt` records the SHA-256 of each. The PoC needs PoC 006's folder (its harness, `prepare.py`,
`facts.py` and `summarize.py`), PoC 007's `results/raw`, and PoC 008's `summarize.py`.

## Replications

A replication needs an Apple silicon Mac and about 4 GB of free memory. Point the run at a replication
folder with `OUT=replications/<name>/results/raw ./run.sh`, and summarize with
`python3 summarize.py replications/<name>/results`.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| | | | |
