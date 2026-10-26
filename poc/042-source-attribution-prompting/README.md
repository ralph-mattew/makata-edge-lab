# PoC 042: Source-attribution prompting for hard-category generation (OP-2/OP-7)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending — do not fill until the run concludes._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox proposal `2026-10-25-applying-retrievalaugmented-generation-with-explicit-sourceattribution-prompting` (engine idea `oa-W4415044773-idea-9`, technique extraction, attacks OP-2; source: *A Survey on Hallucination in LLMs: Definitions, Detection, and Mitigation*). The **only micro-lab-screened** item in the 2026-10-25 inbox (cuad_hard:CONFIRMED). |
| Registered | 2026-10-26 (this draft, before the first run) |

## Question

Does **source-attribution prompting** — instructing Qwen2.5-1.5B to answer only from the retrieved chunks,
**cite the supporting chunk number(s)**, and say ABSENT if none supports a definitive answer — improve
key-fact accuracy on CUAD vs the current non-attribution baseline (67.9% overall), by **≥ +3 pp overall**
and **≥ +5 pp on ≥ 2 of the 3 hard categories**, with retrieval held fixed (recall@3 unchanged)?

## Why it matters here

- Attribution-anchored prompting forces the model to **ground answers in retrieved text** rather than
  parametric memory, directly attacking context-conflict hallucination; it is complementary to PoC-026
  abstention and requires **no new models or RAM** (prompt-only).
- It is a *different* faithfulness mechanism from the entailment/abstention gates (PoC-026/034/041): those
  decide **whether** to answer; attribution shapes **how** the answer is formed (cite-or-abstain), which
  may improve the *content* of answers that are emitted, not just the abstain/answer split.
- Caution from the ledger: on-device generation tricks with the 1.5B have a poor track record (PoC-011
  generation hurt retrieval; 034 over-abstained; 038 HyDE backfired). Attribution is lighter-touch
  (instruction-only, no extra generation stage), so it is the cheapest remaining generation-side probe —
  worth a clean measurement, with a realistic prior of a small or null effect.

## Hypothesis

A citation-and-abstain instruction raises the floor on hallucinated clause text because the model must
point to a chunk, which is harder to satisfy when fabricating. Untested on CUAD with a 1.5B generator.

- **H1:** overall key-fact accuracy ≥ **+3 pp** over the 67.9% baseline.
- **H2:** hard-category key-fact accuracy ≥ **+5 pp** on **≥ 2** of {Exclusivity, Non-Compete, Change-of-Control}.
- **H3:** recall@3 unchanged (retrieval pipeline untouched) — any accuracy change is purely generation-side.
- **H4 (guard against 034's failure mode):** the ABSENT instruction does **not** inflate false abstentions
  on answerable items by > 3 pp (measured as answerable refusal rate vs the non-attribution baseline).

## Method

Reuse the **PoC-006/009 key-fact harness** (CUAD 1,325 Q&A, typed `key_facts` gold via `facts.py`,
hybrid 0.9/0.1 top-3 retrieval, Qwen2.5-1.5B generation, `summarize.py` key-fact set-overlap scorer).
**Change only the generation prompt** to the attribution variant; retrieval, chunks, models, and the
scorer are byte-identical to the baseline.

- **Attribution prompt:** `"Answer using ONLY the numbered contract sections below. After your answer, cite
  the section number(s) you used, e.g. [S2]. If no section supports a definitive answer, say ABSENT."`
  with the retrieved chunks rendered as `[S1] … [S2] … [S3] …`. The citation tail is stripped before
  key-fact scoring so attribution text does not distort the metric.
- **Baseline arm:** the current non-attribution prompt on identical retrieval (re-measured here; must
  reproduce the committed 67.9% overall / recall@3 61.4 before trusting deltas — control).
- **Varies:** the generation prompt only (attribution vs baseline). **Held fixed:** EmbeddingGemma hybrid
  retrieval, PoC-014 chunks, Qwen sampling (as PoC-006/009), the 1,325-item eval set, the key-fact scorer.
  **Measurements:** overall + per-category key-fact accuracy, recall@3 (sanity), answerable refusal rate
  (H4), citation-well-formedness rate (descriptive). **Repetitions:** deterministic (temp 0) → single pass;
  contract-level bootstrap CI for the key-fact deltas.
- Baseline stack: EmbeddingGemma 300M (`--embd-gemma-default`), Qwen2.5-1.5B Q4_K_M; device iPhone 15 Pro
  (6 GB); CUAD (397 contracts, 1,325 items).

## Decision rule

Written before the first run.

- **Adopt** if **H1 (overall ≥ +3 pp) ∧ H2 (≥ +5 pp on ≥ 2 hard cats) ∧ H4 (answerable refusal ≤ +3 pp)**.
- **Reject** if overall key-fact change **< +1 pp** (attribution does not move the content metric).
- **Inconclusive** otherwise — report per-category deltas and the citation-well-formedness rate.
- Report **per-category** deltas prominently.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.40  ·  est. effort 2-3 days

## Harness (to be implemented at run time)

`attribution.py` wraps the PoC-006/009 generate→score path: renders retrieved chunks as `[S1..S3]`, runs
the baseline and attribution prompts on identical retrieval, strips citation tails, scores key-fact
set-overlap (reusing `facts.py` / `summarize.py` logic), and writes `results/attribution.json` +
`results/comparison.txt` with the H1–H4 read-out. Control: the baseline arm must reproduce 67.9% overall.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/042-source-attribution-prompting
python3 attribution.py              # baseline vs attribution on CUAD 1,325; H1–H4 read-out
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `oa-W4415044773-idea-9` · technique: extraction · attacks: OP-2 · route `IN_FRAME_VALIDATE`.
- Micro-lab screen: **mixed** · sub-labs confirmed 1 [cuad_hard:CONFIRMED] · slice-faithfulness-risk high —
  the only screened item in its inbox batch, hence prioritised over the unscreened entailment/self-reflection
  siblings (held).
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25. SCREENING signal, NOT a validated
  result — the lab runs the formal experiment; the 042 verdict feeds back to the ledger.
