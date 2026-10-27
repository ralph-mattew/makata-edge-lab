# PoC 054: Lightweight answer-grounding post-check for absent clauses (OP-7)

| | |
|---|---|
| Status | Concluded — host stage (101 absent + 300 answerable hard items; CAR τ-sweep). |
| Verdict | **Reject — the answer-grounding overlap gate is dominated, exactly like the rest of the gate family.** Thresholding the generated answer's content-token overlap with the top chunk traces the same dominated frontier as PoC-041/043: the **minimum answerable-recall loss to reach +5 pp CAR is 10.0 pp**, and the **max CAR gain at ≤3 pp loss is 0.0** (best feasible point = no gate). H1∧H2 unreachable → **REJECT.** This is the **sixth** confirmation (029 cosine · 031 · 034 binary · 041 calibrated · 043 quote-grounded · 054 answer-overlap) that no post-hoc confidence/grounding gate can separate absent from answerable-but-poorly-retrieved on this stack — the binding constraint is upstream retrieval, not a gate. See Verdict. |
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

## Harness

`grounding-check.py` forks PoC-041/043: base Qwen answer on the hybrid top-3; gate = content-token-overlap
fraction between the answer and the top-1 chunk; abstain iff base refusal OR overlap < τ. τ-swept 0→1;
curve of CAR-gain vs answerable-recall-loss; best feasible point. Absent = PoC-008 hard `answerable=False`
(101), answerable = PoC-007 hard (300). Reads committed vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (EmbeddingGemma + Qwen2.5-1.5B Q4_K_M, temp 0), 101 absent + 300 answerable hard items.

- Baseline absent CAR **84.2%**, answerable refusal **52.0%** (matches 034/041/043).
- **Minimum answerable-recall loss to reach +5 pp CAR: 10.0 pp.**
- **Max CAR gain at ≤3 pp loss: 0.0** (best feasible operating point = no gate).
- **H1 ∧ H2 unreachable** (no τ with +5 CAR at ≤3 pp loss; none even at ≤5 pp) → **REJECT**. MEASURED.

Full curve in `results/grounding-check.json`.

## Verdict

**Reject.** Checking the *generated answer's* overlap with the retrieved chunk is just another point on the
same dominated frontier as the entailment gates — absent-clause items and answerable-but-poorly-retrieved
items are not separable by any post-hoc signal on this stack, whether that signal is retrieval cosine (029),
an entailment proxy (031), a binary YES/NO (034), a calibrated P(YES) (041), a grounded quote (043), or
answer↔chunk overlap (054). The reason is unchanged: when hard-category retrieval misses, the generator sees
the wrong chunk and produces a low-overlap answer *for an answerable item too*, so the gate abstains on
genuine answers at the same rate it catches hallucinations.

Six rejections now close this avenue conclusively. The residual ~14% absent-clause hallucinations (PoC-026)
are not addressable by a confidence/grounding gate; the leverage is upstream retrieval recall — and that is
exactly what the newly-adopted PoC-053 (clause-term binding, recall@3 54.0) and PoC-045 (GreenLeaf) deliver.
Better retrieval, not a better gate, is the path.

## Limits

- **Top-1 chunk overlap, content-token fraction.** Other overlap definitions (top-3 union, char n-gram) sit
  on the same frontier given the six-way convergence.
- Hard categories only; absent = PoC-008 (101), answerable = PoC-007 (300).

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/054-answer-grounding-check
LAB_POC_ROOT=/path/to/lab-clone/poc python3 grounding-check.py
```

---
### Engine provenance
`oa-W4400064731-idea-2` · OP-7 · UNSCREENED. Same gate family as 029/031/034/041/043 (all rejected);
tests the answer-overlap variant. Verdict **REJECT** — dominated frontier (6th gate-family rejection: 029/031/034/041/043/054). Feeds back to the ledger.
