# PoC 003: Qwen2.5 sampler settings and clean stopping on a structured summary

| | |
|---|---|
| Status | Written up (host stage) |
| Verdict | Reject: does not reproduce. The old settings already stop on their own (95%); the recipe's effect is on format, and presence penalty does not carry it |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet (founding reviewers being invited) |
| Source idea | Qwen2.5's published sampling guidance for its quantized models (temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5), and the change Xylo shipped based on it (private app, commit 4a2e7f2) |
| Registered | 2026-10-08, in the commit that adds this file, before the first run |

## Question

On Xylo's Summary prompt, does Qwen's recommended sampler make Qwen2.5-1.5B-Instruct Q4_K_M
stop on its own, with all four sections, more often than the near-greedy settings Xylo used
before? And which setting carries the effect?

## Why it matters here

On 6 GB iPhones, Xylo runs Qwen2.5-1.5B-Instruct Q4_K_M for summaries, with a 288-token answer
budget and about 2,500 characters of document. Xylo's engineering notes record one Summary job on an
iPhone 14 before and after the sampler change (OBSERVED, one document, one run each):

- **Before**, with near-greedy settings: 288 tokens, the full budget. The output was cut off
  mid-word, and no end-of-sequence token was produced.
- **After**, with Qwen's recommended settings: the model stopped on its own at 181 tokens, with
  all four sections in about 1,013 characters.

The same notes also record a known gap: on one test contract the model produced only two of the
four sections. So whether the change fixes the format is not settled either.

The notes credit presence_penalty with the effect (§15.3), but the change moved five settings at
once: temperature, top_p, top_k, repeat penalty and presence penalty. This PoC measures:

- whether the before/after difference holds across documents and seeds;
- whether presence_penalty alone carries it.

The lab's `EdgeRuntime` has no sampler defaults yet. An *adopt* verdict would add one.

## Hypotheses

All HYPOTHESIS until measured. A, B, C and D are the arms below.

1. **H1.** A, Xylo's old settings, hits the 288-token cap in at least 50% of generations.
2. **H2.** B, Qwen's recipe, stops cleanly in at least 90% of generations and has all four
   sections in at least 80%.
3. **H3.** Presence penalty carries the effect:
   - C's clean-stop rate is within 15 points of B's;
   - B's clean-stop rate is at least 30 points above D's.
4. **H4.** The share of B's outputs with at least one unsupported number is no more than 10
   points above A's.
5. **H5.** B's median generated length is at most 220 tokens.

## Method

**Model.** `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` from
[bartowski/Qwen2.5-1.5B-Instruct-GGUF](https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/tree/9eadc66189c7641e1ddd226b8267a9119b2ce2d4)
at commit `9eadc66`:
- 986,048,768 bytes;
- SHA-256 `1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370`;
- the same file Xylo downloads;
- Apache-2.0 license (see the model page);
- not committed.

**Tooling.** The harness is a small Swift program in [`harness/`](harness). It is built against
[llama.swift](https://github.com/mattt/llama.swift) 2.8901.0, which wraps the llama.cpp b8901
xcframework. That is the same binding and build Xylo ships, and it runs on the Metal backend.
[`Package.resolved`](harness/Package.resolved) pins the exact revision.

The generation loop is adapted from Xylo's `GemmaLLMEngine` (commit 196a729):

- **Settings:** the same context settings, the same tokenization, and the same sampler chain
  (penalties, then top_k if above 0, then temperature, top_p and dist).
- **Stopping:** generation ends on the end-of-sequence token, or on a token whose text contains
  `<|im_end|>`. Output is the concatenated token pieces, trimmed.
- **Removed:** the app's memory guards, thermal pacing and cancellation.
- **Changed:** dist gets a fixed seed instead of a random one.

`llama-server` was considered and not used. It feeds every prompt token into the sampler, which
puts the end of the document inside the 256-token penalty window. Xylo feeds in generated tokens
only, so that would change the very settings under test.

**Host.** MacBook Pro, Apple M4 Pro, 24 GB, macOS 26.5.1, Swift 6.3.3, on AC power. The host
shows how the sampler and model behave. Its speed does not transfer to an iPhone GPU, and Metal
numerics may differ slightly between chips.

**Fixed settings.** These mirror Xylo's 6 GB settings:

| Setting | Value |
|---|---|
| Context | 4,096 tokens (`n_batch` 4,096, `n_ubatch` 128) |
| Threads | 2 |
| GPU layers | All |
| Flash attention | Off |
| Answer budget | 288 tokens |
| Seeds | 1 to 5 |

**Arms.** These are in [`arms.json`](arms.json). Every arm uses a penalty window of the last
256 generated tokens.

| Arm | Temperature | top_p | top_k | Repeat | Frequency | Presence | Role |
|---|---|---|---|---|---|---|---|
| `a-near-greedy` | 0.2 | 0.9 | off | 1.3 | 0.15 | 0.15 | Xylo before 4a2e7f2 |
| `b-qwen-recipe` | 0.7 | 0.8 | 20 | 1.05 | 0 | 1.5 | Xylo after 4a2e7f2 |
| `c-near-greedy-presence` | 0.2 | 0.9 | off | 1.3 | 0.15 | **1.5** | A with B's presence penalty (exploratory) |
| `d-qwen-recipe-no-presence` | 0.7 | 0.8 | 20 | 1.05 | 0 | **0** | B without presence penalty (exploratory) |

**Data.** The inputs are 20 contracts from
[CUAD v1](https://zenodo.org/records/4595826) by The Atticus Project, under CC BY 4.0.

- **Archive:** `CUAD_v1.zip`, SHA-256
  `88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e`.
- **Selection:** [`prepare.py`](prepare.py) sorts the 510 files in `full_contract_txt/` by path
  and takes every 25th, starting with the first.
- **Normalization:** whitespace only. Line endings are unified, runs of spaces collapse, each line
  is trimmed, and 3 or more blank lines become 1.
- **Cut:** the first 2,500 characters, the way Xylo cuts a document to its budget (mid-word
  allowed).
- **Prompt:** Xylo's Summary prompt for Qwen, unchanged. That is the system message plus a user message with a worked four-section example; the app adds no primer. The prompt text is not published; see Errata.

`inputs.jsonl` records each input with its hash. It embeds the prompt, so it is not committed; `prepare.py` rebuilds it (see Errata).

**Order.** Each document is run under each seed, and each seed under all four arms in turn. That
makes 20 × 5 × 4 = 400 generations, and any slow drift on the host affects every arm equally.

**Measurements.** All of these are computed by [`summarize.py`](summarize.py):

- **Clean stop:** the generation ended on end-of-sequence or `<|im_end|>` before the cap.
- **Four sections:** `Introduction`, `Summary`, `Key Points` and `Action Items` all appear as
  headings, in that order by first appearance. A heading has 2 or 3 hashes; case and a trailing
  colon are ignored.
- **Complete:** clean stop and four sections.
- **Unsupported number:** a number of 2 or more digits (commas removed) that does not occur in the
  input. The reported figure is the share of generations with at least one.
- **Exemplar leak:** "Riverside", "Eastside", "Annex" or "Community Center" (from the prompt's
  example) appears in the output but not in the input.
- **Descriptive only:** looping (any 6-word sequence 3 or more times), median generated tokens,
  and prefill and decode time.

## Decision rule

The rule compares A and B. Apply the steps in order; the first match wins. "Points" means
percentage points of generations.

1. If B's clean-stop rate is less than 10 points above A's, the verdict is **reject: does not
   reproduce**.
2. Check four criteria:
   - **c1:** B's clean-stop rate is at least 40 points above A's, and the lower bound of the 95%
     confidence interval is above 0. The interval comes from a document-level bootstrap with
     10,000 resamples and seed 0.
   - **c2:** B's complete rate is at least A's.
   - **c3:** B's unsupported-number share is no more than A's plus 10 points.
   - **c4:** B's exemplar-leak rate is at most 5%.
3. If c1 to c4 all hold, the verdict is **adopt**. `EdgeRuntime` gets a Qwen2.5 sampler profile
   with B's settings, citing this PoC.
4. If c1 holds but c3 or c4 fails, the verdict is **reject: trade-off**. B stops cleanly but adds
   unsupported content.
5. Otherwise the verdict is **inconclusive**, naming the failing criteria.

C and D only inform H3; they never change the verdict.

This is a host-stage verdict. Carrying it over to iPhones is INFERRED until a 6 GB iPhone run
confirms it.

## Results

Run 2026-10-08 on the host above, 400 of 400 generations completed. Every number here is
MEASURED on the host unless tagged otherwise. Raw files are in [`results/raw`](results/raw):

- `inputs.jsonl` (not committed; see Errata): the 20 input slices and prompts, with hashes;
- `generations.jsonl`: every output, with its tokens, stop reason and timings;
- `harness.log` and `conditions.txt`.

The tables below come from [`results/summary.md`](results/summary.md), which `summarize.py`
generates along with [`results/summary.json`](results/summary.json).

The model file was copied from Xylo's storage on an iPhone 14 Plus, not downloaded. Its SHA-256
matches the pinned file, and `run.sh` checked it before the run.

**Registered measures.** Each arm has 100 generations: 20 documents × 5 seeds.

| Arm | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Exemplar leak | Median tokens | Median decode tok/s |
|---|---|---|---|---|---|---|---|---|
| A `a-near-greedy` (Xylo before) | 95% | 5% | 3% | 3% | 12% | 1% | 101 | 99.2 |
| B `b-qwen-recipe` (Xylo after) | 98% | 2% | 39% | 39% | 3% | 0% | 131.5 | 109.3 |
| C `c-near-greedy-presence` | 91% | 9% | 0% | 0% | 26% | 1% | 128.5 | 100.5 |
| D `d-qwen-recipe-no-presence` | 100% | 0% | 41% | 41% | 0% | 0% | 126.5 | 108.3 |

Every clean stop came from the end-of-sequence token; the `<|im_end|>` text check never fired.
Looping (the same 6-word sequence 3 or more times) occurred in 0 to 2% of each arm.

The document-level bootstrap of B minus A (10,000 resamples, seed 0) gives:

- **Clean stop:** +3 points, 95% CI [−1, +8].
- **Complete:** +36 points, 95% CI [+26, +47].

**Hypotheses.**

1. **H1, did not hold.** A hit the 288-token cap in 5% of generations, not the predicted 50% or
   more. On these inputs, the old settings stop on their own.
2. **H2, did not hold.** B stopped cleanly in 98% of generations, above the 90% threshold, but
   had all four sections in only 39%, against a threshold of 80%.
3. **H3, did not hold.**
   - C, the old settings with presence penalty 1.5, had a clean-stop rate within 15 points of
     B's (91% against 98%). That half held.
   - B's clean-stop rate was not 30 points above D's: B 98%, D 100%. That half failed.
   - On format, C produced four sections in 0% of generations and D in 41%. Presence penalty
     is not what moves either measure.
4. **H4, held.** 3% of B's outputs had an unsupported number, against 12% of A's.
5. **H5, held.** B's median length was 131.5 tokens, against a limit of 220.

**What the outputs look like** (exploratory; these measures were added to `summarize.py` after
the run and are labeled there as not registered).

A usually writes two sections and stops:

- 86 of A's 100 outputs have exactly two of the four headings, Introduction and Summary.
- 45 of them then write a line such as `### END SUMMARY` and end. That imitates the line that closes the worked example in the prompt (OBSERVED).

Document 0, seed 1:

```
## Introduction
This document is a Co-Branding and Advertising Agreement between i-Escrow, Inc. (i-E) and 2TheMart.com, Inc.

## Summary
- The agreement covers the use of Marks by both parties.
- Launch Date refers to when co-branded site becomes available on auction platform for testing purposes only.
- Information Transfer Mechanism involves transferring information from one party's system into another’s during transactions or user registration processes.
### END SUMMARY
```

| Arm | Generations by number of section headings found (1 / 2 / 3 / 4) | Writes an END line |
|---|---|---|
| A | 0 / 86 / 11 / 3 | 45% |
| B | 0 / 39 / 22 / 39 | 4% |
| C | 4 / 84 / 12 / 0 | 15% |
| D | 0 / 36 / 23 / 41 | 0% |

B's complete rate was higher than A's on 17 of the 20 documents and equal on the other 3. B was
never lower. On 2 documents, none of B's 5 generations was complete.

## Verdict

**Reject: does not reproduce** (decision rule, step 1). B's clean-stop rate was 3 points above
A's, and the rule required at least 10.

On these 20 contracts on the host, the near-greedy settings Xylo used before did not run to the
288-token cap. They stopped on their own 95% of the time. So the iPhone 14 observation in Xylo's
notes (§15.5), where the old settings hit the cap mid-word, did not reproduce here. Nothing in
the lab's `EdgeRuntime` changes.

The rule's question was about stopping, and the recipe did not change that. What it did change is
format:

- **Format gain:** four complete sections went from 3% to 39% (+36 points, 95% CI [+26, +47]),
  and unsupported numbers fell from 12% to 3%.
- **Presence penalty is not the cause:**
  - D, the recipe with presence penalty 0, matched B: 41% four sections, 0% unsupported numbers.
  - C, the old settings plus presence penalty 1.5, was the worst arm: 0% four sections, 26%
    unsupported numbers.

  So the effect comes from the other settings that changed together (INFERRED). Those are lower
  repeat and frequency penalties, higher temperature, and top_k/top_p. Which of them matters was
  not separated here.
- **Still short of the claim:** B gave four sections only 39% of the time. That matches the gap
  Xylo's notes recorded, and it is far from "all four sections" as a dependable result.

The registered rule cannot turn any of this into *adopt*, and no deviation from it is taken. The
format result is a new question for its own PoC, not a verdict here.

**What this points to next** (HYPOTHESIS). A repeat penalty of 1.3 over the last 256 generated
tokens makes the `##` tokens and the section words less likely each time they recur, which would
push the model toward ending early. A follow-up PoC could vary repeat penalty alone (1.05, 1.15
and 1.3, with B's other settings) and measure the four-section rate as the registered outcome.
It could also test removing the line that closes the worked example from the prompt, since A's outputs imitate
it.

## Deviations

None. The method, arms, inputs and decision rule ran as registered. The exploratory section in
`summarize.py` and the section-count and END-line tables above were added after the run. They
are labeled as exploratory and did not affect the verdict.

## Errata

- **2026-10-09: Xylo's Summary prompt moved to a private overlay.** The text is confidential and is no longer in this repository. `prepare.py` reads it from `private/prompts.json`, which is gitignored; without that file it uses the generic stand-in in `generic/prompts.json` and prints a warning. The registered run's `inputs.jsonl` has SHA-256 `77263695c5ea77f372e7a8afcf97380deba040e688f694bfd4c016e71ac50341` (recorded in `results/raw/conditions.txt`). `prepare.py` with the overlay rebuilds it byte for byte (checked 2026-10-09). The file embeds the prompt, so it is no longer committed. The stand-in has the same structure with different wording, so a replication that uses it tests a similar prompt, not Xylo's. Whether the original text can be shared with a reviewer is the author's decision. The verdict and results are unchanged.
- **2026-10-09: raw generations withheld from the public snapshot.** `results/raw/generations.jsonl` holds some outputs that repeat fragments of Xylo's confidential Summary prompt, including its example. It is held in the lab's private archive until the lab decides how to publish them without that text. The summary files here were computed from the full outputs and are unchanged; they cannot be re-derived from this repository until the raw file is restored. Results and verdict are unchanged.

## Limits

- **Host only.** The host is not an iPhone. Metal numerics and speed differ, and there is no
  thermal pacing.
- **Narrow scope.** One model, one prompt, one answer budget, and English contracts only.
- **Different input preparation.** Xylo first compresses a document (`compressDocumentText`),
  which this PoC does not reproduce. Here the input is whitespace-normalized raw text.
- **Different documents.** CUAD contracts are legal text from SEC filings, not the documents
  Xylo's users scan.
- **Weak faithfulness check.** Unsupported numbers are only a proxy for faithfulness. They miss
  numbers written as words and invented names.
- **Format check is about format.** The heading check tests format, not whether the content of
  each section is right.
- **Private source app.** The loop is copied here so the run does not depend on the app. The prompt is Xylo's and is held in a private overlay.

## Reproduce

```sh
cd poc/003-qwen-sampler-stop-behavior
./run.sh            # checks the model hash, downloads and checks CUAD, builds the harness, runs 400 generations
python3 summarize.py
```

The model must be at `models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`; `run.sh` prints the download
command if it is missing.

## Replications

Replications of the host stage are open. The steps and the evidence standard are in
[CONTRIBUTING.md](../../CONTRIBUTING.md); open a Replication issue before running.

**Needs.**
- An Apple silicon Mac with a Swift 6 toolchain (Xcode or Command Line Tools).
- About 1.2 GB of free disk: the 0.99 GB model, the 106 MB dataset, and the build.

**Run** into a folder named `YYYY-MM-DD-<github-handle>-<device>`:

```sh
cd poc/003-qwen-sampler-stop-behavior
R=replications/2026-10-15-yourhandle-m2-air
OUT=$R/results/raw ./run.sh
python3 summarize.py $R/results
cp ../_template/REPLICATION.md $R/README.md   # then fill it in
```

**Record** the llama.swift pin from `conditions.txt`. A different pin is a deviation, and the
replication has to say so.

A 6 GB iPhone run of the same loop is especially welcome, because the original observation that
the old settings hit the cap came from an iPhone 14. The comparison is whether each hypothesis
and decision criterion comes out the same way.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| None yet | | | |
