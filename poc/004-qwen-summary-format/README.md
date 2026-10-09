# PoC 004: What holds Qwen2.5-1.5B to two of four summary sections

| | |
|---|---|
| Status | Written up (host stage) |
| Verdict | Reject: no gain from removing the END line. The repeat penalty, tested alongside, accounts for the format effect PoC 003 found |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet (founding reviewers being invited) |
| Source idea | The exploratory findings of [PoC 003](../003-qwen-sampler-stop-behavior#verdict): the format effect of Qwen's recipe, presence penalty ruled out, and the `### END SUMMARY` lines that copy the closing line of the prompt's worked example |
| Registered | 2026-10-08, in the commit that adds this file, before the first run |

## Question

On Xylo's Summary prompt, does the repeat penalty explain why Qwen2.5-1.5B-Instruct Q4_K_M writes
two of four sections instead of four? And does removing the prompt's closing line of the worked example raise
the share of complete four-section summaries under the settings Xylo ships?

## Why it matters here

[PoC 003](../003-qwen-sampler-stop-behavior) measured Xylo's Summary job on 20 CUAD contracts on
the host (MEASURED):

- Under Xylo's old near-greedy settings (A), 3% of outputs had all four sections; 86% stopped
  after two, Introduction and Summary.
- Under the Qwen recipe Xylo now ships (B), 39% had all four.
- Presence penalty did not carry the difference. B without it (D) reached 41%, and A with it (C)
  reached 0%.
- 45% of A's outputs wrote a line such as `### END SUMMARY` and then stopped, copying the line that closes the worked example in the prompt (OBSERVED).

So even the shipped settings give Xylo users a complete summary less than half the time. Two
explanations came out of PoC 003, both HYPOTHESIS:

1. **Repeat penalty.** A uses 1.3 and B uses 1.05, over the last 256 generated tokens. A
   penalty of 1.3 makes every token already generated less likely, including `##` and the
   section words, so after two sections the model may prefer to end.
2. **The END line.** The worked example in the prompt ends with a delimiter line. The model may treat an END line as the natural close of its own output.

This PoC separates them. Either answer changes something concrete:

- The repeat penalty result tells the lab whether a Qwen2.5 sampler profile in `EdgeRuntime` has
  to cap it.
- The END-line result is a one-line prompt change for Xylo.

## Hypotheses

All HYPOTHESIS until measured. The arms are below. "Four sections" is the PoC 003 measure: all four
headings, in order.

1. **H1. Repeat penalty lowers four-section output under B's other settings.**
   - The four-section rate does not rise as the repeat penalty rises: `b-qwen-recipe` (1.05) ≥
     `b-repeat-1.15` ≥ `b-repeat-1.3`.
   - `b-repeat-1.3` is at least 25 points below `b-qwen-recipe`.
2. **H2. Lowering the repeat penalty alone lifts A.** `a-repeat-1.05` has a four-section rate at
   least 25 points above `a-near-greedy`.
3. **H3. The END line holds output short.** `b-no-end-line` has a four-section rate at least 15
   points above `b-qwen-recipe`.

## Method

Everything not listed here is PoC 003's method, unchanged:

- the model file (`Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`, SHA-256
  `1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370`);
- the harness, which is PoC 003's [`harness/`](../003-qwen-sampler-stop-behavior/harness) built
  and run as is (llama.swift 2.8901.0, llama.cpp b8901, Metal), with the same fixed settings
  (context 4,096, `n_ubatch` 128, 2 threads, all GPU layers, flash attention off, 288-token
  budget, seeds 1 to 5, penalty window 256 generated tokens);
- the host (MacBook Pro, M4 Pro, 24 GB, macOS 26.5.1, on AC power);
- the 20 CUAD v1 contracts, their selection, normalization and 2,500-character cut;
- the scoring, which [`summarize.py`](summarize.py) imports from PoC 003's `summarize.py`.

**Prompt variants.** [`prepare.py`](prepare.py) writes two input files:

- **`xylo`:** Xylo's Summary prompt, built by PoC 003's `prepare.py`. The file is byte-identical
  to PoC 003's `results/raw/inputs.jsonl`.
- **`no-end-line`:** the same prompt with the single line that closes the worked example deleted.
  The example's opening heading, the example itself, and the instructions after it are unchanged.

**Arms.** These are in [`arms.json`](arms.json). Each changes one thing from a PoC 003 arm; the
changed value is in bold.

| Arm | Prompt | Temperature | top_p | top_k | Repeat | Frequency | Presence | Role |
|---|---|---|---|---|---|---|---|---|
| `a-near-greedy` | xylo | 0.2 | 0.9 | off | 1.3 | 0.15 | 0.15 | PoC 003's A (Xylo before 4a2e7f2) |
| `a-repeat-1.05` | xylo | 0.2 | 0.9 | off | **1.05** | 0.15 | 0.15 | A with B's repeat penalty (H2) |
| `b-qwen-recipe` | xylo | 0.7 | 0.8 | 20 | 1.05 | 0 | 1.5 | PoC 003's B (Xylo now) |
| `b-repeat-1.15` | xylo | 0.7 | 0.8 | 20 | **1.15** | 0 | 1.5 | H1 |
| `b-repeat-1.3` | xylo | 0.7 | 0.8 | 20 | **1.3** | 0 | 1.5 | B with A's repeat penalty (H1) |
| `b-no-end-line` | **no-end-line** | 0.7 | 0.8 | 20 | 1.05 | 0 | 1.5 | H3 and the decision rule |

**Order.** [`run.sh`](run.sh) runs the harness once per prompt variant. The first run covers
the five `xylo` arms, interleaved inside each (document, seed) as in PoC 003; the second covers
`b-no-end-line`. That makes 20 documents × 5 seeds × 6 arms = 600 generations. None of the
registered measures is a timing, so running the variants one after the other does not affect
them.

**Measurements.** As PoC 003: clean stop, four sections, complete (clean stop and four
sections), any unsupported number, exemplar leak, looping, median generated tokens and decode
speed. Two measures that were exploratory in PoC 003 are now registered as descriptive: the
number of distinct section headings found, and whether the output contains an END line (a line
starting with hashes and `END`).

**Reproducibility check.** `a-near-greedy` and `b-qwen-recipe` repeat PoC 003's A and B with
the same harness, inputs, seeds and host. `summarize.py` counts how many of their 100
generations are token-for-token identical to PoC 003's. All 200 are expected to match. A
mismatch is reported and investigated; it does not change the verdict.

## Decision rule

The rule compares `b-no-end-line` with `b-qwen-recipe`, on the complete rate. Apply the steps in
order; the first match wins. "Points" means percentage points of generations.

1. If `b-no-end-line`'s complete rate is less than 10 points above `b-qwen-recipe`'s, the verdict
   is **reject: no gain**.
2. Check four criteria:
   - **c1:** the complete rate is at least 15 points higher, and the lower bound of the 95%
     confidence interval is above 0. The interval comes from a document-level bootstrap with
     10,000 resamples and seed 0, as in PoC 003.
   - **c2:** `b-no-end-line` stops cleanly in at least 90% of generations.
   - **c3:** its unsupported-number share is no more than `b-qwen-recipe`'s plus 5 points.
   - **c4:** its exemplar-leak rate is at most 5%. Without the END line the example may run
     into the answer, so this is checked.
3. If c1 to c4 all hold, the verdict is **adopt**: the lab recommends dropping the line, and
   Xylo removes it from its Summary prompt in a change that cites this PoC. Prompts are not part
   of the lab's `Sources/`, so nothing moves there.
4. If c1 holds but c3 or c4 fails, the verdict is **reject: trade-off**.
5. Otherwise the verdict is **inconclusive**, naming the failing criteria.

The repeat-penalty arms answer H1 and H2 only; they never change the verdict. A change to the
sampler Xylo ships, or a Qwen2.5 profile in `EdgeRuntime`, would need its own PoC.

This is a host-stage verdict. Carrying it over to iPhones is INFERRED until a 6 GB iPhone run
confirms it.

## Results

Run 2026-10-08 to 2026-10-09 on the host above, 600 of 600 generations completed. Every number
here is MEASURED on the host unless tagged otherwise. Raw files are in [`results/raw`](results/raw):

- `inputs-xylo.jsonl` and `inputs-no-end-line.jsonl` (not committed; see Errata): the 20 inputs and both prompt variants, with hashes;
- `generations-xylo.jsonl` and `generations-no-end-line.jsonl`: every output, with its tokens,
  stop reason and timings;
- `arms-*.json`, `harness.log` and `conditions.txt`.

The tables below come from [`results/summary.md`](results/summary.md), which `summarize.py`
generates along with [`results/summary.json`](results/summary.json).

**Reproducibility check.** All 100 `a-near-greedy` and all 100 `b-qwen-recipe` generations are
token-for-token identical to PoC 003's A and B. The two runs agree exactly where they overlap, even
though this one ran on battery (see Deviations).

**Registered measures.** Each arm has 100 generations: 20 documents × 5 seeds.

| Arm | Repeat | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Exemplar leak | END line | Median tokens |
|---|---|---|---|---|---|---|---|---|---|
| `a-near-greedy` | 1.3 | 95% | 5% | 3% | 3% | 12% | 1% | 45% | 101 |
| `a-repeat-1.05` | **1.05** | 99% | 1% | 42% | 42% | 0% | 0% | 0% | 131.5 |
| `b-qwen-recipe` | 1.05 | 98% | 2% | 39% | 39% | 3% | 0% | 4% | 131.5 |
| `b-repeat-1.15` | **1.15** | 98% | 2% | 15% | 14% | 12% | 0% | 29% | 112 |
| `b-repeat-1.3` | **1.3** | 91% | 9% | 4% | 4% | 21% | 2% | 24% | 128 |
| `b-no-end-line` | 1.05, **no END line** | 100% | 0% | 36% | 36% | 3% | 0% | 0% | 115 |

Number of distinct section headings found per arm (1 / 2 / 3 / 4):

| Arm | 1 / 2 / 3 / 4 |
|---|---|
| `a-near-greedy` | 0 / 86 / 11 / 3 |
| `a-repeat-1.05` | 0 / 31 / 27 / 42 |
| `b-qwen-recipe` | 0 / 39 / 22 / 39 |
| `b-repeat-1.15` | 0 / 70 / 15 / 15 |
| `b-repeat-1.3` | 2 / 86 / 8 / 4 |
| `b-no-end-line` | 0 / 47 / 17 / 36 |

Every clean stop came from the end-of-sequence token. Looping occurred in 0 to 3% of each arm.
Decode speeds are in `summary.md` but are not comparable to PoC 003's (see Deviations).

The document-level bootstrap (10,000 resamples, seed 0) gives:

- **Complete, `b-no-end-line` − `b-qwen-recipe`:** −3 points, 95% CI [−13, +7].
- **Four sections, `b-repeat-1.3` − `b-qwen-recipe`:** −35 points, 95% CI [−45, −25].
- **Four sections, `a-repeat-1.05` − `a-near-greedy`:** +39 points, 95% CI [+24, +54].

**Hypotheses.**

1. **H1, held.** Under B's other settings, four-section output fell as the repeat penalty rose:
   39% at 1.05, 15% at 1.15, 4% at 1.3. The drop from 1.05 to 1.3 was 35 points, against a
   threshold of 25.
2. **H2, held.** Lowering only the repeat penalty of Xylo's old settings, from 1.3 to 1.05,
   raised four-section output from 3% to 42%: +39 points, against a threshold of 25.
3. **H3, did not hold.** Without the END line, four-section output was 36%, against 39% with
   it.

**Exploratory** (added to `summarize.py` after the run and labeled there as not registered):

- `a-repeat-1.05` beat `a-near-greedy` on 15 of 20 documents and tied on 5; it was never lower.
  Against `b-qwen-recipe` it was higher on 8, equal on 5 and lower on 7.
- `b-no-end-line` against `b-qwen-recipe`: higher on 4 documents, equal on 10, lower on 6.
- Documents where none of the 5 seeds gave a complete summary: 18 of 20 under `a-near-greedy`,
  16 under `b-repeat-1.3`, 5 under `a-repeat-1.05`, and 2 under both `b-qwen-recipe` and
  `b-no-end-line`.

## Verdict

**Reject: no gain** (decision rule, step 1). Removing the example's closing line changed the
complete rate by −3 points, and the rule required at least +10. Xylo's prompt stays as it is.

The repeat-penalty arms answer the question PoC 003 left open:

- **The repeat penalty carries the format effect.** With every other setting held, 1.3 gives
  3 to 4% four-section summaries and 1.05 gives about 40%, under either set of other settings.
  The old settings with only the repeat penalty lowered (`a-repeat-1.05`, 42%) match Qwen's
  recipe (`b-qwen-recipe`, 39%). So the temperature, top_k and top_p changes add little or nothing
  to format on these inputs (INFERRED from two arms at one repeat-penalty value).
- **The END lines are a symptom, not a cause.** They appear when the penalty is high (24 to 45%
  of outputs at 1.15 and 1.3) and almost never at 1.05 (0 to 4%). Removing the line from the
  prompt removed them, but did not add sections (INFERRED).
- **Unsupported numbers follow the same penalty.** They rise from 0 to 3% at 1.05 to 12 to 21% at
  1.15 and 1.3.
- **About 40% is the ceiling of everything tested.** Even at 1.05, most summaries still have
  two or three sections. Whatever limits the rest is not tested here.

None of this changes `EdgeRuntime`; the rule never made the repeat-penalty arms a basis for
adopting a sampler. The repeat-penalty result is OBSERVED on the host only.

**What this points to next** (HYPOTHESIS). Xylo already ships a repeat penalty of 1.05, so the
format gain from its sampler change is already in the app. The remaining gap, about 60% of
summaries without all four sections, may come from the 288-token budget, the length of the
input, or the model's size. The next useful test is the share of complete summaries on a 6 GB
iPhone at Xylo's shipped settings, and how it changes with the answer budget. (Corrected; see
[Errata](#errata).)

## Deviations

- **Power.** The protocol fixes the host "on AC power". This run was on battery
  (`conditions.txt`: "Now drawing from 'Battery Power'"), and the host slept during it. The run
  took about 6 hours of wall time for 29 minutes of compute.

  This does not affect the registered measures, which count tokens and text. It does affect
  timings: decode speeds here (median 62 to 96 tok/s) are not comparable with PoC 003's (99 to
  109), and `b-no-end-line`, which ran last, is the slowest arm. The 200 generations repeated
  from PoC 003 are token-identical, so the sampling itself did not change.
- **Exploratory additions.** The per-document comparisons and the count of documents with no
  complete output were added to `summarize.py` after the run. They are labeled as exploratory
  and did not affect the verdict.

## Errata

- **2026-10-09: the answer budget is not a candidate.** "What this points to next" named the
  288-token budget as a possible cause of the missing sections. This PoC's own results rule it
  out: 98 of 100 `b-qwen-recipe` outputs, and 100 of 100 `b-no-end-line` outputs, ended on the
  end-of-sequence token before the cap (Results, "Clean stop" and "Hit cap"). Incomplete
  outputs are also shorter than complete ones (median 101 tokens against 151 for
  `b-qwen-recipe`). A larger budget cannot add sections the model has already ended without.
  The original text stays above. The next step is now [PoC 005](../005-summary-heading-continuation),
  which tests what happens at the point where the model ends. The verdict and results are
  unchanged.
- **2026-10-09: Xylo's Summary prompt moved to a private overlay.** The text is confidential and is no longer in this repository. `prepare.py` reads it from `private/prompts.json`, which is gitignored; without that file it uses the generic stand-in in `generic/prompts.json` and prints a warning. The registered `inputs-xylo.jsonl` has SHA-256 `77263695c5ea77f372e7a8afcf97380deba040e688f694bfd4c016e71ac50341` (the same file as PoC 003's) and `inputs-no-end-line.jsonl` has `270ddef1764c54d1e73f929d6623e8a2116d975721117648826bf61813344f86`. `prepare.py` with the overlay rebuilds both byte for byte (checked 2026-10-09). Both files embed the prompt, so they are no longer committed. Where this README mentions the line that closes the worked example, its text is the overlay's `summary_end_line`. The stand-in has the same structure with different wording, so a replication that uses it tests a similar prompt, not Xylo's. Whether the original text can be shared with a reviewer is the author's decision. The verdict and results are unchanged.
- **2026-10-09: raw generations withheld from the public snapshot.** `results/raw/generations-xylo.jsonl`, `results/raw/generations-no-end-line.jsonl` hold some outputs that repeat fragments of Xylo's confidential Summary prompt, including its example. They are held in the lab's private archive until the lab decides how to publish them without that text. The summary files here were computed from the full outputs and are unchanged; they cannot be re-derived from this repository until the raw file is restored. Results and verdict are unchanged.

## Limits

- **Host only.** The host is not an iPhone. Metal numerics and speed differ, and there is no
  thermal pacing.
- **Narrow scope.** One model, one prompt with one edit, one answer budget, and English
  contracts only. The documents are legal text from SEC filings, not what Xylo's users scan.
- **Only three repeat penalties.** The repeat-penalty arms test 1.05, 1.15 and 1.3, under two
  sets of other settings. They do not find an optimum, and values below 1.05 are not tested.
- **Format, not content.** The heading check tests format, not whether each section is right;
  unsupported numbers remain only a proxy for faithfulness.
- **Private source app.** The prompt and the loop are copied in PoC 003 so the run does not
  depend on the app.

## Reproduce

```sh
cd poc/004-qwen-summary-format
./run.sh            # checks hashes, builds PoC 003's harness, writes both prompt variants, runs 600 generations
python3 summarize.py
```

The model must be at `models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` (the same file as PoC 003), and
CUAD at `data/CUAD_v1.zip` (downloaded by `run.sh` if missing).

## Replications

Replications of the host stage are open. The steps and the evidence standard are in
[CONTRIBUTING.md](../../CONTRIBUTING.md); open a Replication issue before running.

**Needs.** An Apple silicon Mac with a Swift 6 toolchain, and about 1.2 GB of free disk.

**Run** into a folder named `YYYY-MM-DD-<github-handle>-<device>`:

```sh
cd poc/004-qwen-summary-format
R=replications/2026-10-15-yourhandle-m2-air
OUT=$R/results/raw ./run.sh
python3 summarize.py $R/results
cp ../_template/REPLICATION.md $R/README.md   # then fill it in
```

On other hardware, the reproducibility check compares against PoC 003's host run and is not
expected to match; compare each hypothesis and decision criterion instead.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| None yet | | | |
