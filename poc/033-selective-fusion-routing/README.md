# PoC 033: Per-category selective fusion routing (dense-only for hard categories) (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD) |
| Verdict | **Reject.** Routing the hard categories to dense-only does **not** lift each by +5pp; the per-category fusion effect is real but **heterogeneous and self-cancelling**: dropping BM25 *helps* Non-Compete (+3.0) but *hurts* Change-of-Control (−5.0) and does nothing for Exclusivity (+0.0). A blanket dense-only-for-hard-cats rule therefore *lowers* hard-mean (34.7→34.0) and overall (−0.2); even an oracle per-category best-of{hybrid,dense} nets only +0.2 overall. 2/3 hard cats gain <+3pp → reject by the decision rule. Keep the 0.9/0.1 hybrid everywhere (confirms PoC-032/013). See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | The Fusion Tax: A Diagnostic Analysis of When Hybrid Retrieval Hurts (http://arxiv.org/abs/2610.30612v1); 2026-10-23 ideation-engine DIVERGENT scan. Per-category follow-up to PoC-032. |
| Registered | 2026-10-25 (this draft, before the first run) |

## Question

Does selectively disabling hybrid fusion (falling back to dense-only or sparse-only) for Exclusivity, Non-Compete, and Change-of-Control queries — as diagnosed by query-level fusion cost analysis — improve per-category recall@3 by ≥+5pp on those hard categories?

## Why it matters here

- PoC-013 showed hard categories are invariant to global weight tuning; the Fusion Tax paper shows fusion can *hurt* individual queries even when it helps in aggregate — the hard categories may be the ones paying the tax
- A per-query fusion-disable gate adds zero new model parameters and is trivially implementable on-device at 6GB

## Hypothesis

Neither the Fusion Tax paper nor our PoC-013 tested a per-category oracle that disables fusion for specific legal clause types. We hypothesize that Exclusivity/Non-Compete/Change-of-Control queries are systematically among the fusion-harmed subset — possibly because their terms are rare/jargon (BM25 produces noisy matches) or densely semantic — and that routing these queries to dense-only retrieval recovers ≥+5pp recall@3 on those categories. This recombination is unverified on CUAD.

- H1: Dense-only retrieval (weight=1.0/0.0) on hard-category questions improves Exclusivity recall@3 from ~11% by ≥+5pp
- H2: Dense-only on hard categories does not degrade overall recall@3 by more than 1pp (since hard categories are small)
- H3: The intervention requires no new model, only a category-label routing switch derivable from question text

## Method

Reuse PoC-013/007 harness. For each CUAD question, assign category label (already in dataset). For the three hard categories (Exclusivity, Non-Compete, Change-of-Control), run retrieval with weight=1.0 dense / 0.0 BM25; for all others keep 0.9/0.1. Compare per-category recall@3 and overall recall@3 vs the adopted 0.9/0.1 baseline. No model training required.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the retrieval scorer *per category* — dense-only (1.0/0.0) for the hard categories vs the 0.9/0.1 hybrid elsewhere (plus dense/sparse/hybrid per-category comparison and an oracle router). **Held fixed:** EmbeddingGemma vectors, PoC-014 chunk index, top-3, the eval set. **Measurements:** per-hard-category recall@3 under each scorer, routed-policy overall recall@3, oracle per-category best-of. **Repetitions:** deterministic → single pass.

## Decision rule

If Exclusivity/Non-Compete/Change-of-Control each improve ≥+5pp recall@3 AND overall recall@3 does not fall >1pp: adopt routing. If hard-category gains <+3pp on any two of three: reject. Otherwise: inconclusive.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.38  ·  est. effort 2-3 days

## Harness

`selective-fusion.py` (committed vectors; no model/server): per item, compute recall@3 under dense-only,
sparse-only (BM25), and hybrid 0.9/0.1; then evaluate the routed policy (dense for hard cats, hybrid
elsewhere) and an oracle per-category best-of{hybrid,dense}.

## Results

MEASURED on the host, full CUAD (1,316 items), recall@3.

| Hard category | hybrid 0.9/0.1 | dense-only | sparse-only | dense − hybrid |
|---|---|---|---|---|
| Exclusivity | 6.0 | 6.0 | 1.0 | +0.0 |
| Non-Compete | 33.0 | 36.0 | 8.0 | **+3.0** |
| Change Of Control | 65.0 | 60.0 | 47.0 | **−5.0** |

| Policy | overall recall@3 |
|---|---|
| hybrid everywhere (baseline) | 62.6 |
| routed: dense-only @ hard cats | 62.4 (**−0.2**) |
| oracle per-category best-of{hybrid,dense} | 62.8 (+0.2) |

- **H1 (each hard cat +≥5pp from dense-only):** FAIL — Exclusivity +0, Non-Compete +3, Change-of-Control
  **−5**. MEASURED.
- **H2 (overall drop ≤1pp):** holds (−0.2), but moot. MEASURED.
- **Decision rule** (reject if <+3pp on any two of three): **2/3 fail** (Exclusivity, Change-of-Control).
  MEASURED.

Figures in `results/selective-fusion.json`.

## Verdict

**Reject.** The "fusion tax" *is* real per-category — but it does not point one way. BM25 **taxes
Non-Compete** (dropping it gains +3) yet **genuinely helps Change-of-Control** (dropping it loses 5) and
is neutral on Exclusivity. So a blanket "dense-only for hard categories" rule nets a **loss**
(hard-mean 34.7→34.0; overall −0.2), and even an oracle that picks the better scorer per category gains
only +0.2 overall — not worth a routing mechanism. **Keep the 0.9/0.1 hybrid everywhere**, confirming
PoC-032 (BM25 earns its keep in aggregate) and PoC-013 (0.9/0.1 is the operating point) a third time.

This closes the hybrid-fusion line of inquiry on CUAD from every angle tried: global weight (013),
global drop (032), and per-category routing (033). The Non-Compete signal (BM25 adds noise there) is
real but too small (+3, one category) to productionise, and is dominated by the larger answer-step and
decomposition-pool levers (PoC-018/030).

## Limits

- **recall@3 only**; a +3 Non-Compete retrieval gain would likely not survive to answer quality (cf.
  PoC-017's weak recall→answer conversion on hard categories).
- **Scorers = dense / BM25 / 0.9-0.1 hybrid**; a *learned* per-query fusion gate (predict the tax) is a
  different, heavier idea — but the oracle upper bound (+0.2 overall) caps its value.
- **Fixed chunking** (PoC-014 page); BM25's per-category behaviour could shift under other chunkings.

## Reproduce

```bash
cd poc/033-selective-fusion-routing
python3 selective-fusion.py        # committed vectors; no model/server
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `synth-idea-1` · technique: problem×method · attacks: OP-1
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.65 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **mixed** · sub-labs confirmed 1 [cuad_hard:POINT_WINS_ONLY; cuad_hard:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-23. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
