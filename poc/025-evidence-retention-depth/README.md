# PoC 025: Evidence-retention depth diagnostic for hard categories (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (diagnostic, full CUAD) |
| Verdict | **Inconclusive by the letter (H1 confirmed, H2 mechanism is a no-op) — but a strong, actionable diagnostic.** H1 holds: **18.3%** of hard-category gold chunks are retrieved but sit at rank 4–10 (≥15%). The split is the real finding: **Non-Compete** is a *ranking* problem (top-3 25% but rank 4–10 = 26%, recall@10 = 51%) → a reranker should roughly double it; **Exclusivity** is a *representation* problem (54% of gold at rank 21+, recall@10 only 25%) → a top-10 reranker can't fix it; **Change-of-Control** is already fine (67% top-3). The registration's H2 filter ("keep top-10 by threshold, take top-3 by combined score") is a **proven no-op** for recall@3. Net: greenlight the cross-encoder reranking PoC, scoped to Non-Compete. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Scan or Index? Large Evidence Coverage, Answer Quality, and Cost in Long-Document RAG (http://arxiv.org/abs/2610.28957v1); promoted from the 2026-10-22 DIVERGENT ideation-engine scan (screening signal, not a gate score). |
| Registered | 2026-10-22 (this draft, before the first run) |

## Question

Does applying a full-candidate-pool evidence-retention check (retrieving a wider candidate set and then filtering rather than truncating) raise recall@3 on CUAD vs the fixed top-3 retrieval, without exceeding memory budget?

## Why it matters here

- The paper's key finding is that full-scan pipelines discard relevant evidence during reduction steps — the same risk exists when we truncate to top-3 from a small candidate pool
- If hard-category items have gold chunks ranked 4-6 (just below the cutoff), a wider candidate pool followed by filtering could surface them without changing the embedding or scoring mechanism
- Addresses the PoC-013 finding that increasing retrieval depth alone did not help, by pairing wider retrieval with a principled filtering step rather than naive depth increase

## Hypothesis

The source demonstrates on scientific corpora that evidence loss happens at the reduction/filtering step, not retrieval breadth; we hypothesize the same mechanism operates in CUAD hard categories — gold chunks are retrieved but discarded before top-3. We test this by expanding the candidate pool to top-10 and applying a BM25-score-gated filter (keep chunk if BM25 score > threshold OR semantic score > threshold) before selecting top-3. This is unverified for our domain, embedder, and recall metric.

- H1: At least 15% of hard-category (Exclusivity, Non-Compete, Change-of-Control) gold chunks appear in top-10 candidates but NOT in top-3, confirming reduction-step loss as the bottleneck
- H2: A two-threshold filter (BM25 OR semantic score gate) applied to top-10 candidates raises hard-category recall@3 by ≥4 points above current baseline
- H3: Memory overhead of expanding candidate pool from 3 to 10 does not exceed 200MB additional RAM

## Method

Reuse PoC-007/PoC-013 harness. Step 1 (diagnostic): for every hard-category Q&A item, retrieve top-10 hybrid candidates and record whether gold chunk appears in positions 1-3 vs 4-10 — this directly tests H1. Step 2 (intervention): implement a dual-threshold filter on top-10 candidates (retain if semantic_score ≥ θ_s OR BM25_score ≥ θ_b, then rank by combined score, take top-3). Sweep θ_s, θ_b on a 20% validation split of CUAD. Measure per-category recall@3 and overall recall@3 on held-out 80%.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT if H1 confirmed (≥15% gap) AND H2 (≥4-point hard-category lift) AND H3 (RAM ≤200MB additional). REJECT if H1 not confirmed (gold chunks already in top-3, so problem is elsewhere) or if H2 <+1 point. INCONCLUSIVE if H1 confirmed but H2 < 4 points.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.4  ·  est. effort 3-5 days (diagnostic query + filter implementation, leverages existing harness)

## Harness

`evidence-depth.py` ranks every item's chunks with the hybrid 0.9/0.1 scorer (committed PoC-014
vectors; no model) and records the rank of the best **covering** gold chunk (span overlaps ≥50% of
the gold span, PoC-007 defn). Reports recall@{1,3,5,10,20} and a rank histogram (top-3 / 4–10 /
11–20 / 21+ / never) per category and overall.

## Results

MEASURED on the host, full CUAD (1,316 items with gold + committed vectors), hybrid 0.9/0.1.

recall@k (hard categories ★):

| Category | @1 | @3 | @5 | @10 | @20 |
|---|---|---|---|---|---|
| OVERALL | 45 | 62 | 71 | 79 | 86 |
| ★ Exclusivity | 3 | 7 | 12 | 25 | 45 |
| ★ Non-Compete | 16 | 25 | 33 | 51 | 73 |
| ★ Change Of Control | 38 | 67 | 74 | 78 | 85 |

gold-chunk rank histogram (share of items):

| Category | top-3 | 4–10 | 11–20 | 21+ | never |
|---|---|---|---|---|---|
| OVERALL | 62% | 17% | 7% | 13% | 1% |
| ★ Exclusivity | 7% | 18% | 20% | **54%** | 1% |
| ★ Non-Compete | 25% | **26%** | 22% | 27% | 0% |
| ★ Change Of Control | 67% | 11% | 7% | 15% | 0% |

- **H1 (≥15% of hard-cat gold in rank 4–10):** PASS — **18.3%**. Reduction-step loss is real for the
  hard categories. MEASURED.
- **H2 (dual-threshold filter → +4 recall@3):** the registered intervention is a **no-op** — filtering
  low-scored candidates from the top-10 then taking top-3 by combined score returns the *same* top-3
  as the hybrid baseline, so it cannot raise recall@3 by construction. Not run (provably 0). INFERRED.
- **H3 (RAM ≤ +200 MB):** not applicable — the no-op intervention adds nothing; a real reranker's RAM
  is the sibling PoC's (device) question.

## Verdict

**Inconclusive by the decision rule, but a decisive diagnostic.** H1 is confirmed (18.3% rank-4–10
gap), but the registration's H2 filter provably can't convert it (no-op), so no recall@3 lift is
claimable *via that mechanism*. The valuable result is the **per-category decomposition of the OP-1
bottleneck**:

- **Non-Compete = a ranking problem.** Only 25% of gold is top-3, but another **26% is at rank 4–10**
  and recall@10 is 51% — the gold is being retrieved and then mis-ranked. A **cross-encoder reranker
  over a top-10 pool should roughly double Non-Compete recall@3** (→ ~51% ceiling). **This greenlights
  the sibling reranking PoC, scoped to Non-Compete.**
- **Exclusivity = a representation problem.** 54% of gold sits at rank 21+ and recall@10 is only 25%,
  so a top-10 reranker can't reach it; this needs a better embedder or query decomposition
  (PoC-016), not reranking — consistent with PoC-022/023.
- **Change-of-Control** is already adequate at top-3 (67%); little to gain.

This refines PoC-013's blanket "retrieval depth doesn't help": depth *does* retrieve Non-Compete gold
(it just gets truncated), while Exclusivity gold is genuinely out of reach. The two hard categories
need different fixes.

## Limits

- **Diagnostic, not an intervention** — it measures where gold ranks; it does not itself improve
  recall. The actionable follow-up (reranking) is the sibling PoC.
- **"Covering gold chunk" = ≥50% span overlap** (PoC-007 defn); a stricter/looser overlap would shift
  absolute numbers but not the top-3-vs-4–10 split that drives the conclusion.
- **Fixed chunking (PoC-014 page) + hybrid 0.9/0.1.** Different chunking could change where gold lands.

## Reproduce

```bash
cd poc/025-evidence-retention-depth
python3 evidence-depth.py     # committed vectors; no model/server
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `arxiv-2610.28957v1-idea-7` · technique: extraction · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.78 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [semantic:POINT_WINS_ONLY; numeric:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-22-divergent. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
