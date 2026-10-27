# PoC 055: Minimal single-chunk (k=1) extraction prompt (OP-2)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Source idea | Inbox `2026-10-27-a-minimal-singlechunk-extraction-prompt-fixing-k1` (engine `evo-g2-6`, structured-blend, OP-2; false-null screen). |
| Registered | 2026-10-27 (before the first run). |

## Question

Does fixing **k=1** (top chunk only) + a bare span-extraction prompt beat the k=3 answer step on
hard-category **span-F1**, avoiding both the instruction-overload (PoC-042) and context-dilution the
Raspberry-Pi study reported for small Qwen (k=3→k=5: 75%→52%)?

## Why it matters here

- PoC-047 found minimal Qwen verbatim-copy ≈ generator-free cosine (inconclusive, +2.1) at k=3. This isolates
  the **retrieval depth** for the answer step: does k=1 (one clause, no distractors) help the 1.5B?
- Hard-cat key-fact is undefined (no typed key_facts, PoC-042) → scored by **span-F1** (018/036 definition).

## Hypothesis

One highly-relevant chunk + one imperative removes both distraction and instruction load; but k=1 also loses
the rank-2/3 gold the extractor sometimes needs.

- **H1:** k=1 extraction hard-mean span-F1 ≥ +3 over the k=3 generator-free extractor (PoC-036 ≈ 20.7 at N=3).
- **H2:** k=1 ≥ k=3 for the Qwen-copy arm too (depth, not prompt, is the lever).

## Method

Fork PoC-047: arms = {generator-free cosine extractor, Qwen bare-extract} × depth {k=1, k=3}, on the 300
hard items, span-F1 (SQuAD overlap vs gold). Retrieval = PoC-016 decomposition (held fixed). Deterministic.

## Decision rule

Adopt k=1 if hard-mean span-F1 ≥ +3 over the k=3 best arm. Reject if k=1 < k=3. Inconclusive between.

## Harness (run-time)

`k1-extract.py` forks `047/retrieve-extract.py` with a `--topk {1,3}` sweep. Reads committed vectors via
`LAB_POC_ROOT`.

---
### Engine provenance
`evo-g2-6` · OP-2 · false-null screen. Overlaps PoC-047 (keep generator-free); isolates retrieval depth for
the answer step. Verdict feeds back to the ledger.
