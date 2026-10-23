# PoC (proposed): Does measuring the per-query sparse-dense overlap on CUAD reveal that …

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

> ⚠️ **UNSCREENED (non-faithful screen) — routed to reality.** The micro-lab could not fairly test this idea: the available substrate was at ceiling (baselines [0.4639]) or high slice-faithfulness risk, so its 'null' is a FALSE null, not evidence the idea fails. It targets a harder slice than the screen can measure (e.g. hard-category recall) — the lab's real experiment is the judge. Carries only the gate signal.


| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | The Fusion Tax: A Diagnostic Analysis of When Hybrid Retrieval Hurts (http://arxiv.org/abs/2610.30612v1) |
| Registered | not yet — proposed 2026-10-23 |

## Question

Does measuring the per-query sparse-dense overlap on CUAD reveal that BM25 provides near-zero marginal coverage, justifying dropping it entirely and freeing compute for a denser index or larger LLM context?

## Why it matters here

- If BM25 contributes to fewer than 10% of retrievals on CUAD (low sparse-dense balance), the 0.1 BM25 weight is a compute and latency cost with no recall benefit — removing it frees CPU time and pipeline complexity
- Eliminating BM25 from the hybrid pipeline could allow longer query processing or a larger retrieved context within the same 6GB RAM budget
- The paper's diagnostic framework gives a principled, data-driven rationale for the 'do not fuse' decision rather than an arbitrary ablation

## Hypothesis

The paper's sparse-dense balance diagnostic was developed on BEIR; we apply the same diagnostic to CUAD with EmbeddingGemma + BM25 to measure whether BM25 provides meaningful exclusive coverage, and use the result to decide whether our 0.9/0.1 hybrid is justified or whether dense-only would match or exceed it — unverified for legal contract corpora.

- H1: BM25 provides exclusive top-3 coverage (a relevant chunk in BM25 top-3 but not dense top-3) on fewer than 15% of CUAD queries, indicating low sparse-dense balance
- H2: Dense-only (1.0/0.0) retrieval achieves recall@3 within 1pp of the 0.9/0.1 hybrid (≥60.4%), confirming the fusion tax outweighs fusion benefit on CUAD
- H3: If H1 and H2 hold, latency of the retrieval step decreases by ≥20% by eliminating BM25 scoring

## Method

Reuse PoC-007/013 harness. (1) For each of the 1,325 queries, record BM25 top-3 and dense top-3 chunk sets; compute the fraction where a gold chunk appears exclusively in BM25 top-3 (sparse-only coverage). (2) Run dense-only retrieval (weight 1.0/0.0) and measure recall@3 vs 0.9/0.1 baseline. (3) Time both pipelines on iPhone 15 Pro for latency comparison. All uses existing infrastructure, no new models.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT dense-only (drop BM25) if H1 holds (sparse-exclusive coverage <15%) AND H2 holds (dense-only recall@3 ≥60.4%) AND H3 holds (≥20% latency reduction); REJECT if H2 fails (dense-only recall@3 <60.4%); INCONCLUSIVE if H1 holds but H2 is borderline (60.4%–61.4%)

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.4  ·  est. effort 1-2 days

## Results

Link raw files in `results/` once run. Tag every number MEASURED / OBSERVED / INFERRED.

## Verdict

Adopt / reject / inconclusive, against the decision rule.

## Limits

What this does not show.

## Reproduce

Commands from a clean checkout.

---

### Engine provenance (how this idea was generated)

- Engine idea id: `arxiv-2610.30612v1-idea-9` · technique: extraction · attacks: OP-3
- Disposition: route `IN_FRAME_VALIDATE` · pathway-reach 0.55 · in-frame True
- **Micro-lab screen** (self-lab generate→sandbox→confirm vs the real retrieval benchmark): overall **null** · sub-labs confirmed 1 [cuad_hard:CONFIRMED] · compose-retest True · slice-faithfulness-risk high
- Provenance: idea-evolution-engine (private) DIVERGENT scan 2026-10-23. This is a SCREENING signal (a sub-mechanism showed promise on a benchmark slice), NOT a gate score and NOT a validated result — the lab runs the formal experiment.
