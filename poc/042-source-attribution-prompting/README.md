# PoC 042: Source-attribution prompting for hard-category generation (OP-2/OP-7)

| | |
|---|---|
| Status | Concluded — host stage (464 answerable typed-fact items, baseline vs attribution). |
| Verdict | **Reject — source-attribution prompting *hurts* the 1.5B generator.** On identical retrieval, the citation-and-ABSENT instruction **drops** overall key-fact accuracy **66.8% → 59.5% (−7.3 pp)** and **inflates answerable refusals 14.7% → 23.3% (+8.6 pp)** — the same spurious-ABSTENTION failure mode as PoC-034. The model emits a well-formed citation only **56.5%** of the time, and every fact category is flat-to-worse (Notice-Period −24.2, Expiration −6.6, Governing-Law −6.4). H1 FAIL (−7.3 ≪ +3), H4 FAIL (+8.6 > 3); by the decision rule (overall change < +1 pp) → **REJECT.** The proposal's H2 (hard-category key-fact) is **N/A**: the hard categories carry *no* typed key_facts (clause-presence, not typed-fact extraction) — a mismatch in the proposal (see Deviations). Baseline 66.8% reproduces PoC-009's 67.9% (control ✓). Confirms the ledger lesson: generation-side prompting burdens overload the 1.5B (cf. 011/034/038/040). See Verdict. |
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

## Harness

`attribution.py` retrieves top-3 via hybrid 0.9/0.1 over the committed PoC-014 chunks (identical to
PoC-034/040/041), generates the baseline and attribution prompts on that identical retrieval, strips the
`[Sn]` citation tail before scoring, and scores key-fact via **PoC-006 `facts.py` typed-fact set-overlap**
(imported verbatim). Scope = the **464 answerable typed-fact items** (the categories that carry key_facts).
Writes `results/attribution.json` + `results/comparison.txt`; per-item answers in `results/raw/`. Reads
gitignored vectors via `LAB_POC_ROOT`. Control: baseline must reproduce PoC-009's ~67.9%.

## Results

MEASURED on the host (Qwen2.5-1.5B-Instruct Q4_K_M, temperature 0), **464 answerable typed-fact items**,
deterministic single pass; contract-level bootstrap CI (10k, seed 0). Citation tail stripped before scoring.

| Arm | overall key-fact | 95% CI | answerable refusal | citation rate |
|---|---|---|---|---|
| baseline (no attribution) | **66.8%** | 63.0–70.5 | 14.7% | — |
| attribution (cite + ABSENT) | **59.5%** | 55.3–63.7 | 23.3% | 56.5% |

Per fact-category key-fact (baseline → attribution):

| Category | base | attr | Δ |
|---|---|---|---|
| Notice Period To Terminate Renewal | 68.4 | 44.2 | **−24.2** |
| Expiration Date | 62.3 | 55.7 | −6.6 |
| Governing Law | 94.6 | 88.2 | −6.4 |
| Renewal Term | 84.6 | 82.4 | −2.2 |
| Agreement Date | 29.8 | 29.8 | +0.0 |
| Warranty Duration | 42.5 | 45.0 | +2.5 |

- **Control:** baseline 66.8% (CI 63.0–70.5) reproduces PoC-009's committed 67.9% within CI. MEASURED.
- **H1 (overall key-fact ≥ +3 pp):** **FAIL** — **−7.3 pp**. MEASURED.
- **H2 (hard-cat key-fact ≥ +5 pp on ≥2):** **N/A** — the hard categories carry no typed key_facts, so
  hard-cat key-fact is undefined (see Deviations). Of the *fact* categories, **0** improved ≥ +5 pp.
- **H3 (recall@3 unchanged):** holds by construction — retrieval is byte-identical across arms. OBSERVED.
- **H4 (answerable refusal ≤ +3 pp):** **FAIL** — **+8.6 pp** (14.7 → 23.3): the ABSENT instruction
  triggers spurious abstentions on genuinely answerable items. MEASURED.
- **Citation compliance:** the 1.5B emits a well-formed `[Sn]` citation only **56.5%** of the time —
  nearly half the answers don't follow the attribution instruction at all. MEASURED.

Per-item answers in `results/raw/{base,attr}-answers.jsonl`; summary in `results/attribution.json`.

## Verdict

**Reject.** Source-attribution prompting makes the 1.5B generator *worse*, not better. Overlaying a
citation-and-ABSENT instruction on the generation step drops key-fact accuracy by 7.3 pp and inflates
answerable false-abstentions by 8.6 pp, with no category improving. Two mechanisms compound: (1) the extra
instruction-following load (answer **and** cite **and** self-assess absence) degrades the primary
extraction task on a model that already follows instructions unreliably — it produces a valid citation
only 56.5% of the time; (2) the explicit ABSENT escape hatch is over-used on answerable items, the same
over-abstention that sank PoC-034's entailment gate.

This is the fourth consecutive confirmation of the ledger's consolidated lesson that **generation-side
interventions degrade the 1.5B** (PoC-011 generated context hurt retrieval; 034 self-check over-abstained;
038 HyDE backfired; 040 showed the generator is not the hard-category lever) — now extended to inference
prompting. The practical guidance stands: keep the generation prompt minimal; faithfulness/abstention
leverage is not in richer prompts for this model class.

## Deviations

- **H2 is N/A — proposal metric mismatch (a triage finding).** The proposal asked for a *hard-category*
  key-fact improvement, but the hard categories (Exclusivity / Non-Compete / Change-of-Control) are
  **clause-presence** categories and carry **zero** typed `key_facts` in the CUAD/PoC-006 schema — typed
  facts exist only for 6 fact categories (Renewal Term, Expiration Date, Governing Law, Notice Period,
  Agreement Date, Warranty Duration). Key-fact accuracy is therefore undefined for the hard categories, so
  the mechanism was evaluated where its metric is defined (the 464 typed-fact items), and H2 is reported
  N/A rather than forced onto an inapplicable metric.
- **Scope = 464 typed-fact answerable items** (not the full 1,325): key-fact accuracy only applies to items
  with typed-fact gold. Absent-item CAR is covered by PoC-026/034/041 and not re-run here.
- **HTTP retrieval + generation** (committed PoC-014 vectors, hybrid 0.9/0.1), not PoC-009's Swift GGUFQA
  harness; the baseline reproduces 009's 67.9% within CI, so the delta is trustworthy.

## Limits

- **Key-fact proxy** (typed date/duration/jurisdiction set-overlap), not a full answer-correctness judge.
- **One attribution-prompt wording.** A different phrasing might cite more reliably, but the −7.3 pp key-fact
  drop and 56.5% citation compliance suggest the burden, not the wording, is the binding constraint.
- **Host stage, temperature 0, single pass.** Device latency not measured (prompt-only, no extra model).

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/042-source-attribution-prompting
python3 attribution.py              # baseline vs attribution on the 464 typed-fact items; H1/H4 read-out
# from a detached worktree:  LAB_POC_ROOT=/path/to/lab-clone/poc python3 attribution.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `oa-W4415044773-idea-9` · technique: extraction · attacks: OP-2 · route `IN_FRAME_VALIDATE`.
- Micro-lab screen: **mixed** · sub-labs confirmed 1 [cuad_hard:CONFIRMED] · slice-faithfulness-risk high —
  the only screened item in its inbox batch, hence prioritised over the unscreened entailment/self-reflection
  siblings (held).
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-25 (cuad_hard:CONFIRMED screen). The
  lab ran the formal experiment; verdict **REJECT** (attribution prompting degrades the 1.5B: key-fact
  −7.3 pp, refusals +8.6 pp) feeds back to the ledger — note the screen did not predict this.
