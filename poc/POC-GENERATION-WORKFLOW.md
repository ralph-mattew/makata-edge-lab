# PoC Generation & Publication Workflow

**Purpose**: Standardized end-to-end process for creating, executing, and publishing PoC experiments in the Makata Edge AI Lab.

**Last updated**: 2026-10-19

---

## Complete Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PoC LIFECYCLE (Full Process)                     │
└─────────────────────────────────────────────────────────────────────┘

Phase 1: IDEATION & FILTERING (1-3 hours)
  ├─ Research gathering
  ├─ Add to POC-IDEAS.md (🟢 Feasible)
  ├─ Quality Gate Review (3 gates)
  └─ Decision: ✅ Approved / 🟡 Needs Work / ❌ Rejected

Phase 2: REGISTRATION (30-60 min)
  ├─ Create XXX-title-DRAFT.md
  ├─ Pre-register: Question, Hypotheses, Method, Decision Rule
  └─ Review & finalize registration

Phase 3: EXECUTION (hours to weeks)
  ├─ Implement & run experiment
  ├─ Collect measurements
  └─ Apply decision rule

Phase 4: WRITE-UP (1-2 hours)
  ├─ Complete README.md with results
  ├─ Add verdict, analysis, recommendations
  └─ Commit to lab repo

Phase 5: PUBLICATION (30-60 min)
  ├─ Publish to makata-edge-lab repo (GitHub)
  └─ Publish summary to makata-ai website (public)

Phase 6: FOLLOW-UP
  ├─ Update POC-IDEAS.md (mark ⚫ Completed)
  ├─ Extract lessons learned
  └─ Plan next experiments
```

---

## Phase 1: Ideation & Filtering

### Step 1.1: Research Gathering

**Activities**:
- Read recent papers, blog posts, industry reports
- Identify potential optimization techniques
- Document ideas with references

**Output**: Notes on potential PoC ideas

---

### Step 1.2: Add to Idea Bank

**File**: `poc/POC-IDEAS.md`

**Format**:
```markdown
### PoC-X#: [Title]
**Status**: 🟢 Feasible (not vetted)
**Estimated effort**: [X days/weeks]

**Question**: [Clear research question]

**Why it matters**: [Context and motivation]

**Hypotheses**:
- H1: [Testable prediction]
- H2: [Testable prediction]

**Setup**: [Brief experimental design]

**Decision rule**: [How to interpret results]

**Prerequisites**: [Dependencies or requirements]

**References**: [Papers, blogs, etc.]
```

**Action**: Commit to idea bank with status 🟢 Feasible

---

### Step 1.3: Quality Gate Review

**File**: Create `poc/quality-gate-reviews/[poc-title]-review.md`

**Use template from**: `poc/POC-QUALITY-GATE.md`

**Three Gates**:

#### Gate 1: Problem Validation (30-60 min)
- [ ] Root cause identified with data
- [ ] Baseline failures analyzed (20+ samples)
- [ ] Proposed solution targets identified root cause
- [ ] Problem magnitude quantified
- [ ] Problem exists on iPhone/edge devices

**Deliverable**: Problem validation report

---

#### Gate 2: Solution Understanding (30-60 min)
- [ ] Original paper/blog read and understood
- [ ] Core mechanism explained (not just "it works")
- [ ] Implementation details identified
- [ ] Replication feasible with available tools
- [ ] Theoretical prediction documented
- [ ] If expecting negative, justified why worth testing

**Deliverable**: Method analysis + theoretical prediction

---

#### Gate 3: Feasibility & ROI (30 min)
- [ ] Runs on iPhone (not GPU server only)
- [ ] Memory/latency constraints acceptable
- [ ] Time estimate documented
- [ ] Expected value calculation shows positive ROI
- [ ] Fail-fast design with early exit criteria
- [ ] No clearly superior alternative exists
- [ ] Novel contribution (not just replication)

**Deliverable**: ROI analysis + fail-fast plan

---

### Step 1.4: Gate Decision

**If all 3 gates PASS**:
- Update POC-IDEAS.md: 🟢 → ✅ Approved
- Proceed to Phase 2 (Registration)

**If 1-2 gates FAIL**:
- Update POC-IDEAS.md: 🟢 → 🟡 Needs Work
- Document missing validation/research
- Complete validation work, then re-review

**If all 3 gates FAIL or fundamentally flawed**:
- Update POC-IDEAS.md: 🟢 → ❌ Rejected
- Document rejection reason
- Archive (do not pursue)

---

## Phase 2: Registration

### Step 2.1: Create Draft Registration

**File**: `poc/XXX-title-DRAFT.md`

**Naming convention**:
- `XXX` = 3-digit number (010, 011, 012, etc.)
- `title` = kebab-case short title
- `-DRAFT` suffix until first run

**Template** (see existing PoCs 010-012):

```markdown
# PoC XXX: [Full Title]

| | |
|---|---|
| Status | Planned (registration draft) |
| Verdict | TBD |
| Authors | [Name] ([@github-handle](https://github.com/...)) |
| Reviewers | None yet |
| Source idea | [Reference] |
| Registered | [Date] (this draft, before the first run) |

## Question

[One-sentence research question]

## Why it matters here

[Context: What problem does this solve?]
[Evidence: What baseline/data supports this?]
[Impact: Why is this important for edge AI?]

## Hypotheses

All HYPOTHESIS until measured. A point is a percentage point of items.

1. **H1** (Primary). [Prediction with threshold]
2. **H2** (Secondary). [Prediction]
3. **H3** (Tertiary). [Prediction]

[Descriptive measurements...]

## Method

**Host.** [Hardware specs, same format as PoC 007-009]

**Model.** [If applicable: model, file, SHA-256, license]

**Tooling.** [Software versions]

**Items.** [Dataset description, count, source]

**Conditions.** [Experimental arms/variants]

**Measurements.**

1. [Primary metric - definition]
2. [Secondary metrics]

**Intervals.** [Confidence intervals methodology]

## Decision rule

Written before the first run. The idea under test: [clear statement]

**Step 1 (Primary check).** If [H1 condition]:
- **adopt/reject/inconclusive**: [interpretation]
- [Next steps]

**Step 2 (Secondary check).** If Step 1 passes, check [H2]:
- If H2 holds: [outcome]
- If H2 fails: [outcome]

[Continue for all hypotheses...]

## Limits

**Not measured here**:
- [What this PoC doesn't cover]
- [Scope limitations]

**Deviations from production**:
- [Any simplifications or differences]

## Reproduction

```bash
# Commands to reproduce results
cd poc/XXX-title
./run.sh
```

[Prerequisites, environment setup]

## Results

[Leave blank - fill in Phase 4]

## Verdict

[Leave blank - fill in Phase 4]
```

---

### Step 2.2: Review Registration

**Checklist**:
- [ ] Question is clear and testable
- [ ] Hypotheses are pre-registered (before seeing results)
- [ ] Method is reproducible (exact commands, versions, seeds)
- [ ] Decision rule is unambiguous
- [ ] All three gates passed and documented

**Reviewers**: Internal review (self + lab members if available)

---

### Step 2.3: Finalize Registration

**Actions**:
1. Commit draft registration to git
2. Create PoC directory: `poc/XXX-title/`
3. Add draft to directory: `poc/XXX-title/XXX-title-DRAFT.md`

**Do NOT rename from DRAFT yet** - wait until first run complete

---

## Phase 3: Execution

### Step 3.1: Implement Experiment

**Directory structure**:
```
poc/XXX-title/
├── README.md (or XXX-title-DRAFT.md)
├── scripts/              (if needed)
│   ├── prepare.py
│   ├── run.py
│   └── analyze.py
├── harness/              (if Swift/custom code)
│   └── Sources/
├── data/                 (gitignored)
├── results/
│   ├── raw/              (measurement outputs)
│   └── summary.md        (analysis)
├── run.sh                (master execution script)
└── .gitignore
```

**Key principles**:
- Reproducible (exact seeds, versions)
- Automated (run.sh does everything)
- Documented (clear README instructions)

---

### Step 3.2: Run Experiment

**Best practices**:
- Run on AC power (for consistency)
- Document environment (OS version, hardware)
- Capture all output (logs, timing, errors)
- Use fail-fast design (stop early if clear verdict)

**Timing**:
- Quick tests (PoC 010): 5-30 minutes
- Full runs (PoC 007): 30-90 minutes
- Complex experiments: hours to days

---

### Step 3.3: Apply Decision Rule

**Important**: Follow the pre-registered decision rule exactly
- Don't change thresholds after seeing results
- If rule is ambiguous, document and revise for next time
- Apply step-by-step as registered

**Verdict categories**:
- **Adopt** (full or conditional): Method works, recommend for production
- **Reject** (with reason): Method doesn't work or has critical flaw
- **Inconclusive**: Results unclear, need more investigation

---

## Phase 4: Write-Up

### Step 4.1: Complete README

**File**: Rename `XXX-title-DRAFT.md` → `README.md`

**Add Results section**:
```markdown
## Results

Run [date] on [hardware], from commit `[hash]`.

**Primary findings**:
- H1 (Primary): [Result with data]
- H2 (Secondary): [Result]
- H3 (Tertiary): [Result]

**Measurements table**:

| Metric | Baseline | This PoC | Difference |
|--------|----------|----------|------------|
| [Primary] | X% | Y% | +Z points |
| [Secondary] | A | B | Δ |

**Per-category breakdown** (if applicable):
[Table or list]

**Key observations**:
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

**Raw files**: [Link to results/raw/]
```

---

### Step 4.2: Add Verdict

**Format**:
```markdown
## Verdict

**Decision**: [ADOPT / REJECT / INCONCLUSIVE]

**Reasoning**:
- H1: [PASS/FAIL] - [explanation]
- H2: [PASS/FAIL] - [explanation]
- Decision rule step X: [outcome]

**Recommendation**:
[What should happen next? Deploy? Investigate further? Try alternative?]

**Lessons learned**:
1. [Insight 1]
2. [Insight 2]

**Impact**:
- If adopted: [Expected production benefit]
- If rejected: [What we learned, time saved by knowing]
```

---

### Step 4.3: Update Metadata

**Top of README**:
```markdown
| | |
|---|---|
| Status | Written up ([stage]) |
| Verdict | [Adopt/Reject/Inconclusive] - [one-line summary] |
| Authors | [Name] |
| Reviewers | [Names if applicable] |
| Source idea | [Reference] |
| Registered | [Date] |
| Run | [Date] |
```

**Stages**:
- `host stage` - Tested on Mac only
- `iPhone stage` - Validated on iPhone
- `production` - Deployed to users

---

### Step 4.4: Commit to Lab Repo

**Branch naming**: `poc/XXX-title-writeup`

**Commit message format**:
```
Lab: PoC XXX written up ([verdict])

[One-paragraph summary of what was tested and outcome]

Key findings:
- [Finding 1]
- [Finding 2]
- [Finding 3]

Verdict: [ADOPT/REJECT] - [reason]
Impact: [production benefit or lesson learned]

Signed-off-by: [Name] <[email]>
```

---

## Phase 5: Publication

### Step 5.1: Publish to makata-edge-lab (GitHub)

**Repository**: https://github.com/ralph-mattew/makata-edge-lab

**Steps**:
1. Create branch: `poc/XXX-title-writeup`
2. Commit all PoC files (README, scripts, results)
3. Push branch
4. Create pull request
5. Review (self or team)
6. Merge to main

**PR Template**:
```markdown
# PoC XXX: [Title] - [VERDICT]

## Summary
[2-3 sentence description]

## Key Results
- H1: [Result]
- H2: [Result]
- Verdict: [ADOPT/REJECT/INCONCLUSIVE]

## Impact
[What this means for production / what we learned]

## Files Changed
- poc/XXX-title/README.md (main write-up)
- poc/XXX-title/scripts/ (implementation)
- poc/XXX-title/results/ (measurements)
- poc/POC-IDEAS.md (mark completed)

## Checklist
- [ ] All hypotheses addressed
- [ ] Decision rule applied
- [ ] Results reproducible (run.sh works)
- [ ] README complete
- [ ] POC-IDEAS.md updated
```

---

### Step 5.2: Publish to makata-ai Website

**Repository**: https://github.com/makata-ai/makata-ai (public website)

**Directory**: `content/lab/experiments/`

**File**: `XXX-title.md`

**Format** (Hugo front matter + Markdown):

```markdown
---
title: "PoC XXX: [Title]"
date: 2026-XX-XX
type: "experiment"
verdict: "adopt" # or "reject" or "inconclusive"
stage: "host" # or "iphone" or "production"
tags:
  - retrieval
  - embeddings
  - mobile-ai
  - edge-ai
summary: "[One-sentence summary of what was tested]"
outcome: "[One-sentence outcome]"
impact: "[Production impact if adopt, or lesson learned if reject]"
---

## Overview

**Question**: [Research question]

**Verdict**: **[ADOPT/REJECT/INCONCLUSIVE]** - [one-line reason]

**Impact**: [What this means]

---

## Background

[Why we tested this - 1-2 paragraphs]
[What problem it addresses]
[Link to related PoCs if applicable]

---

## What We Tested

**Hypothesis**: [Main hypothesis in plain language]

**Method**: [Brief description of experiment]
- Dataset: [CUAD, X items]
- Baseline: [What we compared against]
- Measurement: [Primary metric]

---

## Results

**Key Finding**: [Main result in bold]

| Metric | Baseline | This PoC | Change |
|--------|----------|----------|--------|
| [Primary] | X% | Y% | +Z |

**Verdict**: [ADOPT/REJECT] because [reason]

---

## What This Means

### For Production
[If ADOPT: deployment plan]
[If REJECT: what we validated/learned]

### Lessons Learned
1. [Insight 1]
2. [Insight 2]

---

## Technical Details

**Full write-up**: [Link to GitHub repo README]

**Reproduction**: Available in [lab repository](https://github.com/ralph-mattew/makata-edge-lab/tree/main/poc/XXX-title)

---

**Authors**: [Name]
**Date**: [YYYY-MM-DD]
**Lab**: [Makata Edge AI Lab](https://github.com/ralph-mattew/makata-edge-lab)
```

**Key differences from lab version**:
- Shorter, public-friendly language
- Less technical jargon
- Emphasis on impact/learnings
- Hugo metadata for website rendering

---

### Step 5.3: Cross-Link Publications

**In lab repo README**:
```markdown
**Public summary**: https://makata.ai/lab/experiments/XXX-title/
```

**In website post**:
```markdown
**Full technical write-up**: https://github.com/ralph-mattew/makata-edge-lab/tree/main/poc/XXX-title
```

---

## Phase 6: Follow-Up

### Step 6.1: Update Idea Bank

**File**: `poc/POC-IDEAS.md`

**Update status**:
```markdown
### PoC-X#: [Title]
**Status**: ⚫ **Completed** (PoC XXX - [verdict])
**Completed**: [Date]
**Verdict**: [ADOPT/REJECT/INCONCLUSIVE]

**Results**: [One-line summary]
**Impact**: [What we learned/deployed]

**Links**:
- Lab write-up: [poc/XXX-title/](XXX-title/)
- Public summary: https://makata.ai/lab/experiments/XXX-title/

[Keep original description for reference...]
```

---

### Step 6.2: Extract Lessons

**If ADOPT**:
- Plan deployment (next PoC to validate on iPhone?)
- Update production roadmap
- Measure impact after deployment

**If REJECT**:
- Document what we learned (update POC-IDEAS.md)
- Identify alternative approaches
- Share findings (blog post, paper?)

**If INCONCLUSIVE**:
- Plan follow-up experiment
- Refine hypotheses based on results
- Re-register as new PoC

---

### Step 6.3: Plan Next Experiments

**Use results to inform**:
- What to test next (build on success, try alternatives)
- What NOT to test (avoid similar dead-ends)
- Update quality gate criteria (improve filtering)

**Priority queue**:
1. Update POC-IDEAS.md with new priorities
2. Run quality gate on next candidates
3. Repeat cycle

---

## Quality Metrics to Track

**Lab KPIs**:
- Hit rate: % of PoCs that achieve expected outcome (target: 80%+)
- Time to verdict: Days from registration to decision (target: <2 weeks)
- Publication rate: % of PoCs published to website (target: 100%)
- Replication success: % of PoCs reproducible by others (target: 100%)

**Quality gate effectiveness**:
- % of PoCs passing all gates (target: ~10-20% selectivity)
- Time saved by early rejection (hours)
- Post-hoc gate failure rate (PoCs that should have been rejected)

---

## Templates & Checklists

### PoC Registration Checklist

- [ ] Quality gate review completed (all 3 gates)
- [ ] Research question is clear and testable
- [ ] Hypotheses are pre-registered (not data-driven)
- [ ] Method is fully specified (reproducible)
- [ ] Decision rule is unambiguous
- [ ] Baseline is established
- [ ] Expected outcome documented
- [ ] Fail-fast design included
- [ ] Draft committed to lab repo

---

### PoC Execution Checklist

- [ ] Environment documented (hardware, OS, versions)
- [ ] Scripts are automated (run.sh works)
- [ ] Seeds/randomness controlled
- [ ] All measurements collected
- [ ] Decision rule applied as pre-registered
- [ ] Raw results committed to results/raw/
- [ ] Logs and timing captured

---

### PoC Publication Checklist

- [ ] README complete with results
- [ ] Verdict clearly stated
- [ ] Recommendations documented
- [ ] Lessons learned extracted
- [ ] Reproduction instructions verified
- [ ] Lab repo PR created and merged
- [ ] Website post published
- [ ] POC-IDEAS.md updated (marked ⚫ Completed)
- [ ] Cross-links added (lab ↔ website)

---

## Example Timeline

**PoC 010 (BM25-Only Retrieval)** - Actual timeline:

| Phase | Time | Total |
|-------|------|-------|
| Quality gate review | (Retroactive) | 0 min |
| Registration (was pre-drafted) | 10 min | 10 min |
| Implementation (reuse PoC 007) | 15 min | 25 min |
| Execution | 5 min | 30 min |
| Analysis | 10 min | 40 min |
| Write-up | [In progress] | TBD |
| Lab publication | TBD | TBD |
| Website publication | TBD | TBD |

**Expected total**: ~2-3 hours from start to public publication

---

## Common Pitfalls to Avoid

### During Ideation
- ❌ Skipping quality gate (leads to wasted effort)
- ❌ Not validating problem exists (solving imaginary problems)
- ❌ Assuming method without reading implementation

### During Registration
- ❌ Vague hypotheses (not testable)
- ❌ Ambiguous decision rules (leads to post-hoc interpretation)
- ❌ Missing baseline (can't measure improvement)

### During Execution
- ❌ Changing decision rule after seeing results (p-hacking)
- ❌ Ignoring negative results (publication bias)
- ❌ Over-interpreting small differences

### During Publication
- ❌ Hiding negative results (reduces lab credibility)
- ❌ Missing reproduction instructions (not reproducible)
- ❌ Overstating impact (hype vs reality)

---

## Summary

**The Complete PoC Lifecycle**:

1. **Ideation**: Gather research → Add to idea bank
2. **Filtering**: Quality gate (3 gates) → Approve/Reject
3. **Registration**: Pre-register question, method, decision rule
4. **Execution**: Implement, run, measure, apply rule
5. **Write-up**: Complete README with results and verdict
6. **Publication**: Lab repo (technical) + Website (public summary)
7. **Follow-up**: Update idea bank, extract lessons, plan next

**Time investment per PoC**: ~2-5 hours (quick) to 1-2 weeks (complex)

**Key principle**: **Pre-registration prevents p-hacking, quality gates prevent wasted effort**

---

*Last updated: 2026-10-19*
*Next review: After first 3 PoCs using this workflow*
