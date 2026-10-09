# PoC NNN: Title

| | |
|---|---|
| Status | planned / host run / device run / written up |
| Verdict | adopt / reject / inconclusive |
| Authors | Name ([@handle](https://github.com/handle)) |
| Reviewers | Name ([@handle](https://github.com/handle)), or none |
| Source idea | Paper or repo, with link and version or commit |
| Registered | YYYY-MM-DD, commit of this file before the first run |

## Question

One sentence, answerable with a measurement.

## Why it matters here

Which limit in which app this would move, with the current number and where it comes from.

## Hypothesis

What the result is expected to be, stated so a result can contradict it. Tag: HYPOTHESIS.

## Method

- Models: exact files, source URL, SHA-256, license.
- Tooling: versions or commits.
- Devices: host and target, OS build, memory, power state.
- Settings: what varies, what is held fixed.
- Measurements: what is recorded, how, how many repetitions.
- Data: what inputs, where from, license.

## Decision rule

Written before the first run. For example: *adopt if X improves by at least N while Y degrades by
no more than M on the target device; reject if ...; otherwise inconclusive.*

## Results

Link the raw files in `results/`. Every number tagged MEASURED, OBSERVED or INFERRED, with the
device it came from.

## Verdict

Adopt, reject or inconclusive, and why, against the decision rule.

## Deviations

Dated changes to the method after registration, and why.

## Limits

What this does not show.

## Reproduce

Commands from a clean checkout.

## Replications

What hardware a replication needs, how to point the run at a replication folder, and a table:

| Date | Device | Authors | Outcome |
|---|---|---|---|
| | | | |
