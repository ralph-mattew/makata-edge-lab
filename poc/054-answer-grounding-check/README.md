# PoC 054: Lightweight answer-grounding post-check for absent clauses (OP-7)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Source idea | Inbox `2026-10-27-a-lightweight-hallucinationreduction-postprocessing-step` (engine `oa-W4400064731-idea-2`, extraction, OP-7; CLERC hallucination-vs-fluency). |
| Registered | 2026-10-27 (before the first run). |

## Question

Does a zero-parameter **answer-grounding** post-check — abstain if the generated answer's content tokens
are not sufficiently present in the retrieved chunk (token-overlap / substring) — raise Correct Abstention
Rate on absent hard clauses (≥ +5 pp) at ≤ 3 pp answerable-recall loss?

## Why it matters here

- Targets the residual ~14% absent-clause hallucinations (PoC-026). Unlike the entailment gates (034/041/043)
  it checks the *generated answer* against the chunk, not a yes/no judgement — but it is the same family.
- **Cautionary prior:** PoC-043 (quote + substring grounding) rejected at +27 pp answerable loss; 041 (calibrated
  P(YES)) and 034 (binary) also dominated. The open question is whether an *overlap-fraction threshold* on the
  answer (vs a quote) opens any ≤3 pp-loss operating point.

## Hypothesis

A hallucinated positive answer on an absent clause will have low token overlap with the (wrong) retrieved
chunk; a genuine answer overlaps its gold chunk. Threshold the overlap fraction and sweep.

- **H1:** ∃ overlap threshold τ with absent CAR gain ≥ +5 pp over PoC-026 (86.3%).
- **H2:** at that τ, answerable-recall loss ≤ 3 pp.
- **H3:** beats the dominated frontier of 041/043 (reach H1∧H2 where they could not).

## Method

Fork PoC-041/043 (absent = PoC-008 hard `answerable=False`, answerable = PoC-007 hard; hybrid 0.9/0.1 top-3;
Qwen answer). Compute answer↔top-chunk **content-token-overlap fraction**; abstain iff base refusal OR overlap
< τ. Sweep τ∈[0,1]; trace CAR-gain vs answerable-loss curve; best feasible point; 041/043 comparison.
Deterministic (temp 0).

## Decision rule

Adopt if ∃τ with CAR +≥5 ∧ loss ≤3. Reject if no τ reaches +5 CAR at ≤5 loss (dominated, like 041/043).
Inconclusive between.

## Harness (run-time)

`grounding-check.py` forks `041/calibrated-gate.py`: replace the P(YES) gate with answer-vs-chunk overlap
fraction; τ-sweep; `results/grounding-check.json` + curve. Reads committed vectors via `LAB_POC_ROOT`.

---
### Engine provenance
`oa-W4400064731-idea-2` · OP-7 · UNSCREENED. Same gate family as 029/031/034/041/043 (all rejected);
tests the answer-overlap variant. Verdict feeds back to the ledger.
