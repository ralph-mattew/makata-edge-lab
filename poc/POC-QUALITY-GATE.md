# PoC Quality Gate Process

**Purpose**: Ensure Makata Edge Lab only pursues high-quality, well-justified experiments that advance mobile/edge AI research.

**Goal**: Filter out elementary, flawed, or low-ROI experiments before investing significant time.

---

## Pipeline Overview

```
Research → Idea Bank → Quality Gate → PoC Registration → Execution
   ↓           ↓            ↓              ↓                ↓
 Gather    Catalog     Filter/Vet     Pre-register      Run
```

**Current state**: We have Research → Idea Bank (POC-IDEAS.md)
**Gap**: No quality filter between ideas and registration
**Solution**: Add mandatory 3-gate review process

---

## The 3-Gate Review Process

Before any PoC can be registered, it must pass **all three gates** in order:

### Gate 1: Problem Validation (30-60 min)
### Gate 2: Solution Understanding (30-60 min)
### Gate 3: Feasibility & ROI (30 min)

**Total time investment**: 90-180 minutes (1.5-3 hours)
**Time saved**: Avoiding 1-2 week dead-ends on flawed experiments

---

## Gate 1: Problem Validation

**Question**: *Is there actually a problem worth solving?*

### Required Artifacts

1. **Root cause analysis** (not just symptoms)
   - What specific failure mode are we addressing?
   - Evidence from data (not assumptions)
   - Quantified impact (e.g., "38.6% of queries fail because...")

2. **Baseline measurement**
   - Current performance metrics
   - Where exactly does the baseline fail?
   - Sample analysis: 20-50 failure cases categorized

3. **Problem-solution fit**
   - Does the proposed solution address the root cause?
   - Or are we solving a different problem?

### Example (PoC 011 - What We Missed)

❌ **What we assumed**:
- Small chunks (median 25 words) are bad
- Adding context will improve retrieval

✅ **What we should have validated**:
```
1. Analyze PoC 007's 38.6% failures (512 failed items)
2. Sample 50 random failures, categorize:
   - Ambiguous chunks (e.g., "30 days" with no context): X%
   - Semantic mismatch (embedding quality issue): Y%
   - Missing answer (chunking cut the answer): Z%
   - BM25 vs embedding weakness: W%
3. Check if "small chunks" is actually the problem
4. Decision: Only proceed if >50% failures are due to ambiguous chunks
```

**If this category is <30% of failures → proposed solution is off-target**

### Gate 1 Checklist

- [ ] Root cause identified with data (not hypothesis)
- [ ] Baseline failures analyzed (20+ samples categorized)
- [ ] Proposed solution targets the identified root cause
- [ ] Quantified problem magnitude (% of queries affected)
- [ ] Problem exists on **iPhone/edge**, not just desktop

**Verdict**: ⬜ PASS → Proceed to Gate 2  |  ⬜ FAIL → Back to idea bank

---

## Gate 2: Solution Understanding

**Question**: *Do we understand HOW the proposed method actually works?*

### Required Artifacts

1. **Method deep-dive** (not just results)
   - Read the original paper/blog post
   - Understand the core mechanism
   - Identify key implementation details

2. **Implementation checklist**
   - What components are needed?
   - Any model fine-tuning required?
   - Special data preprocessing?
   - Architecture changes?

3. **Approach validation**
   - Can we replicate the method as described?
   - Or are we implementing a "simplified" version that might not work?

### Example (PoC 011 - What We Missed)

❌ **What we assumed**:
- Anthropic's contextual embeddings = prepending document title
- Standard embedding model will handle it

✅ **What we should have checked**:
```
Research Questions:
1. How did Anthropic implement contextual embeddings?
   - Did they fine-tune the model?
   - Did they use special tokens (<doc>, <chunk>)?
   - Did they retrain from scratch?
   - Or just prepend text?

2. Check their GitHub/paper for implementation details
3. Search for replications: "contextual embeddings implementation"
4. Understand the mechanism: WHY does it work?

Expected Finding:
- Anthropic likely FINE-TUNED their embedding model
- Model learned to weight chunk content > metadata
- Our approach (naive prepending) won't work with standard model
```

**If we can't replicate their method → FAIL Gate 2**

### Theoretical Prediction

Before implementing, **predict the outcome** with reasoning:

```markdown
## Hypothesis Prediction

**Approach**: Prepend "Document: {title}. Chunk: {text}" to all chunks

**Expected outcome**: NEGATIVE ❌

**Reasoning**:
1. Embedding = average of token embeddings
2. Adding 10 words of metadata dilutes signal by ~30%
3. Question embeddings don't contain document titles
4. This creates a mismatch → lower similarity scores

**Counter-argument**:
- Context might help semantic matching for ambiguous chunks
- Worth testing, but expect <20% improvement best-case

**Decision**:
- Run minimal test (10 items) as sanity check
- If negative (as predicted) → quick rejection
- If positive (surprised) → expand to full test
```

### Gate 2 Checklist

- [ ] Original paper/blog post read and understood
- [ ] Core mechanism explained (not just "it works")
- [ ] Implementation details identified (fine-tuning? special tokens?)
- [ ] Replication feasible with available tools (no GPU cluster needed)
- [ ] Theoretical prediction documented (expected outcome + reasoning)
- [ ] If expecting negative result, justification for why still worth testing

**Verdict**: ⬜ PASS → Proceed to Gate 3  |  ⬜ FAIL → Back to idea bank

---

## Gate 3: Feasibility & ROI

**Question**: *Is this experiment worth the lab's time?*

### Required Artifacts

1. **Edge AI fit**
   - Runs on iPhone/mobile device?
   - Memory footprint acceptable (<4 GB RAM)?
   - Latency acceptable (<500ms for retrieval)?
   - Model size acceptable (<2 GB)?

2. **Effort estimate**
   - Time to implement: X hours/days
   - Time to run: X minutes/hours
   - Time to analyze: X hours
   - Total time investment: X

3. **Impact estimate**
   - Best-case improvement: +X points recall / -X% latency / -X MB memory
   - Worst-case outcome: No improvement (time lost)
   - Alternative approaches available?

4. **Fail-fast design**
   - Can we test on 10-50 items first?
   - Early exit criteria (if X happens, stop)
   - Incremental milestones (phase 1 → phase 2 → phase 3)

### ROI Calculation

```
Expected Value (EV) = P(success) × Impact - P(failure) × Time_wasted

Example (PoC 011):
- P(success) = 20% (theoretical prediction suggests negative)
- Impact if success = +5 points recall (moderate)
- P(failure) = 80%
- Time if full implementation = 1-2 weeks (wasted)

EV = 0.2 × 5 - 0.8 × 80 hours = 1 - 64 = -63 (NEGATIVE)

Decision: Only proceed if we can test in <3 hours (spot-check)
```

### Comparison with Alternatives

**Always ask**: Are there better approaches to the same problem?

Example:
- PoC 011 (contextual embeddings): Complex, requires fine-tuning, uncertain
- PoC 012 (cross-encoder reranking): **Industry standard**, proven, easier to implement
- Decision: Do PoC 012 first, then reconsider PoC 011

### Gate 3 Checklist

- [ ] Runs on iPhone (not GPU server only)
- [ ] Memory/latency constraints acceptable
- [ ] Time estimate documented (implementation + execution + analysis)
- [ ] Expected value (EV) calculation shows positive ROI
- [ ] Fail-fast design with early exit criteria
- [ ] No clearly superior alternative exists
- [ ] Novel contribution (not just replicating existing work)

**Verdict**: ⬜ PASS → Approve for registration  |  ⬜ FAIL → Back to idea bank

---

## Gate Review Template

Use this template for each PoC candidate:

```markdown
# PoC Quality Gate Review: [PoC Title]

**Reviewer**: [Name]
**Date**: [YYYY-MM-DD]
**Idea source**: [Paper/Blog/Idea Bank #]

---

## Gate 1: Problem Validation

### Root Cause Analysis
[Describe the specific failure mode]

**Evidence**:
- Baseline performance: X% recall / Y ms latency
- Failure analysis: Reviewed N samples
- Categories:
  - Category A: X% of failures
  - Category B: Y% of failures
  - Category C: Z% of failures

**Problem-Solution Fit**:
[Does this PoC address the dominant failure mode?]

### Gate 1 Verdict
⬜ PASS - Root cause identified, solution targets it
⬜ FAIL - Problem not validated / solution mismatch

---

## Gate 2: Solution Understanding

### Method Deep-Dive
**Original source**: [Paper/Blog URL]

**Core mechanism**:
[Explain HOW it works, not just that it works]

**Implementation requirements**:
- [ ] Model fine-tuning needed? [Yes/No - details]
- [ ] Special preprocessing? [Yes/No - details]
- [ ] Architecture changes? [Yes/No - details]
- [ ] New dependencies? [List]

### Theoretical Prediction
**Expected outcome**: [POSITIVE/NEGATIVE/NEUTRAL]

**Reasoning**:
[Why will this work or fail? Show the math/logic]

**If negative expected**: Why still worth testing?
[Justification]

### Gate 2 Verdict
⬜ PASS - Method understood, replicable, prediction documented
⬜ FAIL - Critical details missing / unreplicable approach

---

## Gate 3: Feasibility & ROI

### Edge AI Constraints
- Memory footprint: X GB (limit: 4 GB)
- Latency estimate: X ms (limit: 500 ms for retrieval)
- Model size: X MB (limit: 2 GB)
- iPhone compatibility: [Yes/No]

### Effort Estimate
- Implementation: X hours
- Execution: X minutes/hours
- Analysis: X hours
- **Total**: X hours/days

### Impact Estimate
- Best case: +X points recall / -X% latency / -X MB
- Expected case: [Realistic estimate]
- Worst case: No improvement (time lost)

### ROI Calculation
```
EV = P(success) × Impact - P(failure) × Time
EV = [calculation]
```

**Decision**: [Proceed / Defer / Reject]

### Fail-Fast Design
- [ ] Phase 1 (minimal test): Test on N items, X hours
- [ ] Exit criteria: If [condition], stop
- [ ] Phase 2 (if Phase 1 passes): [Description]

### Alternatives Considered
1. [Alternative 1]: [Why better/worse?]
2. [Alternative 2]: [Why better/worse?]

**Best choice**: [This PoC / Alternative X]

### Gate 3 Verdict
⬜ PASS - Feasible, positive ROI, best approach
⬜ FAIL - Not feasible / negative ROI / better alternative exists

---

## Final Decision

**Overall Verdict**: ⬜ APPROVED FOR REGISTRATION  |  ⬜ REJECTED

**If APPROVED**:
- [ ] Create PoC registration in poc/XXX-title-DRAFT.md
- [ ] Add to experiment pipeline
- [ ] Schedule execution

**If REJECTED**:
- [ ] Update POC-IDEAS.md with rejection reason
- [ ] Mark as ⏸️ (paused) or ❌ (rejected)
- [ ] Document lessons learned (if any)

**Signatures**:
- Reviewer: [Name]
- Approver: [Name] (if different)
```

---

## Integration with Existing Workflow

### Updated Pipeline

```
1. Research Gathering (ongoing)
   ↓
2. Idea Bank Update (POC-IDEAS.md)
   - Add new ideas as 🟢 (feasible, not vetted)
   ↓
3. Quality Gate Review (use template above)
   - Gate 1: Problem Validation
   - Gate 2: Solution Understanding
   - Gate 3: Feasibility & ROI
   ↓
4a. APPROVED → PoC Registration (XXX-title-DRAFT.md)
    ↓
    Execution → Write-up → Publish

4b. REJECTED → Update Idea Bank
    - Mark as ⏸️ (needs more research) or ❌ (fundamentally flawed)
    - Document reason
```

### Idea Bank Status Flags

Update POC-IDEAS.md to use these statuses:

- 🟢 **Feasible** (not vetted) - Initial entry, needs quality gate review
- ✅ **Approved** (passed quality gate) - Ready for registration
- 🟡 **Under Review** (in quality gate) - Currently being vetted
- ⏸️ **Paused** (needs more research) - Failed gate 2 (need better understanding)
- ❌ **Rejected** (fundamentally flawed) - Failed gate 1 or 3
- 🟠 **Low Priority** (feasible but low ROI) - Passed gates but deferred
- ⚫ **Completed** (experiment done) - Results published

---

## PoC 011 Retrospective (Example)

### What Happened
- Idea: Anthropic-style contextual embeddings
- Status: Bypassed quality gate, went straight to registration
- Outcome: 80% negative results, 3 hours invested (spot-check only)

### Gate Review (Retrospective)

**Gate 1: Problem Validation** - ❌ FAIL
- Did not analyze PoC 007's failures to identify root cause
- Assumed small chunks = problem (not validated)
- Should have sampled 50 failures and categorized them first

**Gate 2: Solution Understanding** - ❌ FAIL
- Did not read Anthropic's implementation details
- Assumed naive text prepending would work
- Missed that they likely fine-tuned the model
- Theoretical prediction would have shown negative expected outcome

**Gate 3: Feasibility & ROI** - ⚠️ MARGINAL PASS
- Fail-fast design saved us (spot-check instead of full implementation)
- ROI calculation would have shown negative EV
- PoC 012 (cross-encoder) is a better alternative

### Lessons Learned
1. Always validate the problem before proposing solutions
2. Understand HOW a method works, not just that it works
3. Predict outcomes theoretically before implementing
4. Check for simpler/better alternatives

### Action Taken
- Implemented quality gate process (this document)
- PoC 011 documented as internal rejection
- Future PoCs must pass all 3 gates

---

## Quality Metrics (Track Over Time)

**Goal**: Improve lab's hit rate on PoCs

Track these metrics:

| Metric | Target | Current |
|--------|--------|---------|
| PoCs passing all 3 gates | 80%+ | TBD |
| Approved PoCs that succeed (adopt/partial) | 60%+ | TBD |
| Time saved by early rejection | 50+ hours/year | TBD |
| Average time to verdict (registration → decision) | <2 weeks | TBD |

---

## Examples: Applying the Quality Gate

### Example 1: PoC 010 (BM25-Only Retrieval)

**Gate 1: Problem Validation** - ✅ PASS
- Problem: PoC 007 uses 600 MB embedding model
- Question: Is semantic embedding necessary for keyword-rich CUAD?
- Validation: CUAD has high keyword density ("Delaware law", "30 days")

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Pure BM25 (keyword search), no embeddings
- Well-understood, simple to implement
- Prediction: Likely to fail (semantic needed) but worth validating

**Gate 3: Feasibility & ROI** - ✅ PASS
- Implementation: Reuse PoC 007 harness, disable embeddings (~30 min)
- Execution: ~30 minutes
- Impact if success: Eliminate 600 MB model dependency (huge win)
- ROI: High payoff, low effort

**Verdict**: ✅ APPROVED

---

### Example 2: PoC 012 (Cross-Encoder Reranking)

**Gate 1: Problem Validation** - ✅ PASS
- Problem: Hybrid retrieval gets 61.4% recall, room for improvement
- Industry best practice: Rerank top-K with cross-encoder
- Validated in literature (common RAG pattern)

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Retrieve top-K (K=10), rerank with cross-encoder to top-3
- Models: mxbai-rerank-base-v1 (184M), ms-marco-TinyBERT (4M)
- Prediction: +2-5 points recall improvement (based on literature)

**Gate 3: Feasibility & ROI** - ✅ PASS
- Memory: 184M or 4M model (acceptable)
- Latency: Rerank 10 chunks, <500ms target (testable)
- Effort: 1-2 weeks (integration with PoC 007)
- ROI: Industry standard approach, high confidence

**Verdict**: ✅ APPROVED

---

### Example 3: Hypothetical - "Use GPT-4 for Retrieval"

**Gate 1: Problem Validation** - ✅ PASS
- Problem: Retrieval recall at 61.4%
- Proposal: Use GPT-4 to re-rank or embed chunks

**Gate 2: Solution Understanding** - ✅ PASS
- Method: Call OpenAI API for embeddings or reranking
- Well-documented, proven approach

**Gate 3: Feasibility & ROI** - ❌ FAIL
- **iPhone compatibility**: NO (requires API call, network dependency)
- Latency: Network round-trip >>500ms
- Cost: API costs per query
- **Edge AI constraint violated**

**Verdict**: ❌ REJECTED (not edge AI)

---

## Appendix: Common Red Flags

Watch for these warning signs during gate review:

### Gate 1 Red Flags (Problem Validation)
- ⚠️ "We think small chunks are bad" → Assumption, not data
- ⚠️ No failure analysis of baseline
- ⚠️ Problem is rare (<5% of cases)
- ⚠️ Solution targets symptoms, not root cause

### Gate 2 Red Flags (Solution Understanding)
- ⚠️ "The paper says it works, so..." → Haven't read implementation details
- ⚠️ "We'll use a simplified version" → Might not work
- ⚠️ "Just prepend/append text" → Naive approach, likely to fail
- ⚠️ Can't explain WHY the method works
- ⚠️ Requires unavailable resources (GPU cluster, proprietary data)

### Gate 3 Red Flags (Feasibility & ROI)
- ⚠️ "We'll see if it works" → No theoretical prediction
- ⚠️ Requires >2 weeks with uncertain outcome
- ⚠️ Better alternatives exist (industry standards)
- ⚠️ Violates edge AI constraints (too big, too slow, requires internet)
- ⚠️ No fail-fast design (all-or-nothing approach)

---

## Summary

**The 3-Gate Quality Process ensures**:
1. We solve real problems (Gate 1)
2. We understand how solutions work (Gate 2)
3. We invest time wisely (Gate 3)

**Time investment**: 1.5-3 hours per PoC candidate
**Time saved**: Avoiding 10-80 hour dead-ends on flawed experiments

**Rule**: No PoC can be registered without passing all 3 gates.

---

*Last updated: 2026-10-19*
*Next review: After first 5 PoCs using this process*
