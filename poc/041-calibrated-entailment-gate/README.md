# PoC 041: Calibrated entailment gate for absent clauses — Qwen YES/NO logprobs + threshold sweep (OP-7/OP-4)

| | |
|---|---|
| Status | Concluded — host stage (101 absent + 300 answerable hard-category items, τ-swept). |
| Verdict | **Reject — calibration does not rescue the gate; absent and answerable P(YES) overlap too heavily.** The control is exact: at τ=0.5 the calibrated gate reproduces PoC-034's binary point to the decimal (absent CAR +10.9 pp → 95.0%, answerable loss +21.7 pp). But the whole curve is dominated: reaching **+5 pp CAR costs ≥ 12.3 pp** answerable-recall loss, and the **max CAR gain at ≤3 pp loss (H2) is 0.0** (and 0.0 even at ≤5 pp). H1∧H2 unreachable; **H3 fails** — calibration buys nothing because Qwen's entailment confidence is no more separable than the cosine it replaces. By the decision rule (no τ clears +5 pp CAR at ≤5 pp loss) → **REJECT.** This closes the confidence-gate avenue for absent hard clauses (PoC-029 cosine → 031 → 034 binary → 041 calibrated all fail for the same reason): the top-1 chunk for *answerable* hard-cat items frequently doesn't "contain" the clause either (weak hard-cat retrieval), so no entailment threshold can separate absent from answerable. See Verdict. |
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

## Harness

`calibrated-gate.py` forks PoC-034's `entailment-selfcheck.py`: identical data loading, hybrid 0.9/0.1
retrieval, absent/answerable framing, and `is_refusal`. The only change is `qwen_pyes()` — the gate call
requests first-token logprobs (`logprobs: true, top_logprobs: 20`) and returns **normalised P(YES)** (YES-
vs NO-starting token mass). A τ-sweep (0.00–1.00, step 0.01) writes `results/calibrated-gate.json` (full
curve + best-feasible point + the 034 binary point) and `results/comparison.txt`; per-item probes in
`results/raw/{absent,answerable}-probes.jsonl`. Gitignored committed vectors are read from the lab clone
via `LAB_POC_ROOT` (defaults to the sibling `poc/` dir for a normal clone).

## Results

MEASURED on the host (Mac16,8 M4 Pro; EmbeddingGemma `--embd-gemma-default` + Qwen2.5-1.5B-Instruct
Q4_K_M, temperature 0), **101 absent + 300 answerable** hard-category items, deterministic single pass.
Gate operates on the **top-1** retrieved chunk; abstain iff `P(YES) < τ` OR the base answer is a refusal.

- **Baselines (control):** absent CAR (base refusal only) **84.2%**; answerable baseline refusal **52.0%**
  — both match PoC-034 exactly. MEASURED.
- **034 binary point reproduced exactly:** at τ=0.5, absent CAR **95.0% (+10.9 pp)**, answerable loss
  **+21.7 pp** — identical to PoC-034's reported numbers. The fork is validated. MEASURED.

CAR-gain vs answerable-recall-loss curve (selected τ):

| τ | absent CAR | CAR gain | answerable-recall loss |
|---|---|---|---|
| 0.10 | 89.1% | +5.0 | **+12.3** |
| 0.20 | 90.1% | +5.9 | +15.3 |
| 0.30 | 94.1% | +9.9 | +17.7 |
| 0.40 | 95.0% | +10.9 | +19.7 |
| **0.50 (034 binary)** | 95.0% | +10.9 | +21.7 |
| 0.70 | 96.0% | +11.9 | +25.0 |
| 0.90 | 99.0% | +14.9 | +35.3 |

- **H1 (∃τ with CAR gain ≥ +5 pp):** technically yes (τ≥0.10), but only at ruinous loss. The **minimum
  answerable-recall loss to reach +5 pp CAR is +12.3 pp**. MEASURED.
- **H2 (loss ≤ 3 pp at that τ):** **FAIL** — max CAR gain at ≤3 pp loss is **0.0** (and 0.0 even at ≤5 pp).
  MEASURED.
- **H3 (calibrated dominates 034's binary point):** **FAIL** — the binary point lies *on* the same
  dominated curve; the continuous threshold exposes no better operating point. Calibration buys nothing.
  MEASURED.
- **H4 (feasibility):** one extra Qwen forward pass per item (1-token gate) — negligible host overhead;
  device latency deferred. OBSERVED.

Full curve + per-item probes in `results/calibrated-gate.json` / `results/raw/`.

## Verdict

**Reject.** The calibrated gate was the right way to test whether PoC-034's binary entailment gate failed
on *calibration* or on *signal* — and the answer is unambiguous: it failed on **signal**. The P(YES)
threshold sweep traces the entire precision/recall frontier, and the frontier is dominated everywhere
above a few points of CAR: there is no operating point with ≥ +5 pp CAR at ≤ 3 pp (or even ≤ 5 pp)
answerable-recall loss. The absent-clause P(YES) distribution overlaps the answerable one too heavily.

The mechanism fails for a now-familiar structural reason: **hard-category retrieval is weak**, so the
top-1 chunk often does not "contain" the clause *even for answerable items* — the model correctly reports
low P(YES), and the gate abstains on genuine answers. The gate cannot separate "absent" from
"answerable-but-poorly-retrieved" because that distinction isn't present in the top-1 chunk it sees.

This **closes the confidence-gate avenue for absent hard clauses**: PoC-029 (global cosine), PoC-031
(entailment proxy), PoC-034 (binary entailment), and now PoC-041 (calibrated entailment) all reject for
the same separability ceiling — moving the gate from a retrieval score to a generative entailment
judgement does not raise the ceiling. The residual ~14% absent-clause hallucinations (PoC-026) are not
addressable by a post-hoc confidence gate; the leverage is upstream (hard-category retrieval recall) or in
the answer representation (evidence the gate can actually see), not in thresholding a confidence signal.

## Limits

- **Top-1 gate passage** (as PoC-034). A gate over the top-3 union might see the clause more often for
  answerable items — but that also feeds more distractors to absent items; given the curve is dominated by
  >9 pp, a top-3 gate is unlikely to open a ≤3 pp-loss window. Untested.
- **P(YES) from YES/NO-starting token mass** (first token, top-20 logprobs). A richer entailment prompt or
  multi-token scoring could sharpen the score, but the overlap is large enough that calibration quality is
  not the binding constraint.
- **Hard categories only, host stage.** Absent set = PoC-008 (101), answerable = PoC-007 (300);
  distributions, not paired items. Device latency (H4) deferred.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/041-calibrated-entailment-gate
python3 calibrated-gate.py          # absent+answerable hard-cat; τ-sweep; H1–H4 read-out
# from a detached worktree where gitignored vectors aren't checked out:
#   LAB_POC_ROOT=/path/to/lab-clone/poc python3 calibrated-gate.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `oa-W4411127335-idea-7` · technique: extraction · attacks: OP-7 · route `IN_FRAME_VALIDATE`.
- Micro-lab screen: **NOT_VALIDATABLE** (no runnable screening substrate) — carries only the gate signal;
  weighed accordingly. **Promotion reframe:** the proposal's "lightweight NLI model" is implemented as a
  **calibrated Qwen self-entailment** (zero new params, 6 GB-feasible) with a **threshold sweep** — the
  calibration is the novelty vs PoC-034's rejected binary gate, and the mechanism 029's verdict pointed to.
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. SCREENING signal (NOT_VALIDATABLE)
  — the lab ran the formal experiment; verdict **REJECT** (confidence gates can't separate absent from
  answerable-but-poorly-retrieved) feeds back to the ledger.
