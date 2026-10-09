# PoC 008: A plain "not in the sections" instruction for contract questions

| | |
|---|---|
| Status | Written up (host stage) |
| Verdict | Headline, FoundationModels: reject, no gain (the rule alone changes nothing; the reminder after the question adds 18.3 points of absent rate but costs 7.2 points of key facts). Gemma 4 E2B: adopt (host stage), the rule lifts its absent rate from 64.9% to 80.1%. Qwen2.5-1.5B: reject, trade-off |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet (founding reviewers being invited) |
| Source idea | [PoC 006](../006-doc-qa-fm-gemma-qwen): on contract questions whose answer is not in the sections, FoundationModels says so on 39% of items and Qwen2.5-1.5B on 33% (PoC 006's detector), against 65% for Gemma 4 E2B, although Xylo's chat instruction (private app, v1.2.0) already tells every backend to say so |
| Registered | 2026-10-09, in the commit that adds this file, before the first run |

## Question

At Xylo's shipped settings, does adding a plain instruction to reply with a fixed sentence when the
sections do not contain the answer raise the share of unanswerable contract questions that
FoundationModels, Gemma 4 E2B and Qwen2.5-1.5B flag as absent, without cutting their answers on
questions the sections do answer?

## Why it matters here

PoC 006 found that gap filling is not a 1.5B-model problem. Given three sections that do not contain
the answer, FoundationModels, Xylo's default chat backend on 8 GB iPhones with Apple Intelligence,
answers anyway on 61% of items, and Qwen2.5-1.5B, the only chat model on 6 GB iPhones, on 67% (with
PoC 006's frozen detector; 56% with its punctuation fix, see below). Gemma 4 E2B, a 3.5 GB download, does so on 35%.

Xylo's chat instruction already has one general sentence telling the model to say so in one sentence
when the question cannot be answered from the sections. It does not ask the model to check before
answering, does not forbid a related answer instead, and does not fix the reply. Whether a firmer
version closes the gap is not measured:

1. **FoundationModels, the 8 GB default.** If a firmer instruction brings FoundationModels near
   Gemma's 65%, the download that PoC 006 recommended for Gemma matters less.
2. **The 6 GB tier.** Qwen has no other chat model on that tier. A prompt change is the cheapest
   guard available: no download, no code beyond one string.
3. **A fixed reply** can be recognised exactly by the app, which would make a later guard or UI
   treatment simple. That is a reason for choosing it here, not something this PoC measures.

The cost to watch is over-refusal: a model that is told to refuse when unsure may refuse when the
answer is there.

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items. "Says absent" and "answers"
are the detector's two calls, defined under Measurements.

1. **H1** (FoundationModels follows the instruction). Adding the rule raises FoundationModels'
   absent rate on unanswerable items by at least 15 points, and lowers its answer rate on
   answerable items by no more than 5.
2. **H2** (the 1.5B model follows it less). Qwen's absent-rate gain from the rule is at least 10
   points smaller than FoundationModels'.
3. **H3** (placement). Repeating the instruction after the question raises the absent rate by a
   further 5 points or more over the rule alone, for FoundationModels and for Qwen.

## Method

**Host.** The host of PoC 006: MacBook Pro (Mac16,8), Apple M4 Pro, 24 GB, on AC power. The macOS
build, the toolchain and the power state at the start are recorded in `results/raw/conditions.txt`.
The power source is also logged before every stage in `results/raw/power.log`.

**Models, tooling, data, items and sections.** Identical to PoC 006; see its README for the files,
hashes and licenses. The same 986 CUAD items (504 answerable, 482 unanswerable, from 392
contracts) with the same three fixed sections each. `prepare.py` runs PoC 006's `prepare.py`, so
the base prompts are PoC 006's, and `run.sh` checks that `items.jsonl` and `arms.json` are byte
identical to PoC 006's. The harness is PoC 006's, unchanged (`GGUFQA` and `FMQA`).

**Prompt variants.** Three, in [`variants.json`](variants.json):

| Variant | What is added to PoC 006's prompt |
|---|---|
| `base` | Nothing. PoC 006's prompt, reproduced from the same inputs (its SHA-256 is recorded in `conditions.txt` and must equal PoC 006's) |
| `rule` | After the system instruction, in all three prompt forms: *Before you answer, check whether the sections contain the answer. If they do not, reply exactly: "The provided sections do not contain this." Do not guess, and do not answer with related information instead.* |
| `rule-q` | The same, and one line after the question: *If the sections do not contain the answer, reply exactly: "The provided sections do not contain this."* |

The rule is joined to the system instruction with a space (for Qwen, before ` /no_think`).
The reminder goes on its own line after `Question: …` for Gemma and Qwen, and after the bare
question for FoundationModels. Xylo's own instruction text is not published (see PoC 006, Errata);
`prepare.py` uses the private overlay if present, or the generic stand-in. The added text is new
and public.

**Arms.** Three backends at the settings of PoC 006's [`arms.json`](arms.json), each on three
variants: nine arms. One run per arm, seed 1 for the GGUF arms; FoundationModels cannot be seeded.
`run.sh` runs Gemma, then Qwen, then FoundationModels, each over `base`, `rule` and `rule-q`.

**Measurements.** [`summarize.py`](summarize.py) uses PoC 006's scoring unchanged (output
clean-up, answer rate, absent rate, balanced accuracy, key fact right, any unsupported number),
and PoC 006's bootstrap: contracts are resampled with all their items, the same resample for every
arm, 10,000 resamples, seed 0. Only the detector changes.

- **Detector v2.** PoC 006's detector made two errors in its audit: it missed a "No" behind
  leading punctuation (`: No`, `] No`, `*-No*`; 74 of Qwen's 986 outputs), and it read "No later
  than ..." as absent. Detector v2 drops leading characters that are not letters or digits before
  matching, and treats "No/None" followed by a comparison word (later, earlier, sooner, more, less,
  fewer, greater, longer, shorter, higher, lower), an optional "-ly" adverb and "than" as an answer.
  Every other pattern is PoC 006's. The changes were made from PoC 006's disagreements and
  tested on PoC 006's outputs only, before any PoC 008 output existed: on PoC 006's 120 audited
  outputs v2 agrees with the reader on 120, against 115 for v1, and over PoC 006's run 1 it changes
  78 Qwen calls and 1 Gemma call. The result tables show v1 beside v2.
- **Fixed phrase.** The share of outputs that are exactly the reply the rule asks for
  (descriptive).
- **Descriptive:** errors by type, hitting the answer budget, median answer length and time,
  per-category absent and answer rates.
- **Does `base` reproduce PoC 006?** The share of items where `base` makes the same call as
  PoC 006's run 1 (v1 calls). PoC 006's run-to-run agreement was 93.6% for FoundationModels, 94.8%
  for Gemma and 73.5% for Qwen, so values around those are the noise floor, not a failure.

**Detector audit.** As in PoC 006, with 40 outputs per backend drawn over all three variants (120
in all), shuffled, with no backend, variant or detector call on the sheet. A reader labels each
*answer* or *absent* by the definition above. The author may label the sheet; if not, an AI model
does, and the write-up names the reader and says so. Agreement is reported overall, per backend, for
v1, and without the outputs that are exactly the fixed phrase (which are easy by construction).

**Smoke test, before registration.** The two variants ran on four questions about a made-up services
agreement that is not in CUAD (two answerable, two not), on all three backends. Every run ended normally.
FoundationModels and Gemma answered the two answerable questions and replied that the sections do not contain
the answer to the other two. Qwen with `rule` did the same; Qwen with `rule-q` replied with the fixed sentence
to all four, including the two answerable. The texts were not changed after this.

## Decision rule

Compares a treated variant with `base` for one backend, on the single run of each. Apply the steps
in order; the first match wins.

1. If the detector (v2) agrees with the reader on fewer than 90% of audited outputs, the verdict is
   **inconclusive: detector not valid**.
2. If the balanced-accuracy gain is less than 2 points, the verdict is **reject: no gain**.
3. Check three criteria:
   - **c1:** the balanced-accuracy gain is at least 5 points, and the lower bound of its 95%
     confidence interval is above 0.
   - **c2:** the answer rate on answerable items is no more than 5 points below `base`'s.
   - **c3:** the key-fact rate is no more than 5 points below `base`'s.
4. If c1 to c3 hold, the verdict is **adopt (host stage)**. If c1 holds but c2 or c3 fails, it is
   **reject: trade-off**. Otherwise it is **inconclusive**, naming the failing criteria.

The rule is applied to each backend. For each, `rule` is checked first, and `rule-q` only if `rule`
is not adopted; an adopt on `rule-q` is reported as such. **The headline verdict is
FoundationModels', the 8 GB default and the backend the question started from.** Gemma and Qwen get
the same rule and their own outcomes. Two variants and three backends make six comparisons, with
no correction for multiple comparisons; the intervals are 95% each.

An adopt means the lab recommends adding the text to Xylo's chat instruction for that backend, where
the host result is likely to carry (see Limits). Changing the prompt is Xylo's decision, and an 8 GB iPhone
run comes first for FoundationModels, whose phone model may differ.

## Results

Run 2026-10-09 on the host above from the protocol commit `c69faae` (the merge of the registration), with
no tracked file changed. The run took about 3 hours (14:29 to 17:31, UTC+8): Gemma arms about 25 minutes
each, Qwen about 16, FoundationModels about 19. Every number here is MEASURED on the host unless tagged
otherwise. Raw files are in [`results/raw`](results/raw): `items.jsonl`, `gen-<backend>-<variant>.jsonl`
(every output), the nine `harness-*.log` files, `arms.json`, `conditions.txt` and `power.log`. The tables come
from [`results/summary.md`](results/summary.md), which `summarize.py` generates along with
[`results/summary.json`](results/summary.json). The audit sheet, its key and the labels are in
[`results/audit`](results/audit).

The run covered 986 items (504 answerable, 482 unanswerable) from 392 contracts, 8,874 outputs in all. No
output was an error or empty, and FoundationModels raised no guardrail refusal. At most 1.0% of any arm's
outputs hit the answer budget. `base` reproduces PoC 006's prompt: its inputs have the same SHA-256 as
PoC 006's (`conditions.txt`), and the same call as PoC 006's run 1 on 92.4% of items for FoundationModels
(unseeded; PoC 006's run-to-run agreement was 93.6%) and 100% for Gemma and Qwen (seeded).

**By arm** (percent of items; the answer and absent rates use detector v2; fixed phrase is the share of
outputs that are exactly the requested reply):

| Backend | Variant | Answers answerable | Says absent on unanswerable | Balanced | Key fact right (n=181) | Any unsupported number | Fixed phrase, all | Fixed phrase, answerable | Median words | Median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| `fm` | `base` | 86.3 | 39.2 | **62.8** | 82.3 | 4.4 | 0.0 | 0.0 | 18 | 815 |
| `fm` | `rule` | 90.7 | 38.6 | **64.6** | 86.7 | 3.0 | 2.0 | 0.0 | 21 | 889 |
| `fm` | `rule-q` (battery, see Deviations) | 83.3 | 57.5 | **70.4** | 75.1 | 2.1 | 24.3 | 9.1 | 12 | 747 |
| `gemma-e2b` | `base` | 88.5 | 64.9 | **76.7** | 90.1 | 0.2 | 0.0 | 0.0 | 19 | 1,371 |
| `gemma-e2b` | `rule` | 84.9 | 80.1 | **82.5** | 87.8 | 0.1 | 0.3 | 0.0 | 19 | 1,376 |
| `gemma-e2b` | `rule-q` | 81.9 | 82.8 | **82.4** | 88.4 | 0.1 | 5.9 | 1.4 | 19 | 1,447 |
| `qwen-1.5b` | `base` | 78.6 | 45.0 | **61.8** | 77.3 | 3.0 | 0.0 | 0.0 | 6 | 856 |
| `qwen-1.5b` | `rule` | 75.0 | 59.5 | **67.3** | 71.8 | 1.2 | 16.2 | 7.9 | 8 | 910 |
| `qwen-1.5b` | `rule-q` | 31.0 | 89.6 | **60.3** | 27.1 | 0.1 | 53.4 | 48.8 | 7 | 878 |

On unanswerable items the share that fills the gap (one minus the absent rate), `base` to `rule`: FoundationModels
61% to 61%, Gemma 35% to 20%, Qwen 55% to 40%. With `rule-q`: FoundationModels 43%, Gemma 17%, Qwen 10%.

Detector v1 (PoC 006's, frozen) is in `results/summary.md` for comparison. It differs from v2 by 0.5 points or
less everywhere except Qwen, where it under-counts the absent rate of `base` (32.6% against 45.0%) and, by 0.8 to 1.4 points, of `rule`
(58.7% against 59.5%) and `rule-q` (88.2% against 89.6%). Under v1 Qwen's `rule` gain would be +26.1 points of absent rate and +10.2 of balanced
accuracy, larger than under v2 (+14.5 and +5.5). The decision uses v2.

**Decision rule** (each treated variant against `base`, same backend; contract-level bootstrap, 10,000
resamples, seed 0; points, with 95% CI). Step 1 passed: the detector agrees with the reader on 97.5% of 120
audited outputs, above 90% (see Detector audit).

| Backend | Variant | c1, balanced accuracy (needs at least +5, CI above 0) | c2, answer rate (no worse than -5) | c3, key fact (no worse than -5) | Outcome |
|---|---|---|---|---|---|
| `fm` | `rule` | +1.9 [-0.2, +4.0] | +4.4 [+2.3, +6.6] | +4.4 [+0.6, +8.5] | **reject: no gain** (step 2, gain below 2) |
| `fm` | `rule-q` | **+7.6** [+4.9, +10.4] | -3.0 [-6.2, +0.4] | **-7.2** [-13.1, -1.6] | **reject: trade-off** (c3 fails) |
| `gemma-e2b` | `rule` | **+5.8** [+3.7, +8.0] | -3.6 [-6.1, -1.0] | -2.2 [-4.4, -0.5] | **adopt (host stage)** |
| `gemma-e2b` | `rule-q` | **+5.6** [+3.5, +7.8] | **-6.5** [-9.3, -3.9] | -1.7 [-4.6, +1.1] | reject: trade-off (c2 fails) |
| `qwen-1.5b` | `rule` | **+5.5** [+2.5, +8.4] | -3.6 [-7.6, +0.4] | **-5.5** [-13.0, +2.3] | **reject: trade-off** (c3 fails by 0.5) |
| `qwen-1.5b` | `rule-q` | -1.5 [-4.7, +1.7] | **-47.6** [-52.1, -43.0] | **-50.3** [-58.1, -42.5] | reject: no gain (step 2) |

Per the rule, `rule-q` is checked only if `rule` is not adopted. For Gemma `rule` is adopted, so its `rule-q` row
is reported only. The backend verdict is `rule`'s unless `rule-q` alone is adopted, which did not happen. The
change in absent rate and answer rate on their own, in points (95% CI): FoundationModels `rule` -0.6 [-4.1, +2.8]
and +4.4 [+2.3, +6.6]; FoundationModels `rule-q` +18.3 [+13.8, +22.6] and -3.0 [-6.2, +0.4]; Gemma `rule` +15.1
[+12.0, +18.5] and -3.6 [-6.1, -1.0]; Qwen `rule` +14.5 [+10.1, +19.0] and -3.6 [-7.6, +0.4]; Qwen `rule-q` +44.6
[+40.3, +48.9] and -47.6 [-52.1, -43.0].

**Hypotheses.**

1. **H1, did not hold.** The rule leaves FoundationModels' absent rate where it was (-0.6 points, CI [-4.1, +2.8];
   the threshold is +15). It raises the answer rate by 4.4 points. FoundationModels with `rule` still fills the gap
   on 61% of unanswerable items.
2. **H2, did not hold, and the direction is the other way.** Qwen's absent-rate gain from the rule (+14.5) is 15.1
   points larger than FoundationModels' (CI [+9.5, +20.8]), not 10 points smaller.
3. **H3, held.** The reminder after the question adds 18.9 points of absent rate over the rule alone for
   FoundationModels (CI [+14.4, +23.2]) and 30.1 for Qwen (CI [+25.9, +34.2]). For Qwen it came with answers on
   answerable items falling from 75.0% to 31.0%; for FoundationModels the `rule-q` arm ran on battery.

**Detector audit.** 40 outputs per backend over all variants, 120 in all, labelled by an AI reader (see
Deviations). Agreement: **97.5%** (117 of 120) for v2 and 96.7% for v1. By backend (v2): FoundationModels 100%, Gemma
100%, Qwen 92.5%. Without the 13 audited outputs that are exactly the fixed phrase: 97.2%. All three
disagreements are Qwen outputs: `No notice is needed to stop the contract from renewing.` and `- No change.` (v2 reads
a "No <word>" opening as absent; the reader read an answer), and one output that repeats the reminder sentence (v2
reads it as absent; the reader read an answer, as it does not say the sections lack the information). A literal
reading of "starts with No" would make the first two agree and raise agreement to 99.2% (INFERRED, by hand count).

**Exploratory, not registered.** Computed from the same outputs after the decision. The fixed-phrase share on
*unanswerable* items is 40.2% for FoundationModels `rule-q`, 4.1% for FoundationModels `rule`, 0.6% for Gemma
`rule`, 10.6% for Gemma `rule-q`, 24.9% for Qwen `rule` and 58.3% for Qwen `rule-q`. Gemma's `rule` gain therefore
does not come from the template: it flags absence in its own words ("The provided sections do not contain
information about ...", "The document does not state ..."), which the detector and the audit read as absent.
FoundationModels `rule-q` uses the template on 40.2% of unanswerable items and on 9.1% of answerable ones. Qwen
`rule-q` uses it on 48.8% of answerable items, which accounts for most of its collapse. Per-category tables of
answer and absent rates are in `results/summary.md`.

## Verdict

**Headline, FoundationModels: reject, no gain** (decision rule, step 2, for `rule`). Adding the rule to
FoundationModels' prompt changes its balanced accuracy by +1.9 points (CI [-0.2, +4.0]), below the 2 points the rule
requires. Its absent rate does not move (39.2% to 38.6%); it answers answerable items more often (+4.4 points) and
gets key facts right more often (+4.4). The rule alone makes FoundationModels answer more, not flag more. The
reminder after the question does move it: `rule-q` raises the absent rate by 18.3 points (to 57.5%) and balanced
accuracy by 7.6 points, but lowers the key-fact rate by 7.2 points (CI [-13.1, -1.6]), past the 5-point limit, so
the registered outcome is **reject: trade-off**. That arm ran on battery, so a re-run on AC power would settle it
(see Deviations and next steps).

**Gemma 4 E2B: adopt (host stage), `rule`.** The rule raises balanced accuracy by 5.8 points (CI [+3.7, +8.0]) by
raising the absent rate from 64.9% to 80.1%, so the share of unanswerable items on which it fills the gap falls from
35% to 20%. The answer rate falls by 3.6 points (CI [-6.1, -1.0]) and the key-fact rate by 2.2 (CI [-4.4, -0.5]),
both inside the 5-point limit. The lab recommends adding the rule text to Xylo's Gemma chat instruction. **No
change to Xylo follows from this PoC alone**, and the change is Xylo's decision.

**Qwen2.5-1.5B: reject, trade-off.** The rule raises Qwen's absent rate from 45.0% to 59.5% and balanced accuracy by
5.5 points (CI [+2.5, +8.4]), with 3.6 fewer answers on answerable items. Its key-fact rate falls by 5.5 points,
0.5 past the limit, with a wide interval (CI [-13.0, +2.3]); the registered outcome is reject, and the data do not
say the key-fact loss is real. The reminder is not usable: with `rule-q` Qwen answers 31% of answerable items and
replies with the fixed sentence to 49% of them. On the 6 GB tier a prompt change alone is not a safe guard here.

This verdict is for the host. On an iPhone it is INFERRED for Gemma and Qwen, which run the same weights and
sampler, and not for FoundationModels, whose phone model may differ.

**What this points to next** (HYPOTHESIS).

- **A re-run of FoundationModels `rule-q` on AC power**, with a second sample, to remove the power deviation and
  measure how much that arm moves between runs.
- **Reminder only for FoundationModels.** Placement mattered: the rule at the top did nothing and the line after
  the question moved the absent rate. Whether the line after the question works without the rule is untested.
- **Qwen needs a guard that is not a prompt**, or a different 1.5B-class model, since the prompt either does little
  or makes it refuse everything. A model comparison (Qwen2.5-1.5B against Qwen3 and LFM2) is next in the queue and would take this up.
- **A phone run** of Gemma with the rule, and of FoundationModels, on an 8 GB iPhone.

## Deviations

- **FoundationModels `rule-q` ran on battery.** The Mac was on AC power at the start (`conditions.txt`) and at
  the start of every stage except the last two lines of `power.log`: the `fm` `rule-q` stage began on battery at
  17:13 and the run ended at 17:31, both on battery. The system log shows the Mac on battery from 17:10:04 to
  18:05:09 (UTC+8). The protocol says AC power. FoundationModels' outputs are not expected to depend on the
  power source, but that is not verified; the median time of this arm (747 ms) is the lowest of the three
  FoundationModels arms, so it shows no slowdown. A shorter drop of 6 seconds (15:07:01 to 15:07:07) fell inside
  the Gemma `rule` stage. The decision rule uses no timing.
- **The audit reader is an AI model.** The protocol allows it and says the write-up names the reader. The reader
  was GitHub Copilot (Claude Sonnet 5.5), the assistant that wrote the harness and `summarize.py` and ran this
  PoC. It labelled from the blinded sheet, with no backend, variant or detector call on it, and did not open
  `key.json` until the labels were written. It had already seen the run's aggregate tables. It read "No, ..." to a
  yes-or-no question as *absent* and "Yes, ..." as *answer*, as in PoC 006. It departed from a literal reading
  of "starts with No" in two cases that are not a negative reply to a yes-or-no question (`No notice is needed ...`,
  `- No change.`), and it read an output that only repeats the reminder sentence as an *answer*. No human has
  labelled the sheet. A human check of the three disagreements and of a sample of the rest would make the 97.5%
  more reliable.
- **One raw output redacted before commit.** Qwen `base`, item 79, answered by reciting part of the private chat
  prompt, as it did in PoC 006's run 1. Its `text` and `tokens` in `results/raw/gen-qwen-1.5b-base.jsonl` are
  replaced with a placeholder. `summarize.py` gives a byte-identical `summary.json`, `summary.md` and audit sheet
  before and after (checked 2026-10-09). The output was already counted in the results. No other output in
  `results/` contains a six-word sequence of the private prompt (checked 2026-10-09); `inputs-*.jsonl`, which
  embed it, are not committed.

## Limits

The first group was written before the run.

- **The rule prescribes the reply.** Under `rule` and `rule-q`, a high absent rate partly
  measures compliance with a template. That is what a shipped change would be, but it is not the
  same as the models finding the gap unprompted. The fixed-phrase share and the answer-rate
  guard show how much of the gain is the template.
- **One run per arm.** FoundationModels cannot be seeded, and its calls moved 6% between PoC 006's
  two runs. The bootstrap resamples contracts, not repeated samples of one item, so a gain of a
  few points is within noise. The `base` reproduction check shows the floor.
- **Detector v2 was shaped by PoC 006's disagreements.** It is untested on new outputs until the
  audit. "No <word>" openings that are not a comparison ("No party to this Agreement has ...") are
  still read as absent. "No" counts as absent on yes-or-no questions, as in PoC 006.
- **The audit reader is probably an AI model**, which also built the harness. Agreement shows that
  the detector matches the written definition, not that a person would label the same.
- **Mac, not iPhone.** The same limit as PoC 006 for FoundationModels, Gemma and Qwen.
- **Not the app's full prompt or retrieval, single turn, polarity not correctness, CUAD's
  labels.** As in PoC 006.
- **Over-refusal is measured by answer rate and key facts only.** An answer that is present but
  wrong is not distinguished from a right one outside the six key-fact categories.
- **The base prompt may differ in a replication.** Without the private overlay, `base` is a
  generic stand-in with the same structure, and the rule is added to a different prompt.

Added after the run:

- **FoundationModels `rule-q` ran on battery** (Deviations), and its key-fact loss (-7.2 points) is what turns
  that arm from adopt to trade-off. The interval is wide (CI [-13.1, -1.6]). The result stands as registered and
  is the arm a re-run would check.
- **Qwen's `rule` key-fact loss is 0.5 points past the limit,** with a CI that spans zero (CI [-13.0, +2.3], 181
  items), so the "trade-off" outcome rests on a point estimate near the threshold.
- **The `rule-q` arms test one placement, one wording.** The reminder duplicates the rule's reply sentence.
  Qwen's collapse is for this text, and a shorter or differently placed reminder may not do it.
- **Over-refusal is measured on the sections only.** The answer rate counts any non-absent reply, and the key-fact
  rate covers six categories. A reply that answers wrongly counts as an answer, as in PoC 006.

## Reproduce

From a clean checkout on an Apple silicon Mac with macOS 26.4 or later, Apple Intelligence on, and
Xcode 26:

```sh
cd poc/008-absence-instruction-doc-qa
# models and data: run.sh prints the download commands if they are missing;
# on APFS, cp -c from PoC 006's models/ and data/ clones them
./run.sh
# summarize.py writes results/audit/sheet.csv on the first call; label it into
# results/audit/labels.csv (a copy with the label column filled in), then:
python3 summarize.py
```

`results/raw/inputs-<variant>.jsonl` (about 13 MB each, with the prompts) is not committed;
`prepare.py` rebuilds it byte for byte from the CUAD zip and the overlay, and `conditions.txt`
records the SHA-256 of each. The PoC needs PoC 006's folder: it imports its `prepare.py` and
`summarize.py` and builds its harness.

## Replications

A replication needs an Apple silicon Mac with Apple Intelligence (for `fm`) and about 6 GB of free
memory. Point the run at a replication folder with `OUT=replications/<name>/results/raw ./run.sh`,
and summarize with `python3 summarize.py replications/<name>/results`.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| | | | |
