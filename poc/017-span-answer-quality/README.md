# PoC 017: Span-level answer quality for the non-fact categories (closing the Arm-B gap)

| | |
|---|---|
| Status | Concluded — full corpus (3 hard categories, 300 items) |
| Verdict | **Gap mostly remains; Exclusivity-only positive.** Keyword expansion's big Exclusivity *recall* win (+25) converts to only a small span-F1 answer gain (**2.8→5.9, +3.1** off a tiny base); the hard-category mean is flat (−0.2) and Change-of-Control answers regress (−2.6). Better retrieval alone does **not** fix hard-category *answer* quality — the 1.5B generator is now implicated. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet |
| Source idea | Direct follow-up to [PoC 015](../015-query-formulation). Arm B proved keyword expansion's recall gain *converts* to key-fact accuracy — but only on the 6 categories with a machine-parsable fact. The biggest recall win, **Exclusivity 7%→32%**, is `key_fact=None` and went unmeasured end-to-end. This PoC adds a span-overlap answer metric so the non-fact categories can be scored. |
| Registered | 2026-10-20 (this draft, before the first run) |

## Question

For the **non-fact hard categories** (Exclusivity, Non-Compete, Change Of Control) — which have
no extractable key fact and so could not be scored in PoC 015 Arm B — does keyword expansion's
retrieval gain (PoC 015 Arm A) translate into **better Qwen answers**, measured by how much the
generated answer overlaps the gold answer span (SQuAD-style token F1)?

## Why it matters here

PoC 015 established the hard-category bottleneck is query-vocabulary mismatch and that keyword
expansion lifts recall@3 **+25 on Exclusivity (7%→32%)**. Arm B confirmed such recall gains
convert to answers — but *only* where `facts.py` can extract a date/duration/jurisdiction. The
hard categories are `key_fact=None` (their answers are clause text, not an extractable value), so
the single most important recall win in the whole series is **end-to-end unmeasured**. This PoC
closes that gap with a metric suited to clause-style answers.

## Metric (and its honest limits)

**Span F1** — SQuAD-style token overlap between the Qwen answer and the gold answer span, over
normalized content tokens (lowercased, stopwords removed, de-duplicated):
`precision` = answer-tokens that are in the gold span; `recall` = gold-span tokens that are in
the answer; `F1` = harmonic mean. Reported per category, `raw` vs `keywords`.

This is a **proxy, not ground truth**: clause answers are long, so absolute F1 is low and a short
correct answer scores modest recall. The **delta** (raw→keywords, same prompt + model, only the
retrieved context differs) is the meaningful quantity — a higher answer↔gold-span F1 under
keywords means the better-retrieved context led Qwen to produce more gold-span-aligned content.
Absolute F1 values are **not** claimed as "answer correctness". A secondary **containment**
score (fraction of items where the answer shares ≥25% of the gold span's content tokens) is
reported as a coarser, more interpretable companion.

## Hypotheses

HYPOTHESIS until measured. Baseline is `raw` on the same items.

1. **H1 (conversion on the hard categories).** Keyword expansion raises mean span-F1 across the
   three hard categories by **≥2 points** (absolute F1 is low; a few points is a real shift at
   this scale). Reported with a contract-level bootstrap CI.
2. **H2 (Exclusivity specifically).** Exclusivity — the +25-recall category — shows a positive
   span-F1 delta, i.e. the recall win is **not** purely cosmetic for the category that mattered most.
3. **H3 (no collateral harm).** Change Of Control, where Arm A keywords did **not** help recall
   (+0), does not regress in span-F1 by >2 points.

Descriptive: per-category F1 precision/recall split; containment rate; qualitative examples where
keyword retrieval changed the answer.

## Method

**Host.** MacBook Pro (Mac16,8), M4 Pro, 24 GB, macOS 26.5.1, AC power (as PoC 015).

**Held fixed:** chunks = PoC 014 page; chunk embeddings = PoC 014 `emb-page`; hybrid 0.9/0.1,
top-3; Qwen2.5-1.5B Q4 over the retrieved top-3 with PoC 015's answer prompt. Reuses the PoC 015
`keyfact.py` retrieval + generation path; only the scorer changes (span-F1 instead of `facts.py`).

**Items.** PoC 007 answerable items in the three hard categories (≈300). Gold answer = the gold
span text (`gold_words`).

**Conditions.** `raw` (verbatim CUAD question) vs `keywords` (PoC 015's per-category keyword
query). Both retrieve top-3, same prompt, same model — only the query differs.

**Measurements.** Span-F1 (precision/recall/F1) per category + mean; containment rate; 95% CIs via
contract-level bootstrap (seed 0).

## Decision rule

Written before the first run.

- **Confirm conversion (close the gap)** if H1 (mean hard-category F1 +≥2) **and** H2
  (Exclusivity delta positive) hold → keyword expansion's Exclusivity recall win is real
  end-to-end, and PoC 015's adopt recommendation stands for the hard categories too.
- **Gap remains open / cosmetic** if the hard-category F1 delta is ≤0 → retrieving the right
  clause did **not** produce better answers (recall was cosmetic for these categories); record as
  a limit on the PoC-015 adoption.
- **Inconclusive** for a positive but <2-point, CI-overlapping delta.
- Report per-category deltas and the metric's proxy caveat prominently either way.

## Results

Full corpus: 3 hard categories, 300 items, Qwen2.5-1.5B over retrieved top-3, span-F1 vs gold
span. Raw in `results/span-quality.json`, `comparison.txt`.

**Span-F1 (MEASURED; absolute values are a low proxy — interpret the delta).**

| Category | raw | keywords | Δ | (Arm A recall Δ) |
|---|---|---|---|---|
| **Exclusivity** | 2.8 | 5.9 | **+3.1** | +25 |
| Non-Compete | 18.3 | 17.3 | −1.0 | +7 |
| Change Of Control | 27.8 | 25.3 | −2.6 | +0 |
| **hard mean** | 16.3 (CI 13.3–19.3) | 16.1 (CI 13.1–19.3) | **−0.2** | — |

**Observations.**
- **OBSERVED (H2 passes, narrowly):** on **Exclusivity** — the category whose recall jumped
  +25 — span-F1 roughly **doubled (2.8→5.9)**. So the recall win is **not purely cosmetic** for
  the category that mattered most; better-retrieved clauses did shift Qwen's answers toward the
  gold span. But it is off a *tiny* base, and the overall CIs (13–19) are wide — suggestive, not
  strong.
- **OBSERVED (H1 fails):** the hard-category **mean is flat (−0.2)**. Keyword expansion slightly
  *hurt* Non-Compete (−1.0) and **Change Of Control (−2.6)** answer quality — consistent with Arm
  A, where keywords did not help their recall (CoC +0). H3 fails (CoC regresses >2).
- **INFERRED (the real close):** retrieving the right clause is **necessary but not sufficient**
  for hard-category answer quality. Even with better context, Qwen2.5-1.5B produces little
  gold-aligned text for these long, reasoning-heavy clauses (absolute F1 stays 3–28). The
  bottleneck for *answers* (as opposed to *retrieval*) on hard clause categories is now the
  **on-device generator**, not the query.

## Verdict

**Gap mostly remains; keyword expansion's Exclusivity win is real-but-small end-to-end.**

Against the decision rule:
- **H1 (hard-mean +≥2): NO** (−0.2).
- **H2 (Exclusivity positive): PASS** (+3.1 — the recall win converts, modestly).
- **H3 (CoC no regress >2): NO** (−2.6).

So: PoC 015's adopt recommendation for keyword expansion stands **as a retrieval win and for the
fact-bearing categories** (Arm B), and it gives a small genuine answer gain on Exclusivity — but
it does **not** improve, and can slightly harm, *answer quality* on the other hard clause
categories. The honest close to the hard-category arc: **the query lever is largely spent;
further gains on hard-category answers require generator-side work** (a stronger/better-prompted
on-device model, or extractive post-processing), not more query reformulation. Recommend scoping
keyword expansion to the categories where it helps (retrieval broadly; Exclusivity answers) and
opening a generator-focused thread for the rest.

## Deviations

- **2026-10-20 (the run):** Ran the 3 hard categories (300 items), `raw` vs `keywords`, via the
  PoC 015 retrieval + Qwen path with span-F1 scoring (`span_quality.py`). Answer `n_predict`
  raised to 160 (clause answers are longer than the fact answers in Arm B). Confirmed the metric's
  proxy nature: absolute F1 is low; only the delta is interpreted.

## Limits

1. **Span-F1 is a proxy** for clause-answer quality, not ground truth; only the raw→keywords
   *delta* is interpreted (see Metric). A human-judged or LLM-judge answer score is the rigorous
   follow-up.
2. **Three hard categories only** — the ones Arm B could not score; not the full non-fact set.
3. **Qwen2.5-1.5B Q4 only**; single prompt; **top-3**; **English**; **answerable items only** —
   held fixed to isolate the query transform.
4. Part of the PoC-015 recall gain is lexical (BM25); this PoC inherits that and does not ablate it.
5. Builds directly on PoC 015 (same retrieval + generation); supersedes its "span-level metric"
   follow-up note.

## Reproduce

Requirements: Apple-silicon Mac, llama.cpp; PoC 006/007/014/015 artifacts present.

```bash
cd poc/017-span-answer-quality
llama-server -m ../006-doc-qa-fm-gemma-qwen/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
  -c 4096 -ngl 99 --port 8091 --log-disable &
python3 span_quality.py --conds raw keywords     # retrieve top-3, Qwen answer, span-F1 vs gold
python3 compare.py                                # per-category F1 deltas + CIs
```

## Replications

| Date | Device | Authors | Outcome |
|---|---|---|---|
| 2026-10-20 | Mac16,8 M4 Pro | Ralph Mattew Palomaria | Gap mostly remains; Exclusivity +3.1 span-F1 (2.8→5.9), hard-mean flat (−0.2), CoC −2.6 → generator now the limit |
