# PoC 058: Qwen-1.5B as a length-limited LLM reranker (OP-1)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Source idea | Inbox `2026-10-27-limiting-candidate-text-length-when-using-qwen2515b-as` (engine `arxiv-2610.34816v1-idea-3`, OP-1). |
| Registered | 2026-10-27 (before the first run). |

## Question

Can the already-resident Qwen2.5-1.5B, used as a **length-limited pointwise reranker** over a top-10
candidate pool (short windows), promote hard-category gold from rank 4–10 into top-3 — lifting hard-mean
recall@3 by ≥ +5 pp over the hybrid baseline — without a second (cross-encoder) model?

## Why it matters here

- PoC-025 showed Non-Compete gold sits at rank 4–10; a reranker could promote it. Reusing Qwen avoids the
  cross-encoder PoC-012 parked on latency.
- **Cautionary priors:** PoC-027 (cross-encoder rerank) *collapsed* on distractors (NC 25→8–15); routing
  retrieval through the 1.5B (HyDE 038, gates 034/041/043) has failed repeatedly. And hard-cat retrieval is
  now **solved** by PoC-053 (clause-term binding, recall@3 54.0) — so this must clear a high bar to matter.

## Hypothesis

A short-window pointwise relevance score from Qwen may rerank better than a cross-encoder did (no whole-chunk
reordering); but the 1.5B's weak discrimination may still demote correct clauses.

- **H1:** Qwen-reranked top-3 hard-mean recall@3 ≥ +5 pp over the hybrid baseline (34.7).
- **H2:** it does **not** regress vs the pre-rerank top-3 on any hard category (distractor-robustness, cf. 027).

## Method

Retrieve top-10 per hard item (hybrid 0.9/0.1). For each candidate chunk, prompt Qwen for a short relevance
judgement (constrained: "Does this passage contain a {category} clause? score 0-3" or YES/NO + logprob),
using a length-limited window. Re-rank top-10 by the Qwen score, take top-3, score recall@3 overall + per
hard category vs the hybrid baseline and the pre-rerank top-3. Deterministic (temp 0).

## Decision rule

Adopt if **H1 (+≥5) ∧ H2 (no per-cat regression)**. Reject if recall@3 regresses vs baseline (027 failure
mode) or gain < +2. Inconclusive between.

## Harness (run-time)

`qwen-rerank.py`: hybrid top-10 → Qwen pointwise score (logprob of YES, reuse 041's `qwen_pyes`) → rerank →
recall@3. Reads committed vectors via `LAB_POC_ROOT`; Qwen :8091.

---
### Engine provenance
`arxiv-2610.34816v1-idea-3` · OP-1 · UNSCREENED. Overlaps rejected 027/parked 012; hard-cat retrieval closed
by 053. Verdict feeds back to the ledger.
