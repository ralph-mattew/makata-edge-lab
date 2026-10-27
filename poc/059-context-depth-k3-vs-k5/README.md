# PoC 059: Generation context depth k=3 vs k=5 (OP-2)

| | |
|---|---|
| Status | Concluded — host stage (464 typed-fact items; key-fact). |
| Verdict | **Refuted — k=5 does not degrade the 1.5B; it *improves* key-fact.** The source's finding (k=3→k=5: 75%→52% for a small Qwen) does **not** transfer to CUAD: key-fact rises **66.8 → 72.8 (+6.0)** from k=3 to k=5, and answerable refusals *drop* 13.8% → 6.9%. So more retrieved context *helps* here. H1 (k=5 ≥5 pp below k=3) FAIL; H2 (within 2 pp) FAIL — the effect is a clear +6.0 in the opposite direction → **dilution hypothesis refuted.** Practical: for the *generation* path (fact categories), **k=5 > k=3**; and the OP-8 inference "freed RAM → bigger generator not wider context" is **not** supported — wider context earns its keep on this stack. (Hard categories still use the adopted generator-free extractor, unaffected.) See Verdict. |
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

## Harness

`context-depth.py` generates Qwen answers at k∈{3,5} retrieved passages (hybrid 0.9/0.1, committed vectors)
over the 464 typed-fact items and scores key-fact set-overlap (PoC-006 `facts.py`) + answerable refusal.
Deterministic (temp 0). Reads committed vectors via `LAB_POC_ROOT`; Qwen :8091.

## Results

MEASURED on the host (Qwen2.5-1.5B Q4_K_M, temp 0), **464 typed-fact items**, key-fact.

| k (passages) | key-fact | 95% CI | answerable refusal |
|---|---|---|---|
| **k=3** | 66.8 | 63.0–70.5 | 13.8% |
| **k=5** | **72.8** | 68.9–76.6 | 6.9% |
| Δ (k5−k3) | **+6.0** | — | −6.9 |

- **Control:** k=3 key-fact 66.8 reproduces PoC-042/009. MEASURED.
- **H1 (k=5 ≥5 pp below k=3):** FAIL — k=5 is +6.0 *above*. MEASURED.
- **H2 (within 2 pp):** FAIL — the effect is a clear +6.0. MEASURED.
- More context both lifts key-fact and reduces spurious refusals (the extra passages more often contain the
  gold fact, and the model abstains less). MEASURED.

Summary in `results/context-depth.json`.

## Verdict

**Refuted — the "more context hurts the small generator" claim does not hold on CUAD/Qwen2.5-1.5B.** Going
k=3 → k=5 *improves* typed-fact key-fact accuracy by +6.0 pp and nearly halves answerable refusals. The
cited Raspberry-Pi result (75%→52%) does not transfer — plausibly because CUAD gold facts are dispersed and
a 5th passage more often contains the needed date/duration/jurisdiction than it adds confusing distractors,
and because EmbeddingGemma's top-5 are still on-topic. Two consequences: (1) for the **generation path**
(fact categories), prefer **k=5**; (2) the OP-8 corollary "spend freed RAM on a bigger generator, not a
wider context window" is **not supported here** — a wider window pays off. This does not touch the hard
categories, which use the adopted generator-free extractor (PoC-036) independent of generation k.

## Limits

- **Typed-fact items only** (hard cats carry no typed key_facts, cf. PoC-042); the k-effect on hard-category
  *answer quality* is governed by the extractor, not generation depth.
- **k=5 costs more context tokens / latency**; the +6.0 should be weighed against that on-device.
- **Single prompt, temp 0**; did not sweep k>5 (where dilution may eventually appear).

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/059-context-depth-k3-vs-k5
LAB_POC_ROOT=/path/to/lab-clone/poc python3 context-depth.py
```

---
### Engine provenance
`arxiv-2610.33732v1-idea-6` · OP-2 · UNSCREENED. Confirmatory. Verdict **REFUTED** — k=5 improves key-fact +6.0 (dilution claim does not transfer). Feeds back to the ledger.
