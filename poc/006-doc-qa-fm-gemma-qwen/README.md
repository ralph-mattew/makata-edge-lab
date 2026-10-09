# PoC 006: Contract questions on FoundationModels, Gemma 4 E2B and Qwen2.5-1.5B

| | |
|---|---|
| Status | Written up (host stage) |
| Verdict | Adopt (host stage): Gemma 4 E2B beats FoundationModels on balanced accuracy by 14.5 points (95% CI +11.3 to +17.6), mainly by saying "absent" on 65% of unanswerable items against 39% |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet (founding reviewers being invited) |
| Source idea | Two claims in Xylo's engineering notes (private app, v1.2.0): the quantized 1.5B model fills gaps in the document with invented answers, and the capable tiers, Gemma E2B and FoundationModels, mostly do not |
| Registered | 2026-10-09, in the commit that adds this file, before the first run |

## Question

Given the same three document sections and Xylo's chat prompt, how often does each of Xylo's
three chat backends answer a contract question when the answer is in the sections, and say so
when it is not? The backends are Apple's on-device FoundationModels, Gemma 4 E2B and
Qwen2.5-1.5B, each at the settings Xylo ships for its tier.

## Why it matters here

Xylo answers questions about a document with one of three backends, picked by device memory:

- **8 GB iPhones with Apple Intelligence** use FoundationModels by default. Users can switch to
  Gemma 4 E2B, a 3.5 GB download.
- **8 GB devices without Apple Intelligence** use Gemma 4 E2B.
- **6 GB iPhones** use Qwen2.5-1.5B, the only model that fits next to the rest of the app.

Xylo's notes rank them: the 1.5B model fills gaps with invented answers, while Gemma and FoundationModels are described as mostly unaffected. Those statements come from device testing
during development. No measurement behind them is published, and they shape two choices:

1. **The 8 GB default.** If Gemma answers grounded questions clearly better than
   FoundationModels, the download may be worth asking for. If not, FoundationModels stays the
   default and costs no download.
2. **The 6 GB tier.** If Qwen does fill gaps, the 6 GB tier needs a guard before its answers
   can be trusted. The size of the gap decides how strong that guard has to be.

The lab has no number for either yet. This PoC holds retrieval fixed, so the difference left is
the model, its prompt format and its settings.

## Hypotheses

All HYPOTHESIS until measured. "Says absent" and "answers" are the detector's two calls, defined
under Measurements. A point is a percentage point of items.

1. **H1** (the gap-filling claim). On unanswerable items, Qwen says absent at least 15 points
   less often than FoundationModels, and at least 15 points less often than Gemma.
2. **H2** (the same claim, for numbers). Qwen's outputs contain an unsupported number at least
   5 points more often than FoundationModels' and than Gemma's.
3. **H3** (the capable-tiers claim). FoundationModels and Gemma are within 10 points of each
   other on balanced accuracy.

## Method

**Host.** MacBook Pro (Mac16,8), Apple M4 Pro, 24 GB, macOS 26.5.1 (25F80), on AC power.
FoundationModels runs the on-device model the host's macOS ships. The iPhone model may differ;
see Limits.

**Models.**

| Arm | Model | File and SHA-256 | License |
|---|---|---|---|
| `fm` | Apple FoundationModels, system model | Ships with macOS 26.5.1 (25F80); no file | Apple SDK terms |
| `gemma-e2b` | Gemma 4 E2B instruct, Q4_K_M | `google_gemma-4-E2B-it-Q4_K_M.gguf` from [bartowski/google_gemma-4-E2B-it-GGUF](https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF) at revision `81012ba`, SHA-256 `923c4c86177d2ee173a7f5b4fa3d0ac65f5962ab15e6d6a5bc250aec4fd7bf7e`. The file Xylo downloads, and PoC 001's | Apache-2.0 (Gemma 4) |
| `qwen-1.5b` | Qwen2.5-1.5B-Instruct, Q4_K_M | `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`, SHA-256 `1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370`. PoC 003's file | Apache-2.0 |

**Tooling.** llama.swift 2.8901.0 (llama.cpp b8901, Metal), the build Xylo ships; Swift 6.3.3;
the macOS 26.5 SDK for FoundationModels.

**Items.** From CUAD v1 (CC BY 4.0, the zip PoC 003 uses, SHA-256
`88b694d9…d18e`). [`prepare.py`](prepare.py) builds them; the same zip always gives the same
files.

- **Contracts.** The 427 of 510 contracts with at least 1,800 words. Above Xylo's whole-document
  limits (800 words on 6 GB, 1,100 on 8 GB), so every tier answers from its top 3 sections, as it
  would for these contracts in the app.
- **Questions.** 14 CUAD categories, each asked as one plain question a user might type, listed
  in [`questions.json`](questions.json). CUAD's own category descriptions read as annotation
  guidelines, so they are not used as questions. The categories are the ones a user would ask a
  contract about where CUAD marks the answer as present in some contracts and absent in others:
  dates and terms, renewal and notice, governing law, warranty, termination for convenience,
  non-compete, exclusivity, change of control, audit rights, insurance, liability cap and
  liquidated damages.
- **Answerable and unanswerable.** CUAD marks each (contract, category) pair as having an answer
  span or not. An item is answerable when CUAD gives a span, and unanswerable when it marks the
  clause as absent from the whole contract. Answerable items whose first span is longer than 150
  words are left out, so the span fits in one section.
- **Sample.** For each category, 36 answerable and 36 unanswerable items are drawn at random
  (seed 6), or all of them if fewer exist. Agreement Date has 29 unanswerable items and Governing
  Law 21. That makes **986 items: 504 answerable, 482 unanswerable, from 392 contracts.** The
  order is shuffled once with the same seed.

**Sections.** Xylo retrieves the top 3 chunks of about 175 words on the 6 and 8 GB tiers. This
PoC fixes the sections instead, so every backend sees the same text:

- The contract's words are cut into consecutive 175-word windows.
- An answerable item gets the window that contains CUAD's first answer span. If the span crosses
  a window boundary, a 175-word window centred on the span is used instead. The other two
  sections are the two windows that score highest against the question by BM25 and do not
  overlap the first.
- An unanswerable item gets the three highest-scoring BM25 windows.
- Sections appear in document order. Each has the header `[Page N]`, with N = 1 + its first word
  index ÷ 500, since CUAD's text has no page breaks.

So on answerable items retrieval never fails: the answer is in front of the model. This is the
easy case for retrieval and the hard case for refusing. A backend that says absent here is wrong.

**Prompts.** Each backend gets the prompt Xylo builds for a first chat turn in top-3 mode, from
`DocumentChatEngine` in Xylo v1.2.0:

- **System instruction.** Xylo's chat instruction, unchanged, in all three. It tells the model to answer using only the provided sections and to say so in one sentence when the question cannot be answered from them. The text is not published; see Errata.
- **Gemma.** Gemma 4's turn format: a user turn holding the system instruction, the sections and
  `Question: …`, then the model turn. The prompt is split where Xylo splits it for its prefix
  cache: the part before the sections is tokenized with BOS, the rest without, and the two are
  joined.
- **Qwen.** ChatML: the system instruction with `/no_think` as the system turn, then a user turn
  with the sections and the question, then the assistant turn. Split and tokenized the same way.
- **FoundationModels.** A new `LanguageModelSession` per item. Its instructions are the system
  instruction, the one-line lead-in Xylo puts before the sections (text not published; see
  Errata) and the sections. The prompt is the bare question.
- **Left out, in all three.** Xylo also sends a document summary of up to 120 (Qwen) or 200
  words, and a KEY DETAILS block of extracted names, dates and amounts. Both come from earlier
  steps of Xylo's pipeline with their own model calls, and both can carry the answer. They are
  left out so that the sections are the only evidence; their parts are removed and the rest is
  joined as the app joins it.

**Arms.** In [`arms.json`](arms.json), each at the settings Xylo ships for its tier:

| Arm | Tier | Context | Answer budget | Sampler | Stop |
|---|---|---|---|---|---|
| `fm` | 8 GB, default | Framework (4,096 on the host) | 500 tokens | temperature 0.3, default sampling mode; guardrails `permissiveContentTransformations` | Framework |
| `gemma-e2b` | 8 GB | 2,500, `n_ubatch` 256 | 200 tokens | temperature 0.6, top_p 0.95, top_k 64, repeat penalty 1.0 over 64 tokens, no frequency or presence penalty | end-of-sequence or `<turn\|>` |
| `qwen-1.5b` | 6 GB | 2,048, `n_ubatch` 128 | 200 tokens | temperature 0.7, top_p 0.8, top_k 20, repeat penalty 1.05, presence penalty 1.5, over 256 tokens | end-of-sequence or `<\|im_end\|>` |

Both GGUF arms: 2 threads, all layers on the GPU, flash attention off, `n_batch` equal to the
context, seed 1. The token budgets are Xylo's at nominal thermal state.

**Harness.** [`harness/`](harness) has two programs:

- **`GGUFQA`** is PoC 005's loop without its interventions, with each arm's settings read from
  `arms.json`. It runs Xylo's chat generation loop with a fixed sampler seed. The prompt is
  prefilled in one batch rather than prefix and then suffix; the tokens and positions are the
  same.
- **`FMQA`** runs FoundationModels with Xylo's options and streams the answer. It records the
  time to the first text and errors such as guardrail violations.
  - The framework's default sampling mode takes no seed, so FoundationModels answers cannot be
    rerun token for token. Run 2 measures how much they move.
  - Left out from the app: its repetition-loop break, its retry when the context window is
    exceeded, and its answer clean-up (deduplication and trimming). These rarely fire on a
    single short turn, and none of them changes whether an answer says absent.

Both programs come from reading Xylo's source. No Xylo code is in this repository.

**Order.** [`run.sh`](run.sh) checks the model and data hashes, then runs:

1. Run 1: all 986 items through `gemma-e2b`, `qwen-1.5b` and `fm`, in that order.
2. Run 2: the same, with seed 2 for the GGUF arms and a second pass for `fm`.

Run 1 is the result. Run 2 only measures run-to-run agreement. The host is kept awake with
`caffeinate`, and the script warns if the host is not on AC power.

A smoke test before registration ran each arm on four questions about a made-up services
agreement that is not in CUAD. All three ran to a normal end: Gemma on `<turn|>`, Qwen on
end-of-sequence, and FoundationModels without an error.

**Measurements.** [`summarize.py`](summarize.py) scores run 1, after the clean-up the app
applies before showing an answer (Gemma control tokens removed, Qwen `<think>` blocks removed).

- **Says absent or answers.** A detector reads the answer's first sentence, after a leading list
  marker. It calls the answer **absent** if that sentence starts with "No" or "None", or says the
  document or sections do not mention, specify, state or contain the information. Phrases like
  "not specified", "there is no …", "no mention of …" and "cannot be determined" also count. Any
  other non-empty answer is an **answer**. The patterns are frozen in `summarize.py`. Errors and
  empty outputs are neither.
- **Answer rate.** The share of answerable items the backend answers.
- **Absent rate.** The share of unanswerable items where it says absent. One minus this is the
  rate at which it fills the gap.
- **Balanced accuracy.** The mean of the answer rate and the absent rate. It weights the two
  classes equally even though their counts differ.
- **Key fact right.** On answerable items in six categories, whether the answer contains a fact
  from CUAD's span: a date for Agreement Date, a jurisdiction for Governing Law, a duration for
  Renewal Term, Notice Period and Warranty Duration, and a date or duration for Expiration Date.
  - Dates are matched on day, month and year. Durations are matched on length, with years and
    months treated alike (12 months is one year). Jurisdictions are matched on a list of US
    states, Canadian provinces and countries. The parsers are in [`facts.py`](facts.py).
  - Spans with no parsable fact are left out. Calibrated on the gold spans before registration:
    181 of the 216 answerable items in these categories have one. By category: Governing Law
    35/36, Notice Period 34/36, Renewal Term 32/36, Agreement Date 31/36, Expiration Date 27/36,
    Warranty Duration 22/36.
- **Any unsupported number.** The share of outputs with a number of two or more digits that is
  not in the sections or the question. This is PoC 003's measure, reported over all items and
  over unanswerable items.
- **Descriptive only:**
  - errors by type;
  - hitting the answer budget (for FoundationModels, at least 495 tokens by the framework's own
    count);
  - median answer length and time;
  - per-category rates;
  - run-to-run agreement: the share of items given the same call in run 1 and run 2.

**Detector audit.** The detector is only as good as its agreement with a reader.

- After run 1, `summarize.py` draws 40 outputs per arm (seed 0), drops errors and empty outputs,
  shuffles the rest and writes a sheet with only the question and the answer. The arm and the
  detector's call are not on it.
- A reader labels each output *answer* or *absent* by the definition above, in a copy of the
  sheet saved as `labels.csv`. The write-up names the reader.
- Agreement is the share of labelled outputs where the reader and the detector agree. It is
  reported overall and per arm, and every disagreement is listed.

## Decision rule

The idea under test is **making Gemma 4 E2B Xylo's default chat backend on 8 GB devices, in place
of FoundationModels**. The rule compares `gemma-e2b` with `fm` on run 1. Apply the steps in order;
the first match wins.

1. If the detector agrees with the reader on fewer than 90% of audited outputs, the verdict is
   **inconclusive: detector not valid**.
2. If Gemma's balanced accuracy is less than 5 points above FoundationModels', the verdict is
   **reject: no gain**. FoundationModels stays the default.
3. Check three criteria:
   - **c1:** Gemma's balanced accuracy is at least 10 points higher, and the lower bound of the
     95% confidence interval is above 0. The interval comes from a contract-level bootstrap with
     10,000 resamples and seed 0: contracts are resampled with all their items.
   - **c2:** Gemma's key-fact rate is no more than 5 points below FoundationModels'.
   - **c3:** Gemma's unsupported-number share is no more than 5 points above FoundationModels'.
4. If c1 to c3 all hold, the verdict is **adopt (host stage)**. The lab then recommends Gemma as
   the 8 GB default where it is downloaded. Xylo would make that change only after an 8 GB iPhone
   run, which re-measures FoundationModels on the phone and adds latency, memory and heat.
5. If c1 holds but c2 or c3 fails, the verdict is **reject: trade-off**.
6. Otherwise the verdict is **inconclusive**, naming the failing criteria.

`qwen-1.5b` answers H1 and H2; it never changes the verdict. The 6 GB tier has no other chat
model, so the Qwen result decides what to test next there, not a swap.

## Results

Run 2026-10-09 on the host above, from commit `698321d` (the protocol commit `efa360e` plus the one
line added to `run.sh` that is described under Deviations), with no tracked file changed. Run 1 took
about 52 minutes (10:02 to 10:54, UTC+8) and run 2 about 54. Every number here is MEASURED on the
host unless tagged otherwise. Raw files are in [`results/raw`](results/raw): `items.jsonl` (the 986
items), `gen-<arm>-run<n>.jsonl` (every output), the six `harness-*.log` files, `arms.json`,
`arms-run2.json` and `conditions.txt`. The tables come from [`results/summary.md`](results/summary.md),
which `summarize.py` generates along with [`results/summary.json`](results/summary.json). The audit
sheet, its key and the labels are in [`results/audit`](results/audit).

The run covered 986 items (504 answerable, 482 unanswerable) from 392 contracts, 5,916 outputs in all.
No output was an error or empty, and FoundationModels raised no guardrail refusal. Outputs that hit
the answer budget in run 1: 1 for Gemma, 5 for Qwen and 5 for FoundationModels (at least 495
tokens by the framework's count).

**Run 1, by arm** (percent of items; the answer and absent rates use the detector):

| Arm | Answers answerable | Says absent on unanswerable | Balanced | Key fact right (n=181) | Any unsupported number | Unsupported, unanswerable | Median words | Median ms |
|---|---|---|---|---|---|---|---|---|
| `fm` | 85.5 | 38.6 | **62.1** | 85.1 | 4.5 | 5.2 | 17 | 803 |
| `gemma-e2b` | 88.1 | 64.9 | **76.5** | 90.1 | 0.2 | 0.2 | 19 | 1,143 |
| `qwen-1.5b` | 82.1 | 32.6 | **57.4** | 77.3 | 3.0 | 4.8 | 6 | 694 |

On unanswerable items the share that fills the gap (one minus the absent rate) is 61% for
FoundationModels, 35% for Gemma and 67% for Qwen.

**Decision rule** (`gemma-e2b` against `fm`, run 1; contract-level bootstrap, 10,000 resamples,
seed 0). Step 1 passed: the detector agrees with the reader on 96% of 120 audited outputs, above
90%. Step 2 did not apply: the balanced gain is above 5 points. All three criteria hold:

| Criterion | Result | Threshold |
|---|---|---|
| c1, balanced accuracy | **+14.5 points, 95% CI [+11.3, +17.6]** | at least +10, lower bound above 0 |
| c2, key-fact rate | **+5.0 points, CI [+0.5, +9.8]** | no worse than -5 |
| c3, unsupported-number share | **-4.3 points, CI [-5.5, -3.1]** | no more than +5 |

**Hypotheses.** None held.

1. **H1, did not hold.** Qwen says absent 6.0 points less often than FoundationModels (CI
   [-11.5, -0.6]; the threshold is 15) and 32.4 points less often than Gemma (CI [-37.4, -27.3]).
   Only the Gemma part meets the threshold. FoundationModels fills the gap on 61% of unanswerable
   items, Qwen on 67%.
2. **H2, did not hold.** Qwen's outputs contain an unsupported number 1.4 points less often than
   FoundationModels' (CI [-3.1, +0.2]) and 2.8 points more often than Gemma's (CI [+1.8, +4.0]).
   Neither gap reaches 5 points in the direction claimed.
3. **H3, did not hold.** FoundationModels and Gemma are 14.5 points apart on balanced accuracy, not
   within 10.

**Per category** (balanced accuracy, percent; each category has 36 answerable and 36 unanswerable items,
except Governing Law with 21 unanswerable and Agreement Date with 29; the full table, with answer and
absent rates, is in `results/summary.md`):

| Category | `fm` | `gemma-e2b` | `qwen-1.5b` |
|---|---|---|---|
| Change Of Control | 51 | 83 | 56 |
| Non-Compete | 57 | 86 | 50 |
| Governing Law | 52 | 81 | 73 |
| Expiration Date | 50 | 78 | 53 |
| Insurance | 64 | 89 | 72 |
| Exclusivity | 56 | 78 | 54 |
| Agreement Date | 59 | 78 | 52 |
| Renewal Term | 56 | 72 | 62 |
| Notice Period To Terminate Renewal | 51 | 65 | 54 |
| Cap On Liability | 65 | 69 | 58 |
| Liquidated Damages | 82 | 81 | 71 |
| Audit Rights | 92 | 90 | 53 |
| Warranty Duration | 60 | 57 | 51 |
| Termination For Convenience | 65 | 62 | 44 |

- Gemma is higher in 10 of 14 categories, by 4 to 32 points, and within 3 points of FoundationModels
  (below it) in the other four: Liquidated Damages, Audit Rights, Warranty Duration and Termination
  For Convenience. No per-category interval was computed, and with 36 items per class a difference of
  a few points inside one category is within noise.
- The biggest gains are where the clause is usually missing and FoundationModels names one: Change Of
  Control (says absent on 3% of unanswerable items against Gemma's 67%), Expiration Date (0% against
  56%) and Governing Law (5% against 62%).
- **Exclusivity looks like a yes-or-no reading.** FoundationModels answers 11% of answerable
  Exclusivity items. 65 of its 72 Exclusivity outputs begin "No" (33 "No, the document ...", 16 "No,
  the parties ..." and 16 "No, neither party ..."), and the detector counts "No" as absent. Reading
  the question as yes or no is INFERRED from those openings; the detector's polarity follows the
  protocol.
- Gemma's key-fact rate is lowest on Warranty Duration (45%, against FoundationModels' 59%).

**Latency on the host** (median ms per answer, run 1):

| Arm | total | prefill | generate | to first text |
|---|---|---|---|---|
| `fm` | 803 | | | 636 |
| `gemma-e2b` | 1,143 | 662 | 456 | |
| `qwen-1.5b` | 694 | 547 | 150 | |

Gemma takes about 340 ms longer per answer than FoundationModels on the host. Latency is not in the
decision rule, and no phone figure exists. Run 1 drew from AC power apart from the three short drops
under Deviations.

**Detector audit.** One reader labelled 120 outputs (40 per arm) from the blinded sheet, using the
definition under Measurements. The reader is an AI model, not an independent human; see Deviations.
Agreement is **96% (115 of 120)**: `fm` 100%, `gemma-e2b` 98%, `qwen-1.5b` 90%. The five
disagreements:

| Sheet id | Arm | Item | Detector | Reader | Output starts |
|---|---|---|---|---|---|
| 10 | `qwen-1.5b` | 891 | answer | absent | `: No, the contract does not restrict ...` |
| 35 | `qwen-1.5b` | 341 | answer | absent | `*-No*` |
| 50 | `qwen-1.5b` | 145 | answer | absent | `] No` |
| 90 | `qwen-1.5b` | 227 | answer | absent | `-No.` |
| 115 | `gemma-e2b` | 920 | absent | answer | `No later than [* * *] days prior to the end of the Initial Term ...` |

Four of the five are one failure. The detector strips a leading list marker (`-`, `*`, a number) but
not other leading punctuation, so a Qwen output that opens with `: No`, `] No` or `*-No*` is read as
an answer. The fifth runs the other way: an answer that begins "No later than" is read as absent,
because the first pattern is `^(no|none|nope)\b`.

**Exploratory: the leading-punctuation miss over all outputs (not registered).** In run 1, 74 of
Qwen's 986 outputs begin with punctuation then "No" and are read as answers, against 1 of
FoundationModels' and none of Gemma's. Reading them as absent, with no other change, gives (percent):

| Arm | Answers answerable | Says absent on unanswerable | Balanced |
|---|---|---|---|
| `fm` | 85.3 (was 85.5) | 38.6 | 62.0 (was 62.1) |
| `gemma-e2b` | 88.1 | 64.9 | 76.5 |
| `qwen-1.5b` | 78.6 (was 82.1) | 44.2 (was 32.6) | 61.4 (was 57.4) |

The fix moves `fm` by at most 0.2 points and `gemma-e2b` by none, so the decision rule, which compares
those two, is unaffected. It does move Qwen: its absent rate rises 11.6 points, so Qwen would be 5.6
points above FoundationModels on absent rate, not 6.0 below. H1 still would not hold, since H1 needs
Qwen 15 points below both. The registered figures above stay as registered. The opposite error, a
"No <word>" opening that is really an answer, was not measured the same way: 4 Gemma and 27 Qwen
outputs begin that way, and some, such as "No later than" and "No more frequently than", are answers.

**Run-to-run agreement** (same call in run 1 and run 2, percent of 986 items): `fm` 93.6,
`gemma-e2b` 94.8, `qwen-1.5b` 73.5. FoundationModels cannot be seeded, so its run 2 is a fresh sample.
Qwen's calls move much more between runs than the others'. Run 2 timings are not used (see
Deviations).

## Verdict

**Adopt (host stage)** (decision rule, step 3). On 986 contract questions over 392 contracts, each
answered from three sections, Gemma 4 E2B has a balanced accuracy of 76.5%, against 62.1% for
FoundationModels: a gain of 14.5 points (CI +11.3 to +17.6). It also gets the key fact right more often
(+5.0 points) and gives an unsupported number less often (-4.3 points). The gain comes from saying
"absent" when the clause is not there: on 65% of unanswerable items against 39%. On answerable items
the two answer at about the same rate (88% and 86%).

The lab recommends Gemma 4 E2B over FoundationModels as the contract-question backend on 8 GB devices
where the 3.5 GB model is downloaded. **No change to Xylo follows from this PoC alone.** Under the rule,
an 8 GB iPhone confirms it first, and changing the default is Xylo's decision.

Two findings go beyond the registered decision (MEASURED, with the reading INFERRED):

- **The capable-tiers claim does not hold for FoundationModels on this task.** Xylo's notes describe Gemma and FoundationModels as mostly unaffected. FoundationModels fills the gap on 61%
  of unanswerable items, close to the 1.5B model's 67%. What separates the backends is Gemma.
- **Filling gaps is not specific to the 1.5B model.** H1 failed because FoundationModels is
  nearly as bad. The data do not say the 1.5B model is as good as the others: its key-fact rate is the
  lowest (77%) and its calls are the least stable between runs (74%).

This verdict is for the host. On an iPhone it is INFERRED for Gemma and Qwen, which run the same
weights and sampler, and not for FoundationModels, whose phone model may differ.

**What this points to next** (HYPOTHESIS).

- **Why FoundationModels fills the gap.** Whether a prompt that says to answer "not in the sections"
  when it is not closes the gap is untested.
- **The 1.5B model.** A registered comparison of 1.5B-class models on this task, since its run-to-run
  agreement is 74%.
- **A phone run** of Gemma and FoundationModels on an 8 GB iPhone.
- **A corrected detector.** A second reading of these outputs with the leading-punctuation fix,
  registered before it is applied.

## Deviations

- **`run.sh` was edited after registration and before the run.** It now starts with `exec </dev/null`
  after the `cd` (commit `698321d`), so a background run does not depend on its terminal. PoC 007's run
  had crashed at its last line for that reason (INFERRED, not reproduced). The edit was checked with
  `bash -n` only. No other file under `poc/006-doc-qa-fm-gemma-qwen` changed between the protocol commit
  and the run.
- **The audit reader is an AI model.** The protocol says only that a reader labels each output and that
  the write-up names the reader. The reader was GitHub Copilot (Claude Sonnet 5.5), the assistant that
  wrote the harness and `summarize.py` and ran this PoC. It labelled from the blinded sheet, with no
  arm and no detector call on it, by the definition under Measurements. It had already seen the
  run's aggregate tables, and had read the detector's source. The labels were written before the
  agreement was computed. They apply the definition literally: "No, a party cannot terminate this
  contract without cause" is *absent*, and "Yes, no marketing exclusivity ... is conferred" is
  *answer*. No human has labelled the sheet. A human check of the five disagreements and of a sample of
  the rest would make the 96% more reliable.
- **Power.** Run 1 started on AC power (`conditions.txt`; the Mac was plugged in at 10:01:30, 39
  seconds before the first stage). Three drops to battery of about 2, 5 and 4 seconds fell inside the
  `fm` run 1 stage (10:50:28, 10:51:39 and 10:51:45), which lasted about 18 minutes. Run 2 then spent
  two stretches on battery, 11:25:05 to 11:32:56 and 11:33:13 to 11:41:19 (UTC+8): the last five
  minutes of `qwen-1.5b` run 2 and eleven of the 18 minutes of `fm` run 2. Run 2 timings are
  therefore not reported. The decision rule uses run 1 and no timing, and run-to-run agreement uses
  only the calls.
- **Reproduce block.** The block had a garbled line from a paste error. It is corrected in this
  commit; no result depends on it.

## Errata

- **2026-10-09: Xylo's chat prompt moved to a private overlay.** The text is confidential and is no longer in this repository. `prepare.py` reads it from `private/prompts.json`, which is gitignored; without that file it uses the generic stand-in in `generic/prompts.json` and prints a warning. The registered `inputs.jsonl` has SHA-256 `1e6c3a40f55280a6af727b14d58d05fcd6536dbe3750220cdfe6340180596a11` (recorded in `results/raw/conditions.txt`). `prepare.py` with the overlay rebuilds it byte for byte (checked 2026-10-09). The file was already uncommitted. The stand-in has the same structure with different wording, so a replication that uses it tests a similar prompt, not Xylo's. Whether the original text can be shared with a reviewer is the author's decision. The verdict and results are unchanged.
- **2026-10-09: one raw output redacted.** Run 1 item 79 of Qwen2.5-1.5B answered by reciting part of the private chat prompt. Its `text` and `tokens` in `results/raw/gen-qwen-1.5b-run1.jsonl` are replaced with a placeholder. `summarize.py` gives a byte-identical `summary.json`, `summary.md` and audit sheet before and after (checked 2026-10-09). Qwen reciting its own instructions is OBSERVED on this one output; it was already counted in the results as before.

## Limits

- **The detector misses leading punctuation.** It reads `: No`, `] No` and `*-No*` as answers and
  reads "No later than ..." as absent. The effect on the decision is 0.2 points or less (see Results).
  Qwen's absent rate is under-counted by about 11.6 points. The registered figures keep the frozen
  detector.
- **"No" counts as absent.** On yes-or-no questions (Exclusivity, Non-Compete, Liquidated Damages and
  similar) a reply "No, neither party ..." is read as absent. That is right when CUAD found no clause and
  wrong when the clause exists and the reply is a literal no. The polarity follows CUAD's labels and
  the protocol, not the truth of the reply.
- **The audit reader is an AI model**, the same assistant that built the harness. Its agreement with
  the detector shows that the detector matches the written definition when applied literally, not that a
  person would label the same.

- **Mac, not iPhone.** FoundationModels on macOS 26.5.1 may not be the model or the runtime of
  an iPhone on the same OS version. Gemma and Qwen run on Metal on an M4 Pro, not an A-series
  GPU. Answer quality should carry over for the GGUF models, as the same weights and sampler run
  on both (INFERRED). FoundationModels' may not.
- **Not the app's full prompt.** Without the summary and KEY DETAILS, every backend has less
  context than in the app. That may lower answer rates on dates and parties, which KEY DETAILS
  often carries.
- **Not the app's retrieval.** On answerable items the answer is always in the sections. So
  this measures what each backend does with the right evidence, or with none. It does not measure
  retrieval misses, which PoC 007 is to take up.
- **Single turn.** No conversation history, and no reuse of a cached prefix.
- **Polarity, not full correctness.** Outside the six key-fact categories, an answer counts as
  right on an answerable item whether or not its content matches CUAD's span. It counts as long as
  it does not say absent. A wrong answer given confidently still counts as an answer.
- **CUAD's labels.** "Absent" means CUAD's annotators found no such clause in the contract. A
  missed clause makes an unanswerable item answerable in fact, and penalizes a backend that
  finds it.
- **One sample per item** in run 1, with sampling on. Run 2 shows how much a second sample moves
  the calls. The verdict uses run 1 only.

## Reproduce

From a clean checkout on an Apple silicon Mac with macOS 26.4 or later, Apple Intelligence on,
and Xcode 26:

```sh
cd poc/006-doc-qa-fm-gemma-qwen
# models: run.sh prints the download commands if they are missing
./run.sh
# summarize.py writes results/audit/sheet.csv on the first call; label it into
# results/audit/labels.csv (a copy with the label column filled in), then:
python3 summarize.py
```

`results/raw/inputs.jsonl` (13 MB of prompts) is not committed. `prepare.py` rebuilds it byte for byte from the CUAD zip and the private overlay, and `conditions.txt` records its SHA-256. Without the overlay, `prepare.py` uses a generic stand-in prompt (see Errata).

## Replications

A replication needs an Apple silicon Mac with Apple Intelligence (for `fm`) and about 6 GB of
free memory. Point the run at a replication folder with
`OUT=replications/<name>/results/raw ./run.sh`, and summarize with
`python3 summarize.py replications/<name>/results`. An iPhone replication needs an app harness
that is not in this repository yet.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| | | | |
