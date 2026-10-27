# PoC 058: Qwen-1.5B as a length-limited LLM reranker (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (300 hard items; recall@3). |
| Verdict | **Reject — Qwen reranking reproduces PoC-027's failure mode and is dominated by PoC-053.** Reranking the hybrid top-10 by Qwen's P(YES) relevance score barely moves hard-mean recall@3 (**34.7 → 36.0, +1.3**) and — like the PoC-027 cross-encoder — **promotes some categories while demoting others**: Exclusivity 6 → 16 and Non-Compete 33 → 36, but **Change-of-Control 65 → 56 (−9)**. H1 (+≥5) FAIL, H2 (no per-cat regression) FAIL (CoC −9) → **REJECT.** The 1.5B's pointwise relevance judgement is too noisy to reorder reliably (same lesson as 027), and it is **far dominated by PoC-053** (clause-term query binding, recall@3 54.0) which solves hard-cat retrieval at the query stage with no per-item LLM calls. See Verdict. |
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

## Harness

`qwen-rerank.py`: hybrid 0.9/0.1 top-10 per hard item → Qwen pointwise relevance score (P(YES) from
first-token logprobs, length-limited 600-char window) → rerank → top-3 → recall@3, vs the pre-rerank
hybrid top-3. Reads committed vectors via `LAB_POC_ROOT`; Qwen :8091.

## Results

MEASURED on the host (Qwen2.5-1.5B Q4_K_M, temp 0), **300 hard items**, recall@3.

| Arm | hard-mean | Exclusivity | Non-Compete | Change-of-Control |
|---|---|---|---|---|
| hybrid top-3 (baseline) | 34.7 | 6 | 33 | 65 |
| Qwen-reranked top-3 | 36.0 | 16 | 36 | **56** |
| Δ | +1.3 | +10 | +3 | **−9** |

- **H1 (+≥5):** FAIL — +1.3. MEASURED.
- **H2 (no per-category regression):** FAIL — Change-of-Control **−9** (65 → 56). MEASURED.
- Decision rule (regression OR Δ<2) → **REJECT**. MEASURED.

Summary in `results/qwen-rerank.json`.

## Verdict

**Reject.** The Qwen-as-reranker idea hits exactly the wall PoC-027 found with a cross-encoder: a weak
pointwise relevance model **promotes some hard-category gold and demotes others**. Here it lifts Exclusivity
(6 → 16) and nudges Non-Compete (33 → 36) but *demotes* Change-of-Control (65 → 56), for a net +1.3 that
fails both the +5 bar and the no-regression guard. The 1.5B simply cannot judge passage relevance reliably
enough to reorder — consistent with every generation-in-the-loop-for-retrieval result in the series (HyDE
038, entailment gates 034/041/043).

Decisively, the question this PoC set out to answer — can we promote NC gold from rank 4–10 into top-3 — is
**already solved upstream and far better** by PoC-053 (clause-term query binding, recall@3 **54.0** hard-mean)
and PoC-045 (GreenLeaf embedder), neither of which needs a per-item LLM rerank call. The hard-category
retrieval problem is closed; a Qwen reranker is both weaker and more expensive. Do not pursue LLM reranking
on this stack.

## Limits

- **Pointwise P(YES) scoring, 600-char window, top-10 pool.** A listwise prompt or longer window might
  reorder differently, but the CoC regression + the 053 dominance make a reversal immaterial.
- recall@3 only; Qwen rerank also adds ~10 LLM calls/query (latency) that the query-side levers avoid.

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/058-qwen-llm-reranker
LAB_POC_ROOT=/path/to/lab-clone/poc python3 qwen-rerank.py
```

---
### Engine provenance
`arxiv-2610.34816v1-idea-3` · OP-1 · UNSCREENED. Overlaps rejected 027/parked 012; hard-cat retrieval closed by 053. Verdict **REJECT** — reproduces 027's demotion failure (CoC -9), dominated by 053. Feeds back to the ledger.
