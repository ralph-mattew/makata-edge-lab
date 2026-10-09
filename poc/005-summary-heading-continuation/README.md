# PoC 005: Continuing a summary past an early end

| | |
|---|---|
| Status | Written up (host stage) |
| Verdict | Adopt (host stage): inserting the missing heading raises complete four-section summaries from 39% to 93%, with no measured rise in unsupported numbers |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet (founding reviewers being invited) |
| Source idea | The remaining gap in [PoC 004](../004-qwen-summary-format#verdict): at Xylo's shipped settings, about 60% of summaries still lack a section. PoC 004's own outputs show where they stop (Why it matters here) |
| Registered | 2026-10-09, in the commit that adds this file, before the first run |

## Question

At the sampler settings Xylo ships, Qwen2.5-1.5B-Instruct Q4_K_M ends its Summary before writing
all four sections in about 60% of outputs. When the model tries to end early, does inserting the
next section's heading and letting it continue raise the share of complete four-section
summaries? And does it do so without adding unsupported numbers or empty sections?

## Why it matters here

[PoC 004](../004-qwen-summary-format) found that the repeat penalty carries the format effect, and
Xylo already ships the low value (1.05). At that value 39% of summaries were complete on the host
(MEASURED, `b-qwen-recipe`). The rest are what Xylo's users see as a summary missing its Key
Points or Action Items.

PoC 004's raw outputs, read again before this registration, show how the incomplete summaries
end. These counts are on the 100 `b-qwen-recipe` generations (MEASURED, host):

- **The budget is not the limit.** 98 of 100 ended on the end-of-sequence token, before the
  288-token cap. Incomplete outputs are shorter than complete ones (median 101 tokens against
  151).
- **The model drops trailing sections.** Of the 61 incomplete outputs, 38 stop after Introduction
  and Summary, and 22 after Key Points. Action Items is missing from 61 outputs and Key Points
  from 38.
- **It is not a scoring artifact.** Allowing bold or plain-text headings finds the same 39 complete
  outputs as the registered `##` check.
- **It varies by seed more than by document.** 18 of the 20 contracts have at least one complete
  output in five seeds.

So the model can write all four sections on nearly every contract. On a given sample it
often ends at a section boundary instead. That makes the end of the output, not the prompt or the
budget, the place to intervene (INFERRED). This changes PoC 004's "what this points to next",
which named the answer budget; see the [errata](../004-qwen-summary-format#errata) there.

Two interventions at the end of the output are common in local inference:

1. **Insert the next heading.** When the model samples an end token while sections are missing,
   drop the end token, append the next section's heading, and keep sampling. The heading text is
   fixed, so the model only writes the content.
2. **Suppress the end token.** While sections are missing, make the end tokens impossible to
   sample, so the model must keep writing and write the heading itself.

Either would be a small change in Xylo's generation loop, and a candidate for a structured-output
helper in `EdgeRuntime` once a device run confirms it.

## Hypotheses

All HYPOTHESIS until measured. "Complete" is the PoC 003 measure: a clean stop, with all four
headings in order.

1. **H1.** `b-insert-heading` is complete in at least 80% of generations.
2. **H2.** `b-suppress-end` is complete in at least 80% of generations.
3. **H3.** Neither intervention raises the share of outputs with an unsupported number by more
   than 5 points over `b-shipped`.

## Method

Everything not listed here is PoC 003's method, unchanged:

- the model file (`Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`, SHA-256
  `1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370`);
- llama.swift 2.8901.0 (llama.cpp b8901, Metal), with PoC 003's fixed settings (context 4,096,
  `n_ubatch` 128, 2 threads, all GPU layers, flash attention off, 288-token budget, seeds 1 to 5,
  penalty window 256 generated tokens);
- the host (MacBook Pro, M4 Pro, 24 GB, macOS 26.5.1, on AC power);
- the 20 CUAD v1 contracts, their selection, normalization and 2,500-character cut, and Xylo's
  Summary prompt. The input file is built by PoC 003's own `prepare.py`, so it is byte-identical
  to PoC 003's `results/raw/inputs.jsonl`;
- the scoring, which [`summarize.py`](summarize.py) imports from PoC 003's `summarize.py`.

**Harness.** [`harness/`](harness) is a copy of PoC 003's harness with one addition: an
`intervention` per arm. With `none`, the loop behaves exactly as PoC 003's. The two
interventions act only while a later section is missing. "Later section" means the section after
the last of the four headings already in the output, by the same heading check the scorer uses.

- **`insert_heading`.** When the model samples an end token (end-of-sequence or `<|im_end|>`),
  the token is not added to the output. Instead the harness appends `\n\n## <next section>\n`,
  for example `\n\n## Key Points\n`, and decodes it, and sampling continues.
  - The inserted tokens count toward the 288-token budget. A heading is only inserted if it fits
    with at least one token to spare; otherwise the output ends there.
  - They enter the sampler's penalty window, like generated tokens.
  - The dropped end token stays in the sampler's history, because llama.cpp's
    `llama_sampler_sample` records it when it is sampled. So after an insertion the end token
    carries the presence and repeat penalties. An app using the same call would behave the same
    way.
  - Every insertion is recorded with its heading and position.
- **`suppress_end`.** Before each sampling step, the logits of the end tokens are set to minus
  infinity. Sampling is otherwise unchanged. Once Action Items is written, the model can end as
  usual.

A smoke test before registration ran the three arms on one made-up memo that is not in the
dataset, and `b-shipped` on contract 0, which PoC 003 already published. `b-shipped` matched PoC
003's tokens 5 of 5; both interventions produced four-section outputs on the memo.

**Arms.** These are in [`arms.json`](arms.json). All use the Qwen recipe Xylo ships: temperature
0.7, top_p 0.8, top_k 20, repeat penalty 1.05, frequency penalty 0, presence penalty 1.5.

| Arm | Intervention | Role |
|---|---|---|
| `b-shipped` | none | PoC 003's B and PoC 004's `b-qwen-recipe`: Xylo now. Control |
| `b-insert-heading` | insert_heading | H1, H3 and the decision rule |
| `b-suppress-end` | suppress_end | H2 and H3 |

**Order.** [`run.sh`](run.sh) runs the harness once, with the three arms interleaved inside each
(document, seed). That makes 20 documents × 5 seeds × 3 arms = 300 generations. It keeps the host
awake with `caffeinate` and warns if the host is not on AC power.

**Measurements.** As PoC 003 and 004: clean stop, hit cap, four sections, complete, any
unsupported number, exemplar leak, looping, END line, median generated tokens and decode speed.
One new measure:

- **Thin section:** a section present in the output with fewer than 15 characters of content,
  after list markers (`-`, `*`, `[ ]`, numbering) and whitespace are removed. An inserted heading
  that the model leaves empty, or fills with "None.", counts. Calibrated before registration on
  PoC 004's published outputs: 1 of 100 `b-qwen-recipe` outputs had a thin section.

Also recorded: the number of headings inserted per output.

**Reproducibility check.** `b-shipped` repeats PoC 003's B with the same model, inputs, seeds,
settings and host. `summarize.py` counts how many of its 100 generations are token-for-token
identical to PoC 003's `b-qwen-recipe`. All 100 are expected to match. A mismatch is reported
and investigated; it does not change the verdict.

## Decision rule

The rule compares `b-insert-heading` with `b-shipped`, on the complete rate. Apply the steps in
order; the first match wins. "Points" means percentage points of generations.

1. If `b-insert-heading`'s complete rate is less than 20 points above `b-shipped`'s, the verdict is
   **reject: no gain**.
2. Check five criteria:
   - **c1:** the complete rate is at least 30 points higher, and the lower bound of the 95%
     confidence interval is above 0. The interval comes from a document-level bootstrap with
     10,000 resamples and seed 0, as in PoC 003.
   - **c2:** `b-insert-heading` stops cleanly in at least 90% of generations. The end token is
     penalized after an insertion, so outputs may run to the cap.
   - **c3:** its unsupported-number share is no more than `b-shipped`'s plus 5 points.
   - **c4:** at most 10% of its outputs have a thin section.
   - **c5:** its exemplar-leak rate is at most 5%. A forced Action Items section may copy the
     example's action items.
3. If c1 to c5 all hold, the verdict is **adopt**. The lab recommends inserting missing headings
   in Xylo's Summary loop, and Xylo makes that change in a commit that cites this PoC. Moving the
   technique into `EdgeRuntime` needs a device run first.
4. If c1 holds but c3, c4 or c5 fails, the verdict is **reject: trade-off**.
5. Otherwise the verdict is **inconclusive**, naming the failing criteria.

`b-suppress-end` answers H2 and H3 only; it never changes the verdict.

This is a host-stage verdict. Carrying it over to iPhones is INFERRED until a 6 GB iPhone run
confirms it.

## Results

Run 2026-10-08 (UTC) on the host above, on AC power, 300 of 300 generations completed in
about 13 minutes. Every number here is MEASURED on the host unless tagged otherwise. Raw files
are in [`results/raw`](results/raw):

- `inputs.jsonl` (not committed; see Errata): the 20 inputs, byte-identical to PoC 003's (same `inputs_sha256`);
- `generations.jsonl`: every output, with its tokens, stop reason, timings and, for
  `b-insert-heading`, each inserted heading and its position;
- `arms.json`, `harness.log` and `conditions.txt`.

The tables below come from [`results/summary.md`](results/summary.md), which `summarize.py`
generates along with [`results/summary.json`](results/summary.json).

**Reproducibility check.** All 100 `b-shipped` generations are token-for-token identical to PoC
003's `b-qwen-recipe`. This is the third run of those 100 generations, and all three agree.

**Registered measures.** Each arm has 100 generations: 20 documents × 5 seeds.

| Arm | Clean stop | Hit cap | Four sections | Complete | Any unsupported number | Thin section | Exemplar leak | Loop | END line | Median tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| `b-shipped` | 98% | 2% | 39% | 39% | 3% | 1% | 0% | 1% | 4% | 131.5 |
| `b-insert-heading` | 94% | 6% | 96% | **93%** | 5% | 3% | 0% | 1% | 7% | 166.5 |
| `b-suppress-end` | 78% | 22% | 76% | 76% | 4% | 1% | 1% | 2% | 15% | 179.5 |

Number of distinct section headings found per arm (2 / 3 / 4; no output had fewer than 2):

| Arm | 2 / 3 / 4 |
|---|---|
| `b-shipped` | 39 / 22 / 39 |
| `b-insert-heading` | 2 / 2 / 96 |
| `b-suppress-end` | 17 / 7 / 76 |

`b-insert-heading` inserted no heading in 41 outputs, one in 52 and two in 7. Its 41 outputs
without an insertion are token-identical to `b-shipped`'s, as they should be: the intervention
only acts when the model tries to end early. Median decode speed was 90 to 94 tok/s in every arm.

The document-level bootstrap (10,000 resamples, seed 0) gives:

- **Complete, `b-insert-heading` − `b-shipped`:** +54 points, 95% CI [+44, +64].
- **Complete, `b-suppress-end` − `b-shipped`:** +37 points, 95% CI [+27, +46].
- **Any unsupported number, `b-insert-heading` − `b-shipped`:** +2 points, 95% CI [0, +5].
- **Any unsupported number, `b-suppress-end` − `b-shipped`:** +1 point, 95% CI [0, +3].

**Hypotheses.**

1. **H1, held.** `b-insert-heading` was complete in 93% of generations, against a threshold of
   80%.
2. **H2, did not hold.** `b-suppress-end` was complete in 76%. In 22% it ran to the 288-token cap,
   17 of those 22 with only two sections.
3. **H3, held.** Unsupported numbers rose by 2 points with `b-insert-heading` and 1 point with
   `b-suppress-end`, both within the 5-point limit.

**Decision rule.** `b-insert-heading` against `b-shipped`: +54 points complete (step 1 passed).
c1 (+54 points, CI lower bound +44), c2 (94% clean), c3 (5% against 3% + 5), c4 (3% thin) and c5
(0% leak) all pass.

**Exploratory** (added to `summarize.py` after the run and labeled there as not registered):

- `b-insert-heading` gave more complete outputs than `b-shipped` on 19 of 20 documents and the same
  number on 1; it was never lower. `b-suppress-end`: higher on 17, equal on 3.
- Documents with no complete output in five seeds: 2 under `b-shipped`, 0 under
  `b-insert-heading`, 1 under `b-suppress-end`.
- Inserted headings: Key Points 36 times, Action Items 30 times.
- Of the 7 incomplete `b-insert-heading` outputs, 6 ran to the cap. Two of those had no insertion
  and match `b-shipped`.
- **When the end token is suppressed, the model does not write the next heading.** It keeps
  writing the section it was in. The outputs that ran to the cap mostly stretch the Summary
  section, and many drift into describing the prompt's own format rules (OBSERVED, from reading
  the 22 outputs; a rough text search finds words such as "format", "example" or "END" in 19 of
  them).
- **Forced Action Items look like the model's own.** In sections under an inserted Action Items
  heading, 48 of 75 lines (64%) start with a generic verb such as "ensure", "review" or
  "confirm". In Action Items sections the model wrote unprompted, in either arm, the share is
  149 of 238 (63%). The verb list was chosen after reading the outputs, so this is a rough check
  (OBSERVED). Several forced sections say "None" or "None specified", which the thin-section
  measure counts.

## Verdict

**Adopt** (decision rule, step 3). On the host, inserting the next section heading when
Qwen2.5-1.5B tries to end early raises complete four-section summaries from 39% to 93%. It does
not measurably raise unsupported numbers, empty sections or copying from the prompt's example.
Outputs that were already complete are unchanged, token for token.

Suppressing the end token also helps, to 76%, but costs more: one output in five runs to the
cap, because the model keeps writing the current section instead of starting the next. A
heading the model does not have to write is the part that matters (INFERRED from the two arms).

The lab recommends inserting missing headings in Xylo's Summary loop. Under the rule, that change
is made in Xylo in a commit that cites this PoC. Moving the technique into `EdgeRuntime` waits
for a device run.

This verdict is for the host. On an iPhone it is INFERRED: the sampling code is the same, but
Metal numerics differ, so the exact outputs will too.

**What this points to next** (HYPOTHESIS).

- **A device run.** The same three arms on a 6 GB iPhone, to confirm the complete rate and see
  the cost in time: `b-insert-heading`'s median output is 35 tokens longer.
- **Content, not only format.** The checks here show that each section exists. Whether a forced
  Action Items section suits a contract that has no real action items is not tested. A content
  check, by a reader or against a reference, is the open question.

## Deviations

- **Exploratory additions.** The per-document comparisons, the counts of inserted headings, the
  sections found in capped `b-suppress-end` outputs, and the action-item verb check were added to
  `summarize.py` after the run. They are labeled as exploratory and did not affect the verdict.

## Errata

- **2026-10-09: Xylo's Summary prompt moved to a private overlay.** The text is confidential and is no longer in this repository. `prepare.py` reads it from `private/prompts.json`, which is gitignored; without that file it uses the generic stand-in in `generic/prompts.json` and prints a warning. The registered `inputs.jsonl` has SHA-256 `77263695c5ea77f372e7a8afcf97380deba040e688f694bfd4c016e71ac50341` (recorded in `results/raw/conditions.txt`; it is PoC 003's file). `prepare.py` with the overlay rebuilds it byte for byte (checked 2026-10-09). The file embeds the prompt, so it is no longer committed, and `summarize.py` needs it rebuilt first. The stand-in has the same structure with different wording, so a replication that uses it tests a similar prompt, not Xylo's. Whether the original text can be shared with a reviewer is the author's decision. The verdict and results are unchanged.
- **2026-10-09: raw generations withheld from the public snapshot.** `results/raw/generations.jsonl` holds some outputs that repeat fragments of Xylo's confidential Summary prompt, including its example. It is held in the lab's private archive until the lab decides how to publish them without that text. The summary files here were computed from the full outputs and are unchanged; they cannot be re-derived from this repository until the raw file is restored. Results and verdict are unchanged.

## Limits

- **Host only.** The host is not an iPhone. Metal numerics and speed differ, and there is no
  thermal pacing.
- **Format, not content.** The checks test that each section is there and not empty. They do not
  test whether a forced Action Items section is right for the document; unsupported numbers remain
  only a proxy for faithfulness. A contract may have no real action items, and the model is then
  pushed to write some.
- **Narrow scope.** One model, one prompt, one sampler setting, and English contracts only. The
  documents are legal text from SEC filings, not what Xylo's users scan.
- **Two interventions only.** Grammar-constrained decoding, and prompts that ask for the missing
  section in a second call, are not tested.
- **Private source app.** The prompt and the loop are copied in PoC 003 so the run does not
  depend on the app.

## Reproduce

```sh
cd poc/005-summary-heading-continuation
./run.sh            # checks hashes, builds the harness, writes the inputs, runs 300 generations
python3 summarize.py
```

The model must be at `models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` (the same file as PoC 003), and
CUAD at `data/CUAD_v1.zip` (downloaded by `run.sh` if missing).

## Replications

Open. None yet. The steps and the evidence standard are in
[CONTRIBUTING.md](../../CONTRIBUTING.md); use [`_template/REPLICATION.md`](../_template/REPLICATION.md).
