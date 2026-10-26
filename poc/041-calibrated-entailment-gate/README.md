# PoC 041: Calibrated entailment gate for absent clauses — Qwen YES/NO logprobs + threshold sweep (OP-7/OP-4)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending — do not fill until the run concludes._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox proposal `2026-10-25-a-lightweight-nlibased-postgeneration-entailment-check` (engine idea `oa-W4411127335-idea-7`, technique extraction, attacks OP-7; source: *Understanding and Mitigating LLM Hallucinations in HR Chatbots*). The lever **PoC-029's verdict explicitly named** ("an NLI/entailment check on the single top chunk") for the ~14% Qwen misses on absent hard clauses (PoC-026). |
| Registered | 2026-10-26 (this draft, before the first run) |

## Question

On the ~14% of absent hard-category items where Qwen2.5-1.5B currently hallucinates a positive answer
(PoC-026: 86.3% correct abstention), does a **calibrated** entailment gate on the top-1 retrieved chunk —
Qwen's own **P(YES)** token probability for "does this passage contain a [clause] clause?", thresholded at
a swept τ — raise Correct Abstention Rate (CAR) by **≥ +5 pp** while keeping answerable-recall loss
**≤ 3 pp**, i.e. reach an operating point that PoC-034's **binary** YES/NO gate could not?

## Why it matters here

- **PoC-034 already tried the binary version and failed on the tradeoff:** its YES/NO self-check lifted
  absent CAR +10.9 pp (84.2→95.0) but over-abstained on answerable items by **+21.7 pp** (52.0→73.7) — a
  single, uncalibrated operating point far past the ≤3 pp budget. The mechanism's problem was not *signal*
  but *calibration*: a binary gate is one fixed point on the precision/recall curve, with no way to trade
  a little CAR for much less answerable loss.
- **A continuous score fixes exactly that.** Reading Qwen's P(YES) (vs P(NO)) token probability turns the
  gate into a tunable threshold τ, so we can trace the whole CAR-gain vs answerable-loss curve and ask the
  decisive question 034 could not: *is there any τ that clears +5 pp CAR at ≤3 pp loss?*
- **6 GB-feasible and distinct from prior work.** It adds **zero parameters** (reuses the already-loaded
  Qwen — one extra forward pass), unlike a dedicated NLI model (infeasible alongside EmbeddingGemma+Qwen at
  6 GB). It is distinct from the **cosine** gates PoC-029/031 already rejected (those thresholded retrieval
  similarity; this thresholds a generative entailment judgement) and from PoC-034 (binary, uncalibrated).

## Hypothesis

A calibrated entailment gate has a usable operating point that the binary gate lacked, because P(YES) is
monotone in the model's evidence confidence and absent-clause top chunks concentrate at low P(YES).

- **H1:** ∃ threshold τ at which absent-clause **CAR gain ≥ +5 pp** over the PoC-026 baseline (86.3%).
- **H2:** at that same τ, **answerable-recall loss ≤ 3 pp** vs the no-gate baseline.
- **H3 (the real test):** the calibrated gate **dominates PoC-034's binary point** — i.e. at matched CAR
  gain it incurs strictly less answerable loss, or it reaches H1∧H2 simultaneously (which 034 could not).
- **H4 (feasibility):** one extra Qwen forward pass per item; host-measured latency recorded (device
  ≤ +1.5 s is the on-device claim, deferred to the device stage).

## Method

Reuse the **PoC-034 harness** verbatim for data, retrieval, and the absent/answerable framing; change
**only** the gate from a binary YES/NO string to a calibrated P(YES) with a threshold sweep.

- **Data.** Absent = PoC-008 `answerable=False` hard-category items (questions embedded fresh via
  EmbeddingGemma, same as 034). Answerable = PoC-007 hard-category items with gold spans (committed query
  vectors). Retrieval = hybrid 0.9/0.1, top-3 for the answer, **top-1 chunk** for the gate (as 034).
- **Gate score.** Prompt Qwen (:8091) `"Does the following contract passage explicitly contain a {cat}
  clause? Answer YES or NO only."` with `n_predict=1` + logprobs, and read **P(YES) = Σ prob of
  YES-starting first tokens** (normalised against the NO mass). Abstain iff `P(YES) < τ` **or** the base
  answer is a refusal (same `is_refusal` as 034 — the gate only *adds* abstentions).
- **Sweep.** τ over the observed P(YES) range; for each τ record absent CAR and answerable-recall loss;
  plot the curve; identify the **max CAR gain subject to loss ≤ 3 pp**, and the 034 binary point for
  comparison (recompute 034's YES/NO decision from the same logprobs at τ = argmax, i.e. P(YES) > P(NO)).
- **Varies:** the gate threshold τ (continuous). **Held fixed:** EmbeddingGemma hybrid retrieval, the
  PoC-014 chunk index, the PoC-008 absent set + PoC-007 answerable set, the top-1 gate passage, Qwen
  sampling (temperature 0.0). **Measurements:** CAR-gain/answerable-loss curve, best feasible operating
  point, 034-binary comparison, host latency. **Repetitions:** deterministic (temp 0) → single pass.
- Baseline stack: EmbeddingGemma 300M (~270 MB QAT Q4_0, `--embd-gemma-default`), Qwen2.5-1.5B Q4_K_M;
  device iPhone 15 Pro (6 GB); CUAD (397 contracts).

## Decision rule

Written before the first run.

- **Adopt** if **H1 ∧ H2** — ∃ τ with absent CAR gain ≥ +5 pp **and** answerable-recall loss ≤ 3 pp.
- **Reject** if **no** τ reaches +5 pp CAR at ≤ 5 pp loss (the curve is dominated, like 034's point) — the
  residual 14% is not separable by an entailment confidence and the generator is the hard limit.
- **Inconclusive** if a τ clears +5 pp CAR only at 3–5 pp loss (usable but over the H2 budget) — report the
  curve and the best operating point.
- Report the **full CAR/loss curve** and the explicit 034-binary comparison (H3) regardless of verdict.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 3-5 days

## Harness (to be implemented at run time)

`calibrated-gate.py` forks PoC-034's `entailment-selfcheck.py`: same data loading, retrieval, and
`is_refusal`; the gate call requests first-token logprobs (llama-server `logprobs`/`n_probs`) and returns
P(YES); a τ-sweep produces `results/calibrated-gate.json` (curve + best feasible point + 034-binary point)
and `results/comparison.txt`. Control: at τ = P(YES)>P(NO) the gate must reproduce PoC-034's binary CAR
(+10.9) and answerable loss (+21.7) within noise.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/041-calibrated-entailment-gate
python3 calibrated-gate.py          # absent+answerable hard-cat; τ-sweep; H1–H4 read-out
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `oa-W4411127335-idea-7` · technique: extraction · attacks: OP-7 · route `IN_FRAME_VALIDATE`.
- Micro-lab screen: **NOT_VALIDATABLE** (no runnable screening substrate) — carries only the gate signal;
  weighed accordingly. **Promotion reframe:** the proposal's "lightweight NLI model" is implemented as a
  **calibrated Qwen self-entailment** (zero new params, 6 GB-feasible) with a **threshold sweep** — the
  calibration is the novelty vs PoC-034's rejected binary gate, and the mechanism 029's verdict pointed to.
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. SCREENING signal, NOT a validated
  result — the lab runs the formal experiment; the 041 verdict feeds back to the ledger.
