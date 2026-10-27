# PoC 059: Generation context depth k=3 vs k=5 (OP-2)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Source idea | Inbox `2026-10-27-using-only-3-retrieved-passages-vs-5` (engine `arxiv-2610.33732v1-idea-6`, OP-2). |
| Registered | 2026-10-27 (before the first run). |

## Question

Does feeding the Qwen generator **k=5** retrieved passages degrade key-fact accuracy vs **k=3** (the source
reports 75%→52% for a small Qwen), confirming k=3 as the adopted generation depth from the *generation*
side (PoC-009 confirmed it for recall)?

## Why it matters here

- Cheap confirmatory check: if more context hurts the 1.5B's answers, it locks in k=3 and tells OP-8 that
  freed RAM should fund a *bigger generator*, not a *wider context window*.

## Hypothesis

More passages add distractors a 1.5B can't filter, lowering key-fact.

- **H1 (confirm):** k=5 key-fact ≥ 5 pp **below** k=3 → k=3 confirmed optimal.
- **H2 (refute dilution):** k=5 within 2 pp of k=3 → depth is not the lever.

## Method

Reuse the PoC-042 key-fact harness (464 typed-fact items; hard cats carry no typed key_facts, cf. 042).
Generate answers with Qwen at k∈{3,5} retrieved passages (hybrid 0.9/0.1), identical prompt; score key-fact
set-overlap (`facts.py`) + answerable refusal. Deterministic (temp 0).

## Decision rule

Confirm k=3 if k=5 is ≥ 5 pp below k=3. Refute dilution if within 2 pp. Inconclusive between. (Descriptive —
no new mechanism adopted; informs the k setting + OP-8 allocation.)

## Harness (run-time)

`context-depth.py` forks `042/attribution.py` baseline arm with a `--k {3,5}` sweep (no attribution prompt).
Reads committed vectors via `LAB_POC_ROOT`; Qwen :8091.

---
### Engine provenance
`arxiv-2610.33732v1-idea-6` · OP-2 · UNSCREENED. Confirmatory (validates k=3 from the generation side).
Verdict feeds back to the ledger.
