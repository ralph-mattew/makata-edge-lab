# PoC 043: Evidence-quote entailment gate for absent clauses (OP-7)

| | |
|---|---|
| Status | Concluded — host stage (101 absent + 300 answerable hard-category items). |
| Verdict | **Reject — grounding amplifies the same separability failure, it doesn't fix it.** The quote-grounded gate pushes absent CAR *higher* than any prior gate — **84.2% → 98.0% (+13.9 pp)**, beating PoC-034's +10.9 — but at the **worst answerable-recall loss yet: +27.0 pp** (52.0% → 79.0%). The substring-grounding check abstains on **66.7%** of *answerable* items because weak hard-cat retrieval means the top-1 chunk often lacks a verbatim clause sentence to quote even when the clause exists. H1 (CAR ≥ +5) passes but **H2 (loss ≤ 3) fails hard (+27)** and **H3 fails** (does not beat 041's dominated frontier — it sits further along the *same* dominated curve). Decision rule: loss > 5 pp → **REJECT.** Third confirmation after 034/041 that the entailment-gate family cannot separate absent from answerable-but-poorly-retrieved; grounding makes over-abstention worse, not better. See Verdict. |
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

## Harness

`quote-gate.py` forks `041/calibrated-gate.py`: identical data/retrieval/`is_refusal`. The gate asks Qwen
to quote the clause sentence (or ABSENT) on the top-1 chunk; `quote_grounded()` abstains iff the reply is
ABSENT/empty **or** no contiguous run of ≥6 content-words from the quote appears in the chunk's content-word
sequence (token-level grounding, robust to whitespace/case). Writes `results/quote-gate.json` + per-item
probes. Reads gitignored vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default` + Qwen2.5-1.5B-Instruct Q4_K_M, temp 0),
**101 absent + 300 answerable** hard-category items, deterministic single pass. Gate on the top-1 chunk;
abstain iff ABSENT/empty quote OR quote not grounded in the chunk.

| | absent CAR | answerable refusal |
|---|---|---|
| baseline (no gate) | 84.2% | 52.0% |
| **quote-grounded gate** | **98.0% (+13.9 pp)** | **79.0% (+27.0 pp)** |
| gate abstentions from quote-grounding failure | 80.2 pp of absent | 66.7 pp of answerable |

- **Control:** baseline absent CAR 84.2% / answerable refusal 52.0% — matches PoC-034/041. MEASURED.
- **H1 (CAR ≥ +5 pp):** PASS — **+13.9 pp** (higher than 034's +10.9 and 041's). MEASURED.
- **H2 (answerable-recall loss ≤ 3 pp):** **FAIL** — **+27.0 pp** (worse than 034's +21.7). MEASURED.
- **H3 (beats 041's dominated frontier):** **FAIL** — the (CAR +13.9, loss +27) point lies further along the
  *same* dominated frontier; no better CAR/loss tradeoff than 034/041. MEASURED.
- **Why:** grounding-failure abstentions fire on **66.7%** of answerable items — the top-1 chunk for an
  answerable hard-cat item frequently contains no verbatim ≥6-word clause sentence (weak retrieval, or Qwen
  paraphrases), so the grounding check retracts genuine answers. MEASURED.

Per-item probes in `results/raw/{absent,answerable}-probes.jsonl`.

## Verdict

**Reject.** The evidence-quote gate was the sharpest test of whether *grounding* (demand a verifiable
verbatim quote), rather than *calibration* (041) or a *binary decision* (034), was the missing ingredient
for absent-clause abstention. It is not. Requiring a grounded quote drives absent CAR to 98% — the highest
of the family — but at +27 pp answerable-recall loss, the worst of the family, because the grounding check
cannot distinguish "no clause exists" (correct abstain) from "the clause exists but isn't a verbatim
sentence in the weakly-retrieved top-1 chunk" (wrong abstain). Both produce an ungroundable quote.

This is the **third confirmation** (after PoC-034 binary and PoC-041 calibrated) that the entailment-gate
family hits the same wall identified in PoC-029: absent and answerable-but-poorly-retrieved items are not
separable at the gate, regardless of whether the gate thresholds a decision, a confidence, or a quote's
groundedness. The binding constraint is upstream **hard-category retrieval recall** — until the gold clause
is reliably in the passage the gate inspects, no post-hoc verification can tell the two cases apart. The
avenue (029/031/034/041/043) is closed; effort belongs on retrieval recall and span representation.

## Limits

- **Top-1 gate passage** (as 034/041). A top-3 gate would raise grounded-quote availability for answerable
  items but also give absent items more text to spuriously quote; given the +27 pp gap, unlikely to open a
  ≤3 pp window. Untested.
- **Grounding = ≥6 contiguous content-words** present in the chunk. Looser grounding would cut answerable
  loss but also admit more absent hallucinations (weaker gate) — it trades along the same dominated frontier.
- **Hard categories only, host stage.** Absent = PoC-008 (101), answerable = PoC-007 (300).

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/043-evidence-quote-entailment && python3 quote-gate.py
# from a detached worktree:  LAB_POC_ROOT=/path/to/lab-clone/poc python3 quote-gate.py
```

---

### Engine provenance

- Engine idea (OP-7), unscreened. Promoted alongside the held faithfulness batch per the user's directive
  to **run rather than desk-reject**. Distinct from PoC-034 (binary) / 041 (calibrated) by the
  quote-grounding mechanism. Verdict **REJECT** (grounding amplifies the same separability failure) feeds back to the ledger.
