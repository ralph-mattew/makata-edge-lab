# Governance

How the lab decides what gets published, and how it corrects mistakes.

## Roles

- **Editor**: Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)).
  Maintains the repository, registers PoC protocols, merges contributions, and applies this
  document.
- **Reviewers**: people invited to review contributions, listed below. Nobody reviews their own
  work or work they have a conflict of interest with.
- **Contributors**: anyone with a merged contribution.

| Reviewer | Areas | Since |
|---|---|---|
| (founding reviewers being invited) | | |

## How a result gets published

**PoCs.** The question, method and decision rule are committed before the first run. That commit
is the registration. Results come in a later commit and are judged against the registered decision
rule. Later changes to the method are listed, with dates, in the PoC's *Deviations* section. PoCs
are currently written by the lab. Each names its authors and reviewers at the top.

**Replications.** Reviewed against the evidence standard in [CONTRIBUTING.md](CONTRIBUTING.md).
Each needs approval from someone other than its author. Until the lab has reviewers, the editor
reviews. After that, a replication by the editor needs a reviewer's approval.

**When a replication disagrees.** A replication never changes a PoC's verdict by itself. The PoC
gets a dated note linking to the replication. The editor then decides, with reasons, whether the
original result stands, the verdict becomes *inconclusive*, or the PoC needs a new run.

## Corrections

- **Editorial changes** (typos, wording, voice, links) are made directly. The git history records
  them.
- **Substantive changes** (a number, a claim, a conclusion or a verdict) are never made silently.
  The document gets a dated entry in an *Errata* section saying what changed and why, and the
  original text stays visible.
- **Retraction.** If a result can't be supported (for example, a wrong model file or a broken
  measurement), the PoC is marked *retracted* at the top with the reason. Its files stay in the
  repository.
- Anyone can report a suspected error with the "Possible error in a result" issue form.

## Conflicts of interest

Write-ups disclose funding, employment or affiliations related to what they measure, for example
maintaining the tool under test. The lab currently has no funding. Many PoCs measure settings taken
from the editor's own apps (Xylo and Unawain); each PoC says so where it applies.

## AI assistance

The lab uses AI tools to help write code and documents. Results always come from actually running
the tools, and a person checks them before they are published. Contributors disclose AI use as
described in [CONTRIBUTING.md](CONTRIBUTING.md).

## Changing this document

Changes are made by pull request and listed in the [CHANGELOG](CHANGELOG.md). Once the lab has
reviewers, a change stays open for at least seven days so they can comment.
