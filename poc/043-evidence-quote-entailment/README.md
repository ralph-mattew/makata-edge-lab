# PoC 043: Evidence-quote entailment gate for absent clauses (OP-7)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending — do not fill until the run concludes._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox proposal `2026-10-25-a-zeroparameter-entailment-check-implemented-as-a-structured` (engine idea, OP-7; sources: *HR-chatbot hallucination* + *ULME*). |
| Registered | 2026-10-26 (this draft, before the first run) |

## Question

Does a **zero-parameter evidence-quote** gate — ask Qwen to *quote the exact sentence* that proves the
clause exists on the top retrieved chunk, or write ABSENT, and **verify the quote is actually present** in
the chunk (substring grounding) — raise Correct Abstention Rate (CAR) on absent hard clauses by **≥ +5 pp**
over the PoC-026 baseline (86.3%) at **≤ 3 pp** answerable-recall loss — i.e. where PoC-034 (binary) and
PoC-041 (calibrated P(YES)) both failed?

## Why it matters here

- PoC-041 showed a *confidence* threshold on Qwen's YES/NO cannot separate absent from
  answerable-but-poorly-retrieved (the whole frontier is dominated). This proposal attacks the problem
  differently: instead of thresholding confidence, it demands a **verbatim quote** and **grounds it** with a
  substring check — a hallucinated or empty quote forces abstention. If the model can only confirm presence
  when it can point to real text, the gate might abstain *honestly* on absent items without the collateral
  over-abstention 034/041 incurred.
- It is the last distinct variant of the entailment-gate family (034 binary YES/NO, 041 calibrated P(YES),
  043 quote-grounded) — a clean test of whether **grounding**, not calibration, is the missing ingredient.
- Zero new parameters (one extra Qwen pass), 6 GB-feasible.

## Hypothesis

Forcing a verifiable quote changes the error mode: absent items have no sentence to quote (→ ABSENT or a
quote that fails the substring check → abstain), while answerable items with the clause in the top chunk
yield a real quote (→ answer). Untested on our stack.

- **H1:** absent-clause CAR gain **≥ +5 pp** over 86.3%.
- **H2:** answerable-recall loss **≤ 3 pp** (the quote requirement does not gate out genuine answers).
- **H3:** the quote-grounded gate **beats PoC-041's dominated frontier** — reaches H1∧H2 where the
  confidence threshold could not (max CAR gain at ≤3 pp loss was 0.0).
- **H4:** one extra Qwen pass per item (host latency recorded; device deferred).

## Method

Fork the PoC-041/034 harness (same absent = PoC-008 hard-cat `answerable=False`, answerable = PoC-007
hard-cat, hybrid 0.9/0.1 retrieval, `is_refusal`). Replace the gate with an **evidence-quote** prompt on
the top-1 chunk: *"Quote the exact sentence from the passage that confirms a [clause] clause exists. If no
such sentence exists, write ABSENT."* Parse: **abstain iff** the reply is ABSENT/empty **or** the quoted
span (normalised, ≥6 content words) is **not a substring** of the chunk (hallucinated quote). The base
answer path is unchanged; the gate only *adds* abstentions (as 034/041).

- **Varies:** the gate (quote + substring grounding) vs no gate. **Held fixed:** retrieval, chunk index,
  absent/answerable sets, Qwen sampling (temp 0). **Measurements:** absent CAR, answerable-recall loss,
  quote-grounding-failure rate (quotes that weren't in the chunk), host latency. **Repetitions:**
  deterministic → single pass.
- Baseline stack: EmbeddingGemma 300M (`--embd-gemma-default`), Qwen2.5-1.5B Q4_K_M; CUAD (397 contracts).

## Decision rule

- **Adopt** if **H1 (CAR ≥ +5 pp) ∧ H2 (loss ≤ 3 pp)**.
- **Reject** if CAR gain **< +2 pp** or answerable-recall loss **> 5 pp**.
- **Inconclusive** if CAR gain 2–5 pp. Report the 034/041 comparison (H3) regardless.

## Expected outcome (engine estimate, not a result)

promising · confidence 0.52 · est. effort 3-4 days

## Harness (to be implemented at run time)

`quote-gate.py` forks `041/calibrated-gate.py`: same data/retrieval/`is_refusal`; the gate calls Qwen for a
quote and applies a substring-grounding check; writes `results/quote-gate.json` (CAR, loss, grounding-fail
rate, 034/041 comparison) + `results/comparison.txt`. Reads gitignored vectors via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/043-evidence-quote-entailment && python3 quote-gate.py
```

---

### Engine provenance

- Engine idea (OP-7), unscreened. Promoted alongside the held faithfulness batch per the user's directive
  to **run rather than desk-reject**. Distinct from PoC-034 (binary) / 041 (calibrated) by the
  quote-grounding mechanism. Verdict feeds back to the ledger.
