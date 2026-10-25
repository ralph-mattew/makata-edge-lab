# PoC 034: Qwen entailment self-check gate for absent clauses (OP-7)

| | |
|---|---|
| Status | Concluded — host stage (101 absent + 300 answerable hard-cat items) |
| Verdict | **Inconclusive by the rule → do not adopt (sharp precision/recall tradeoff).** The two-stage self-check *works* as an abstainer — absent CAR **84.2 → 95.0 (+10.9pp, H1 passes)** — but it wrongly abstains on answerable hard items at **+21.7pp (52.0 → 73.7, H2 fails by ~7×)**. Root cause: the gate conflates "clause absent from the *contract*" with "clause absent from the weakly-retrieved *top-1 chunk*", and hard-category retrieval is poor (Exclusivity recall@3 ~6%), so it over-abstains on real answerables. The abstainer is **retrieval-quality-bound** — safe only where retrieval is already good (fact categories), which is not where we need it. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | DeclineCraft (single-shot vs. iterative retrieval CAR measurement) + authority-framing / over-refusal study (small-LLM legal domain prompt sensitivity); 2026-10-25 ideation-engine scan. Actions the PoC-029/031 forward-pointer (generation-side entailment). |
| Registered | 2026-10-25 (this draft, before the first run) |

## Question

Does appending a lightweight entailment self-check prompt to Qwen2.5-1.5B Q4's generation step — explicitly asking the model whether the top retrieved chunk actually contains the queried clause before committing to an answer — raise Correct Abstention Rate (CAR) on the residual ~14% absent-clause misses by ≥10pp while losing ≤3pp on answerable recall?

## Why it matters here

- OP-7 is the last open absent-clause lever: PoC-026 showed 86.3% CAR is already achieved by the generator alone, but ~14% of absent-clause items still produce hallucinated positives — a post-generation entailment check is the named candidate mechanism (PoC-029) and has never been tested on our stack.
- Parent 2 (DeclineCraft) isolates that retrieval context itself can hurt abstention; Parent 1 (authority-framing) shows Qwen2.5-1.5B is sensitive to prompt-level framing cues — combining these two findings suggests that a carefully framed two-step prompt (retrieve → self-check entailment → answer/decline) could exploit the model's already-strong abstention instinct rather than fighting it, without adding any new model or RAM cost.

## Hypothesis

No source has shown that a self-entailment prompt injected into Qwen2.5-1.5B's generation step (framed as: 'Does the following passage explicitly state [clause type]? Answer YES or NO, then answer the question only if YES') raises CAR on CUAD absent-clause items beyond the generator's current 86.3% baseline. The mechanism blends DeclineCraft's finding (context exposure controls abstention) with the framing-sensitivity finding (Qwen responds to explicit instruction cues) into a two-stage prompt: (1) entailment gate framed as a binary chunk-check, (2) conditional answer generation only if gate fires YES. This specific two-stage prompt design and its net effect on CAR vs. answerable recall on CUAD are entirely unverified.

- H1: CAR on the residual ~14% absent-clause misses rises by ≥10pp vs. the current single-step generation baseline (current: ~86.3% overall CAR; target for residual subset: measure subset CAR before and after).
- H2: Answerable-recall loss is ≤3pp (key-fact accuracy on answerable hard items does not drop more than 3pp — the gate should say YES and pass through for truly answerable items).
- H3: The two-stage prompt adds no extra model or RAM cost — implemented purely as a prompt template change within the existing Qwen2.5-1.5B Q4 + EmbeddingGemma stack.

## Method

Reuse the existing experiment harness and CUAD hard-category eval set. Implement a two-stage prompt: Stage 1 — inject the top-1 retrieved chunk and ask 'Does this passage explicitly contain a [CATEGORY] clause? Answer YES or NO only.' Stage 2 — if YES, proceed with the standard answer prompt; if NO, return a structured abstention. Measure CAR on the subset of absent-clause items the current stack misses (~14% of absent hard items identified in PoC-026), plus key-fact accuracy on answerable hard items. Compare both to the PoC-026 single-step baseline. Run on full hard-category split (Exclusivity, Non-Compete, Change-of-Control).

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the generation step — single-step answer (PoC-026 baseline) vs a two-stage prompt (Stage 1 binary gate "does the top-1 chunk explicitly contain a [CATEGORY] clause? YES/NO"; Stage 2 answer only if YES). **Held fixed:** EmbeddingGemma hybrid retrieval, top-3 context for the answer / top-1 for the gate, Qwen2.5-1.5B Q4, the PoC-008 absent + PoC-007 answerable hard-cat sets. **Measurements:** CAR on absent items; abstention (recall loss) on answerable items; both vs baseline. **Repetitions:** greedy (temp 0) → single pass. No new model (H3 holds by construction).

## Decision rule

Adopt if H1 (CAR gain ≥10pp on residual misses) AND H2 (answerable recall loss ≤3pp) AND H3 (no new model/RAM). Reject if H1 < +5pp on residual misses. Inconclusive otherwise — report directional finding and consider a constrained-decoding variant.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.38  ·  est. effort 1 week

## Harness

`entailment-selfcheck.py` (Qwen :8091 + EmbeddingGemma :8090): per hard-category item, retrieve
hybrid top-3; run the single-step answer prompt (baseline) and the two-stage gate (Stage 1 YES/NO on
the top-1 chunk → Stage 2 only if YES). Abstention = gate says NO or the answer is a refusal (frozen
regex). Absent items (abstaining is correct) → CAR; answerable items (abstaining is wrong) → recall loss.

## Results

MEASURED on the host (Qwen2.5-1.5B Q4, greedy). 101 absent + 300 answerable hard-category items.

| Metric (hard categories) | single-step baseline | + self-check gate | Δ |
|---|---|---|---|
| **CAR on absent** (higher better) | 84.2% | **95.0%** | **+10.9pp** |
| **Abstention on answerable** (= recall loss, lower better) | 52.0% | **73.7%** | **+21.7pp** |

- **H1 (absent CAR +≥10pp):** PASS — +10.9pp. MEASURED.
- **H2 (answerable recall loss ≤3pp):** FAIL badly — +21.7pp (≈7× the budget). MEASURED.
- **H3 (no new model/RAM):** holds — prompt-only, one extra Qwen call. OBSERVED.

Summary in `results/entailment-selfcheck.json`.

## Verdict

**Inconclusive by the decision rule; do not adopt.** The generation-side self-check is a *genuinely
effective abstainer* — it pushes absent-clause CAR from 84% to 95% (+10.9pp), clearing H1 and
confirming the OP-7 forward-pointer from PoC-029/031 that a generation/entailment check (not a cosine
proxy) is the right tool for absent detection. **But it is retrieval-quality-bound and unusable on the
hard categories:** it over-abstains on real answerables by +21.7pp because the Stage-1 gate cannot tell
"the contract has no such clause" from "the clause wasn't in the weakly-retrieved top-1 chunk" — and
hard-category retrieval is exactly where the top-1 chunk is usually wrong (Exclusivity recall@3 ~6%,
PoC-025/030). The baseline already abstains on 52% of answerable hard items for the same reason; the
gate makes it worse.

**Implications:**
- The abstainer itself is sound; the blocker is upstream **retrieval quality** on the hard categories —
  the same wall PoC-022/023/025/027/028/030/033 hit. Any absent-clause gate inherits it.
- It would likely be **safe on the fact categories** (good retrieval) — a scoped use (gate only where
  recall@3 is high) is the sensible follow-up, but that is not the hard-category problem OP-7 targets.
- Net: keep the single-step generator (PoC-026's 86% CAR) for now; the residual ~14% is not cheaply
  recoverable without first fixing hard-category retrieval.

## Limits

- **Gate on the top-1 chunk only** (per the proposal). Gating on the top-3 context would reduce false
  abstentions but also dilute the absent signal; untested, but bounded by the same retrieval ceiling.
- **Hard categories only** — the favourable-retrieval (fact) categories would likely pass H2; not measured.
- **Lexical refusal detection** (frozen regex) for the baseline; a paraphrased decline could be missed,
  which would understate the baseline CAR and *overstate* the gate's gain — the −21.7pp answerable cost
  is the deciding number regardless.

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

cd poc/034-qwen-entailment-selfcheck
python3 entailment-selfcheck.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g2-4` · technique: structured-blend · attacks: OP-7
- Gates (0–10): G1 6.75 · G2 6.25 · G3 6.5 · null-control Δ6.0 (real 6.25 vs null 0.25)
- Tournament: rank 2, elo 999.3 · priority 📊 MEDIUM (9.071928687196106)
- Provenance: idea-evolution-engine (private) scan 2026-10-25. Gate-approved + null-control-screened, NOT yet empirically validated.
