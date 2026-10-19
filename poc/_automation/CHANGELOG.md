# Automation Pipeline Changelog

## 2026-10-19 - Quality Gate Refinement

### Problem
Initial quality gate validation rejected all 36 extracted ideas (0% approval rate) because Gate 1 was too strict. It demanded root cause analysis for every idea, even those addressing **established constraints** like:
- Memory: 600MB EmbeddingGemma model
- Thermal: Neural Engine load
- Latency: Embedding generation overhead
- Quality: 61.4% recall baseline

This made the gate reject valid resource optimization ideas (e.g., "binary embeddings to save memory") as "solution-first without problem validation."

###Changes

**Gate 1: Problem Validation** (prompts/gate1-validation.txt)
- Added "ESTABLISHED CONSTRAINTS" section listing known mobile/edge limitations
- Changed criteria from "root cause analysis required" to "problem is real" (accepts established constraints)
- **New criterion**: "Addresses real tradeoff" - rejects pure optimization without cost consideration
  - Example REJECT: "Does max semantic weight improve recall?" (like PoC 013 - no tradeoff)
  - Example ACCEPT: "Does binary embedding save 60% memory with <10% recall loss?" (explicit tradeoff)
- Lowered threshold from ≥7.0 to ≥6.0

**Gate 2: Solution Understanding** (prompts/gate2-validation.txt)
- Lowered threshold from ≥7.0 to ≥6.0 (consistency with other gates)

**Error Handling** (4-validate-quality-gate.py)
- Fixed `UnboundLocalError` in exception handler (line 55)
- Now properly returns error details when JSON parsing fails

### Results

**Before refinement**:
- 36 ideas → 0 approved (0%)
- All rejected for "lacking root cause analysis"

**After refinement** (preliminary, 22/36 evaluated before crash):
- 5 ideas approved:
  1. Binary embeddings (sign-only compression)
  2. Sign-pattern matching for retrieval
  3. Two-stage retrieval (BM25 recall → semantic rerank)
  4. Source-grounded answer formatting
  5. Query-guided reranking

**Estimated final approval rate**: ~14-20% (5-7 ideas out of 36)

### Key Insight

The quality gate now correctly:
- **Accepts**: Ideas addressing known constraints with explicit quality/resource tradeoffs
- **Rejects**: Pure optimization without considering cost (like PoC 013's "max semantic weight")

This aligns with the lab's mission: mobile/edge AI requires balancing quality against memory, thermal, and latency constraints.

### Next Steps

1. Complete validation run on all 36 ideas
2. Run Stage 5 (prioritization) on approved ideas
3. Generate weekly summary (Stage 6)
4. Integrate approved ideas into POC-IDEAS.md queue
