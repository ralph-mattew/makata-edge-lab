# PoC 044: Self-reflection / self-critique loop on Qwen generation (OP-7)

| | |
|---|---|
| Status | Concluded — host stage (464 typed-fact items + 101 absent / 300 answerable hard-cat). |
| Verdict | **Reject — the self-critique pass is catastrophic for the 1.5B.** Key-fact accuracy **collapses 66.8% → 29.1% (−37.7 pp)** — every category craters (Renewal −56, Expiration −51, Governing-Law −42) — and the critique retracts **96%** of answerable hard-cat answers to "not stated" (answerable refusal 52.0% → 96.0%, **+44 pp**). Absent CAR "rises" 84.2% → 100% (+15.8) only because it now abstains on *everything* — a spurious pass. H1 FAIL (−37.7 ≪ +3), H4 FAIL (+44), H3 pass (1.73× latency), H2 technically pass but meaningless. Decision rule (key-fact gain < +1 pp) → **REJECT.** Strongest confirmation yet that generation-side self-correction destroys this model class (cf. 011/034/038/040/042/043). See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox proposal `2026-10-25-applying-a-selfreflection-selfcritique-loop-on-qwen2515bs-generated` (engine idea, OP-7; source: Portuguese legal-domain RAG). |
| Registered | 2026-10-26 (this draft, before the first run) |

## Question

Does a post-generation **self-critique** pass — Pass 1 answers from the top-3 chunks, Pass 2 asks the model
*"does the evidence actually support your answer? revise or abstain"* — improve **key-fact accuracy** on the
typed-fact items (≥ +3 pp) and **CAR** on absent hard clauses (≥ +2 pp) within a **≤ 2× latency** budget, on
our CUAD / Qwen2.5-1.5B stack?

## Why it matters here

- Self-reflection acts on the *generation* stage, not embeddings — the proposal's bet is that it is "the one
  generation-based trick that survives a tiny model." The ledger's prior is skeptical (PoC-011/034/038/040/042
  all show generation-side interventions degrade the 1.5B), so this is a direct, pre-registered test of that
  prior rather than a desk-rejection.
- If it works it needs no new model/RAM — only extra tokens (one more pass).

## Hypothesis

A critique pass lets the model catch unsupported answers and retract them. Transfer from the source
(Portuguese, unknown LLMs) is unverified; the 1.5B may instead flip correct answers or over-retract.

- **H1:** key-fact accuracy ≥ **+3 pp** over the single-pass baseline (measured on the 464 answerable
  typed-fact items — see Deviations: hard categories carry no typed key_facts, cf. PoC-042).
- **H2:** CAR on absent hard-category items ≥ **+2 pp** over PoC-026 (86.3%).
- **H3:** end-to-end latency ≤ **2×** the single-pass baseline (one extra generation pass).
- **H4 (guard):** answerable refusal does not inflate > 3 pp (over-retraction guard, cf. 034/042).

## Method

Reuse the PoC-042 key-fact path (hybrid 0.9/0.1 top-3 over committed PoC-014 chunks; key-fact via PoC-006
`facts.py`) and the PoC-041 CAR path (absent/answerable hard-cat). **Two-pass generation:** Pass 1 =
standard answer; Pass 2 = critique prompt *"Review your answer against the sections. If any part is not
supported, correct it; if nothing supports it, reply 'not stated'."* fed the Pass-1 answer + the same
sections; the Pass-2 output is the final answer. Compare key-fact (typed-fact items), CAR (absent hard),
answerable refusal, and wall-clock latency vs the single-pass baseline on identical retrieval.

- **Varies:** single-pass vs self-reflection (two-pass). **Held fixed:** retrieval, chunks, Qwen sampling
  (temp 0), eval sets. **Measurements:** overall + per-category key-fact, absent CAR, answerable refusal,
  per-query latency (both passes). **Repetitions:** deterministic → single pass.
- Baseline stack: EmbeddingGemma 300M (`--embd-gemma-default`), Qwen2.5-1.5B Q4_K_M; CUAD (397 contracts).

## Decision rule

- **Adopt** if **H1 (key-fact ≥ +3 pp) ∧ H3 (latency ≤ 2×)** and H4 holds.
- **Reject** if hard-category/overall key-fact gain **< +1 pp**.
- **Inconclusive** if gain +1–2 pp or latency > 2×.

## Expected outcome (engine estimate, not a result)

inconclusive · confidence 0.45 · est. effort 3-5 days

## Harness

`self-reflect.py` wraps the PoC-042 generate→score path with a second critique pass (Pass 2 = *"review the
draft against the sections; correct unsupported parts, or reply 'not stated'"*). Scores key-fact (464
typed-fact items, PoC-006 `facts.py`) + CAR/answerable-refusal (absent/answerable hard, PoC-041 logic) +
wall-clock latency (both passes). Writes `results/self-reflect.json` + per-item `results/raw/keyfact.jsonl`.
Reads gitignored vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (Qwen2.5-1.5B-Instruct Q4_K_M, temp 0), deterministic single pass. Baseline = Pass-1
answer; self-reflection = Pass-2 revised answer, on identical retrieval.

| Metric | baseline | self-reflection | Δ |
|---|---|---|---|
| key-fact accuracy (464 typed-fact items) | **66.8%** | **29.1%** | **−37.7 pp** |
| absent-clause CAR (101 hard) | 84.2% | 100.0% | +15.8 pp |
| answerable refusal (300 hard) | 52.0% | 96.0% | **+44.0 pp** |
| latency multiplier | 1× | **1.73×** | — |

Per fact-category key-fact (baseline → reflection): Renewal Term 84.6→28.6 (**−56.0**), Expiration Date
62.3→11.5 (−50.8), Notice Period 68.4→24.2 (−44.2), Governing Law 94.6→52.7 (−41.9), Warranty Duration
42.5→30.0 (−12.5), Agreement Date 29.8→21.4 (−8.3).

- **Control:** baseline key-fact 66.8% reproduces PoC-009's 67.9% / PoC-042's 66.8%. MEASURED.
- **H1 (key-fact ≥ +3 pp):** **FAIL** — **−37.7 pp**, every category collapses. MEASURED.
- **H2 (CAR ≥ +2 pp):** technically PASS (+15.8) but **spurious** — CAR hits 100% only because the critique
  abstains on *everything* (answerable refusal simultaneously +44 pp). MEASURED.
- **H3 (latency ≤ 2×):** PASS — 1.73×. MEASURED.
- **H4 (answerable refusal ≤ +3 pp):** **FAIL** — **+44.0 pp** (retracts 96% of genuine answers). MEASURED.

Per-item draft/final in `results/raw/keyfact.jsonl`.

## Verdict

**Reject.** The self-critique pass does not refine the 1.5B's answers — it demolishes them. Asked to review
its draft and "correct unsupported parts or say 'not stated'," the model defaults to wholesale retraction:
it abstains on 96% of answerable items and loses 37.7 points of key-fact accuracy, with the steepest drops
on the categories it was previously *best* at (Renewal Term 84.6→28.6, Governing Law 94.6→52.7). The
apparent +15.8 pp absent-CAR gain is an artifact of indiscriminate abstention, not improved discrimination
— it is the same over-abstention that sank the entailment gates (034/041/043), now triggered by a critique
prompt instead of a gate.

This is the **strongest instance** of the series' consolidated finding: generation-side self-correction is
not "the one trick that survives a tiny model" — it is actively harmful. The 1.5B lacks the meta-cognitive
reliability to judge its own support; given a license to retract, it retracts correct answers. Combined with
PoC-011 (generated context hurt retrieval), 034 (self-check over-abstained), 038 (HyDE backfired), 040
(generator not the lever), and 042 (attribution degraded key-fact), the guidance is now unambiguous: **do
not add generation-side reasoning/critique/attribution passes to this model class.** Keep generation
single-pass and minimal; leverage is upstream (retrieval recall, span representation), not in the generator.

## Deviations

- **H1 measured on typed-fact items, not hard categories.** As established in PoC-042, the hard categories
  (Exclusivity / Non-Compete / Change-of-Control) carry **no typed `key_facts`** (clause-presence, not
  typed-fact extraction), so hard-category key-fact is undefined; the key-fact hypothesis is evaluated on
  the 464 typed-fact items where the metric applies. Hard-category behaviour is covered by the CAR arm.

## Limits

- **One critique-prompt wording.** A gentler prompt might retract less, but a −37.7 pp collapse and 96%
  retraction indicate the model's self-judgement, not the wording, is the binding failure.
- **Host stage, temp 0, single pass.** Latency is host wall-clock (1.73×); device latency not measured.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/044-self-reflection-loop && python3 self-reflect.py
# from a detached worktree:  LAB_POC_ROOT=/path/to/lab-clone/poc python3 self-reflect.py
```

---

### Engine provenance

- Engine idea (OP-7), unscreened. Promoted per the user's directive to **run rather than desk-reject**, as a
  formal pre-registered test of the "generation-side helps the 1.5B" prior. Verdict feeds back to the ledger.
