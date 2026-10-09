# Contributing

Thanks for considering a contribution. The lab's results are only as good as the evidence behind
them, so this guide is mostly about evidence.

## What the lab accepts right now

| Contribution | How |
|---|---|
| **Replication** of an existing PoC on your hardware | Pull request, described below |
| Fix to a PoC script that blocks a replication | Pull request, kept small |
| Bug in the Swift package | Issue, or a pull request with a test |
| Possible error in a published result | Issue, using the "Possible error in a result" form |
| Questions, PoC ideas, papers worth testing | [Discussions](https://github.com/ralph-mattew/makata-edge-lab/discussions) |

New PoCs and new code under `Sources/` are not open to outside contributions yet. They will be
once the review process has been tried on replications. Ideas for either are welcome in Discussions
now.

## Replicating a PoC

A replication runs a PoC's registered method, unchanged, on different hardware and reports what
it found. A result that disagrees with the original is as publishable as one that agrees.

1. Open a **Replication** issue naming the PoC and your device, so two people don't run the same
   thing without knowing.
2. Follow the PoC's *Reproduce* and *Replications* sections. Don't change the method. If you have
   to (a different tool version, a setting your device can't run), write down what and why.
   PoCs 003 to 007 use text from a private app that is not published; without it they run on
   the stand-ins in [`generic/`](generic), which tests a similar prompt, not the registered one (see
   [`generic/README.md`](generic/README.md)).
3. Put everything in `poc/NNN-slug/replications/YYYY-MM-DD-<github-handle>-<device>/`:
   - `README.md`, copied from [`poc/_template/REPLICATION.md`](poc/_template/REPLICATION.md);
   - `results/raw/`: every file the run script wrote, unedited;
   - `results/summary.md` and `results/summary.json`, if the PoC has a summarize script.
4. Open a pull request. Every commit needs a sign-off (see below).

## Evidence standard

Every pull request that adds results must have:

- **Raw output** as the tools wrote it, not retyped or trimmed.
- **Conditions**: device model, chip, memory, OS build, power state, tool versions.
- **Hashes**: model and data files match the PoC's SHA-256, or the difference is stated.
- **A command** that regenerates every summary from the raw files.
- **Tagged claims**: each claim is MEASURED, OBSERVED, INFERRED or HYPOTHESIS (see the
  [README](README.md#how-results-are-reported)), with the device it came from.
- **No personal data**: no user names in file paths, serial numbers, device UDIDs, locations or
  account identifiers. CI rejects home-directory paths, but read your logs before committing.
- **No large or third-party files**: no model weights, datasets or copyrighted text. PoCs
  download these and record where from.

## Sign-off (DCO)

Every commit must end with a line like

```
Signed-off-by: Your Name <you@example.com>
```

`git commit -s` adds it. It certifies the
[Developer Certificate of Origin 1.1](https://developercertificate.org): you wrote the
contribution, or otherwise have the right to submit it under this repository's licenses. A CI check
enforces it on pull requests. To fix a missing sign-off, run `git commit --amend -s` for the last
commit, or `git rebase --signoff main` for all of them, then force-push your branch.

## Licensing and credit

You keep the copyright to your contribution. Code is licensed under Apache-2.0; write-ups and
result data under CC BY 4.0 (see [README](README.md#license)). Signing off means you agree to
license your contribution that way.

Replication authors are named in their replication's README and in the PoC's *Replications*
table. Reviewers are named on the work they review. The git history is the full record.

## AI assistance

Using AI tools is fine. Say what you used and for what in your replication README. You are
responsible for every number and sentence you submit. Results must come from actually running the
tools; generated or estimated numbers are never accepted as results.

## Review

A reviewer checks the evidence standard, regenerates the summaries from your raw files, and
compares your conditions and deviations with the PoC's method. They may ask questions or ask for
missing files. Review is best effort, because the lab is small. Accepting a replication means it
meets the evidence standard. It doesn't mean the lab endorses conclusions beyond what the data
shows. How disagreements and corrections are handled is in [GOVERNANCE.md](GOVERNANCE.md).

## Writing style

Keep it plain and specific. Give numbers with their units and device. In write-ups, use the lab,
the experiment or the run as the subject ("the run measured 13 MiB"), not "I" or "we"; the byline
says who did the work. State limits.

## Conduct

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
