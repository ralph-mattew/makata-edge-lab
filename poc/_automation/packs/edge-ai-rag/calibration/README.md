# Gate calibration harness

A labeled regression test for the Stage 4 quality gates — the ideation analog of
the Xylo `qa/` golden harness. It runs known-verdict ideas through the *same*
gates production uses (`_gates.py`) and checks the grader's APPROVED/REJECTED
outcome matches the label, so gate quality is a number you can watch when you
change a gate prompt or a `quality_gate.*_min_score` threshold.

## Run

```bash
export ANTHROPIC_API_KEY=...          # gates call the API (gate model = llm.models.gate)
./calibrate.py                         # scorecard; exit code 2 if any outcome disagrees
./calibrate.py --json                  # machine-readable
```

## Cases (`cases.jsonl`)

Each line is an idea record plus harness-only fields: `id`, `label`
(APPROVED/REJECTED), `expected_fail_gate` (1/2/3 or null), `rationale`. Grounded
in real lab history:

| Case | Label | Why |
|---|---|---|
| `cal-int8-embed` | APPROVED | Novel, clear memory/quality tradeoff, source-supported mechanism, cheap — passes all 3 gates. |
| `cal-010-bm25-dup` | REJECTED | Already answered by PoC 010 (in `completed_pocs`); re-running a concluded experiment should be refused. |
| `cal-011-contextual` | REJECTED @ G2 | Idea's mechanism (static prepend) ≠ source's (model-generated per-chunk context) — the pre-registration concern on PoC 011 (registered, not yet run). |
| `cal-013-maxweight-dup` | REJECTED @ G1 | Duplicate of concluded PoC 013, which swept 0.1–0.9 and adopted 0.9 (+6.3 recall); a plain re-sweep is already answered. |
| `cal-voice-junk` | REJECTED @ G1 | Untestable, no baseline, no threshold. |

## Current baseline

**5/5 outcomes correct** on `claude-sonnet-4-6` at thresholds 6.0/6.0/6.0.

`expected_fail_gate` is a **soft** signal (reported, not gated): a right verdict
reached at a different gate still counts — e.g. the duplicate case can be caught
at Gate 1 (already-concluded) or Gate 2 (settled mechanism) run-to-run.

## Notes / findings this harness surfaced

- The gates **trusted the model's self-declared verdict**, which could contradict
  its own score (FAIL at 6.8). Now the pipeline derives the verdict from
  `overall_score` vs the config threshold (`_gates._apply_threshold`), and the
  `quality_gate.*_min_score` knobs are actually enforced.
- The first adversarial prompt draft **under-scored well-grounded ideas**; the
  prompts now explicitly say skepticism targets hand-waving, not rigor.
- Add cases over time (especially real rejected/inconclusive PoCs). Keep the set
  small and authentic; don't overfit prompts to it.
