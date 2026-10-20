# Ideation: transfer-aware gating + cross-pollination synthesis

Record of why the funnel was approving nothing, what changed, and the measured
before/after. Dated 2026-10-20.

## Symptom

Two consecutive full scans approved **0** ideas. Gate 2 (solution understanding)
passed **0/6** both times. The funnel looked broken.

## Diagnosis (critical check: too-strict filter vs too-shallow ideation — it was BOTH)

Using the lab's own PoC 014 (clause-aware chunking) as a ground-truth probe — a PoC we
had independently judged worth registering — the pipeline *independently proposed the
same idea*, it passed Gate 1 (7.0), then Gate 2 **failed it (4.75)**. Gate 2's reasoning
was factually correct (the StrucChunk source uses BGE-M3 + RRF on GDPR/CrPC, not CUAD,
not EmbeddingGemma, recall@5 not @3). That exposed two coupled faults:

1. **Extraction over-claimed.** It fabricated source-backed specifics (our dataset,
   embedder, metric, a numeric gain) and attributed them as if the source proved them.
2. **Gate 2 structurally penalized transfer.** Its "prediction" criterion required the
   *source* to predict the outcome. But a PoC is a PRE-REGISTERED TRANSFER experiment —
   the source by definition never ran our 6GB/CUAD/EmbeddingGemma stack. So every honest
   transfer hypothesis (the lab's entire thesis) was unfailable-by-construction.

Also: a stale `config.yaml` (`retrieval: 0.7/0.3`, superseded by PoC 013's 0.9/0.1, and a
`completed_pocs` list that stopped at PoC 010) fed those wrong specifics into extraction.

## Changes

- **config.yaml** — retrieval 0.7/0.3 → 0.9/0.1; `completed_pocs` refreshed through PoC 015.
- **idea-extraction.txt (+schema)** — separate `source_establishes` (what the paper
  proved) from `transfer_hypothesis` (the unverified leap we test) from `source_limits`
  (the gap the idea discloses itself); numeric bars stated as OURS, not source claims.
- **gate2-validation.txt (+_gates fields)** — judge mechanism clarity + honest transfer,
  not source pre-confirmation. FAIL reserved for (A) mechanism-absent / not-in-source and
  (B) source-misrepresentation. Still catches the PoC-011 naive-prepend class.
- **Stage 3b synthesis (NEW)** — `knowledge/open-problems.md` + `idea-synthesis.txt`
  (problem×method, method×method, analogical transfer, constraint-driven) +
  `3b-synthesize-ideas.py` derive recombined candidates from the paper batch × the lab's
  open problems. Wired into `run-weekly-scan.sh` between Stage 3 and Stage 4.

## Measured before/after (same 8 relevant papers, 2026-10-20 arXiv scan)

| | Old pipeline | Reframed + synthesis |
|---|---|---|
| Ideas gated | 12 (per-paper only) | 10 (6 reframed + 4 synthesized) |
| Gate 1 pass | 6/12 | 6/10 |
| **Gate 2 pass** | **0/6 (0%)** | **6/6 (100%)** |
| Gate 3 pass | 0/0 | 4/6 |
| **Approved** | **0** | **4 (40%)** |

The clause-chunking idea old-Gate-2 wrongly failed (4.75) now scores Gate 2 **8.5**.
Rejections now happen at the RIGHT gates — Gate 1 (novelty/problem: LIRQuant 4.2,
relevance-worth 4.5) and Gate 3 (ROI: on-device EmbeddingGemma *fine-tuning* 0.0) —
not the structural transfer-penalty.

**2 of the 4 approved are synthesized cross-pollinations** no single paper proposed, both
attacking OP-1 (the hard-category bottleneck):
- *StrucChunk clause-boundary chunking **+ cross-reference resolution*** (problem×method) —
  the untested follow-up flagged by PoC 014.
- *Decomposing hard-category questions into focused sub-questions* (method×method:
  RESIN × query-formulation) — a PoC-015 cousin.

## Calibration (regression guard)

`calibration/cases.jsonl` — added `cal-transfer-strucchunk` (a well-framed transfer PoC
that MUST pass Gate 2). Latest run: 5/6 correct.
- `cal-transfer-strucchunk` → APPROVED ✅ (Gate 2 7.5) — the fix holds.
- `cal-011-contextual` → REJECTED ✅ — the adversarial mechanism-mismatch catch is intact
  (recalibration did not defang Gate 2).
- `cal-010-bm25-dup` → the one miss (APPROVED, expected REJECTED): a known dup scoring
  exactly at the Gate 1 threshold (6.0). Pre-existing LLM variance at temp 0.1, unrelated
  to these changes (Gate 1 / feedback loop untouched) and the OPPOSITE failure mode
  (too-loose on a dup, not too-strict). Watch, don't over-tune.

## Honest limits / watch-items

- Gate 2 at 100% on this batch is not proof it's now toothless — the 6 were genuinely
  source-grounded mechanisms, and `cal-011` confirms the catch still fires. But monitor
  the Gate 2 pass rate across future scans; if it stays ~100%, re-tighten criterion 1
  (mechanism-in-source), not criterion 3 (transfer).
- Two approved ideas overlap PoC 014 (clause chunking, now inconclusive). Once PoC-014's
  outcome is in the shared `outcomes.jsonl`, the Gate 1 feedback loop should dedup the
  boundary-only variant; the cross-reference-resolution variant remains genuinely novel.
- Synthesis can hallucinate a plausible-but-wrong recombination; Gate 2 (mechanism
  grounding) is the backstop, and the source_papers provenance makes it auditable.
