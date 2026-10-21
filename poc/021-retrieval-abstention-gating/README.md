# PoC 021: Retrieval-confidence abstention gating for absent clauses (OP-4)

| | |
|---|---|
| Status | Concluded — host stage (1,325 answerable + 438 absent items, full run) |
| Verdict | **Reject the global single-threshold gate — but H1 confirmed: OP-4 is a severe, real problem.** Baseline false-positive surfacing on absent clauses is **75.1%** (≫20%). No single raw-cosine threshold cuts FP by ≥30% without a >3 pt recall loss: the first T meeting H2 (T=0.55 → FP 43%) costs +8.2 recall, triggering the decision rule's reject clause. Raw top-1 cosine doesn't separate absent from answerable (answerable top-1 median 0.596; absent items also match *something*). Per-category FP is highly uneven (Exclusivity 6% vs Change-of-Control 66%), pointing to per-category thresholds or a better confidence signal. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | DeclineCraft: A RAG Abstention Benchmark for Jointly Measuring Combined Retrieval and Parametric Knowledge (http://arxiv.org/abs/2610.28340v1); promoted from the 2026-10-21 ideation-engine scan (subsumes the near-duplicate "abstention/confidence-gating" proposal from the same scan). |
| Registered | 2026-10-21 (this draft, before the first run) |

## Question

Does applying a calibrated abstention signal — analogous to DeclineCraft's Correct Abstention Rate — to our hybrid retrieval stack reduce false-positive clause surfacing rate on category-absent CUAD items by ≥30% without degrading recall@3 on answerable items by more than 2 points?

## Why it matters here

- OP-4 (absent-clause false retrieval) is entirely unmeasured in our stack; the first measurement alone is high-value for Xylo's production use case where falsely surfacing a non-existent exclusivity clause is a legal liability
- DeclineCraft provides both a benchmark design pattern (unanswerable questions with audited parametric exposure) and a single-shot retrieval-confidence signal that our harness can implement without generation — directly applicable to our extractive pipeline

## Hypothesis

DeclineCraft tested abstention in a generative LLM setting; we transfer the abstention signal to the retrieval layer by using a retrieval-confidence threshold (max cosine similarity of top-1 chunk to query) as a surrogate for 'no relevant clause found'. If max-sim < threshold T, we predict 'clause absent' rather than returning chunks. We test whether calibrating T on a held-out CUAD absent-clause set reduces false-positive surfacing without hurting recall@3 on answerable items. No generation required.

- H1: False-positive retrieval rate on CUAD category-absent items is measurably high (>20%) at current settings — establishing the baseline OP-4 measurement
- H2: A calibrated max-sim threshold T reduces false-positive rate by ≥30% on absent items
- H3: Recall@3 on answerable items degrades by ≤2 points at the chosen T
- H4: Hard-category absent items (Exclusivity, Non-Compete) show especially high false-positive rates, explaining part of the OP-1 difficulty

## Method

Reuse PoC-007 harness. Step 1: identify CUAD items where the gold answer is 'not present / not applicable' — these form the absent-clause test set. Step 2: measure current false-positive retrieval rate (top-1 chunk returned with sim > 0.5 for an absent clause). Step 3: sweep threshold T over [0.4, 0.5, 0.6, 0.7]; for each T, measure false-positive rate on absent items and recall@3 on answerable items. Step 4: select T that maximizes F1(abstention accuracy, recall@3 preservation). Report per-category breakdown including hard categories.

- Baseline stack: EmbeddingGemma 300M (via `--embd-gemma-default`, reproduces committed PoC-014 vectors at cosine 1.00000), Hybrid 0.9 semantic + 0.1 BM25 (PoC-013 weight). No generator needed — the gate is a retrieval signal.
- Device: iPhone 15 Pro (6GB). Dataset: CUAD. Absent/answerable split from **PoC-008**'s `items.jsonl` (`answerable` flag: 482 absent / 504 answerable; 364/392 contracts overlap the PoC-014 chunk index, the rest are skipped).
- **Varies:** the abstention threshold T on the top-1 raw semantic cosine (sweep {0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70}). **Held fixed:** EmbeddingGemma retrieval, hybrid 0.9/0.1 ranking, chunk index, the eval set. The gate uses the **raw top-1 semantic cosine** (an absolute, cross-item-comparable value) — *not* the per-set-normalized hybrid score.
- **Measurements:** false-positive rate on absent items (predict "present" when top-1 cosine ≥ T), recall@3 on answerable items (top-3 cover ≥ 50% of gold span, PoC-007 defn), abstention F1, per-category breakdown incl. hard categories. **Repetitions:** deterministic retrieval → single pass; question embeddings computed once.

## Decision rule

If H1 confirmed AND H2 + H3 hold at some T: adopt threshold gating as a production safety feature; if false-positive baseline <10% (OP-4 not a real problem): deprioritize; if recall@3 drops >3 points at any T achieving H2: reject threshold approach

## Expected outcome (engine estimate, not a result)

likely to confirm H1 (high baseline false-positive) and partially meet H2/H3 — adopt with calibration  ·  confidence 0.6  ·  est. effort 1 week

## Harness

`abstain-gate.py` measures both sides on the same EmbeddingGemma space, no generator:

- **Answerable side** — PoC-007's 1,325 items with the committed query vectors + PoC-014 page
  vectors + spans (the validated recall path; no re-embedding, no gold-alignment risk). Gives
  ungated recall@3 and the top-1 raw semantic cosine per item.
- **Absent side** — PoC-008's `answerable=False` items (438 usable after the 364/392 contract
  overlap filter); their questions are embedded fresh via EmbeddingGemma (query prefix). Gives the
  top-1 raw semantic cosine per absent item.

The gate uses the **raw top-1 semantic cosine** (absolute, cross-item comparable), swept over
{0.40…0.70}. FP(absent) = fraction with top-1 ≥ T; gated recall@3 = fraction of answerable with
top-1 ≥ T AND hybrid top-3 covers the gold span.

## Results

MEASURED on the host (EmbeddingGemma via `--embd-gemma-default`), 1,325 answerable + 438 absent
items, single deterministic pass. Ungated recall@3 = 61.8%; **baseline FP on absent (cos ≥ 0.50)
= 75.1%**.

| T | FP on absent | correct abstention (CAR) | gated recall@3 | recall drop | abstention-F1 |
|---|---|---|---|---|---|
| 0.40 | 95.9% | 4.1% | 61.7% | +0.1 | 7.9 |
| 0.45 | 90.4% | 9.6% | 61.2% | +0.6 | 16.7 |
| 0.50 | 75.1% | 24.9% | 59.6% | +2.2 | 35.0 |
| 0.55 | 43.2% | 56.8% | 53.7% | +8.2 | **51.0** |
| 0.60 | 16.0% | 84.0% | 35.2% | +26.6 | 48.8 |
| 0.65 | 3.9% | 96.1% | 12.5% | +49.3 | 42.8 |
| 0.70 | 0.9% | 99.1% | 2.3% | +59.5 | 40.3 |

- **H1 (baseline FP > 20%):** PASS — 75.1%. Absent-clause false surfacing is severe and, until now,
  entirely unmeasured. MEASURED.
- **H2 (a T cuts FP ≥ 30%):** achievable — T ≥ 0.55 cuts FP from 75% to 43% (−43% relative). MEASURED.
- **H3 (recall drop ≤ 2 at that T):** FAIL — at T = 0.55 recall drops +8.2; the only thresholds with
  drop ≤ 2 (T ≤ 0.50) barely reduce FP. No T satisfies H2 and H3 together. MEASURED.
- **H4 (hard categories especially bad):** partly — Change-of-Control absent FP 65.7% and Non-Compete
  30.3% are high, but **Exclusivity is only 6.1%** (its absent items are well-separated). Per-category
  FP spans 0%–91%. MEASURED.

Full sweep + per-category FP in `results/abstention-sweep.json`; summary in `results/comparison.txt`.

## Verdict

**Reject the global single-threshold gate; keep the H1 finding.** The decision rule's reject clause
fires: every threshold that achieves H2 (FP −30%) costs > 3 points of recall (+8.2 at T = 0.55). The
root cause is that the raw top-1 cosine does **not** separate absent from answerable — answerable
items sit at a median top-1 of 0.596 and absent items also retrieve *something* similar (75% clear
0.50), so a single global cut can't split them. **But H1 is a high-value positive result:** this is
the first OP-4 measurement on our stack and it shows absent-clause false surfacing is severe (75%),
which matters directly for Xylo (falsely surfacing a non-existent exclusivity/non-compete clause is a
legal-liability risk). The per-category spread (Exclusivity 6% vs Change-of-Control 66%) points at
the next move: **per-category calibrated thresholds** (ties into the still-inbox per-category-weight
proposal) or a learned confidence signal (margin between top-1 and top-k, cross-encoder score), not a
single global cosine cut.

## Limits

- **Absent side uses PoC-008's question set** (438 of ~482 after the contract-overlap filter); the
  answerable side uses PoC-007 — the two were authored separately, so this compares distributions,
  not paired items.
- **Gate signal is raw top-1 cosine only.** Richer signals (top-1 − top-2 margin, hybrid-score mass,
  a cross-encoder) are untested and are the natural follow-up.
- **Host embeddings.** On-device numbers (an iPhone embedder build) are not measured; the signal is
  model-space-dependent and should be re-checked if the embedder changes (e.g. PoC-022).

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

cd poc/021-retrieval-abstention-gating
python3 abstain-gate.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `synth-idea-3` · technique: problem×method · attacks: OP-4
- Gates (0–10): G1 6.25 · G2 7.0 · G3 7.25 · null-control Δ6.75 (real 7.0 vs null 0.25)
- Tournament: rank 2, elo 1016.0 · priority 📊 MEDIUM (8.121185372005046)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
