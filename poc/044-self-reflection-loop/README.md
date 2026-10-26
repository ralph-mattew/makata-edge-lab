# PoC 044: Self-reflection / self-critique loop on Qwen generation (OP-7)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending — do not fill until the run concludes._ |
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

## Harness (to be implemented at run time)

`self-reflect.py` wraps the PoC-042 generate→score path with a second critique pass; scores key-fact
(typed-fact items) + CAR (absent hard, reusing 041's refusal logic) + latency; writes
`results/self-reflect.json` + `results/comparison.txt`. Reads gitignored vectors via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/044-self-reflection-loop && python3 self-reflect.py
```

---

### Engine provenance

- Engine idea (OP-7), unscreened. Promoted per the user's directive to **run rather than desk-reject**, as a
  formal pre-registered test of the "generation-side helps the 1.5B" prior. Verdict feeds back to the ledger.
