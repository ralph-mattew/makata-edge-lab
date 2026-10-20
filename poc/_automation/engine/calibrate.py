#!/usr/bin/env python3
"""Calibration / regression harness for the quality gates.

Runs a labeled set of historical ideas (calibration/cases.jsonl) through the
SAME gates Stage 4 uses and checks the grader's APPROVED/REJECTED verdict matches
the known-correct label. This turns gate quality into a number you can
regression-test whenever you touch a gate prompt or threshold — the ideation
analog of the Xylo `qa/` golden harness.

  ./calibrate.py                 # run all cases, print scorecard
  ./calibrate.py --json          # machine-readable per-case results
Exit code 2 if any case's outcome disagrees with its label.

Needs ANTHROPIC_API_KEY (the gates call the API). Gate model = llm.models.gate.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml

from _client import make_client, resolve_model, CostTracker, concurrent_map
from _gates import load_gate_prompts, validate_idea
from pack import load_pack, add_pack_arg

HERE = Path(__file__).parent
CAL_KEYS = ("id", "label", "expected_fail_gate", "rationale")  # harness-only fields


def actual_outcome(idea: dict) -> tuple[str, int | None]:
    """Map the gate run's overall_verdict to (APPROVED|REJECTED, fail_gate|None)."""
    verdict = idea.get("overall_verdict", "")
    if verdict == "APPROVED":
        return "APPROVED", None
    if verdict.startswith("REJECTED_GATE"):
        return "REJECTED", int(verdict[-1])
    return "REJECTED", None


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibrate the quality gates against labeled cases.")
    ap.add_argument("--cases", default=None, help="cases JSONL (default: the pack's calibration/cases.jsonl)")
    ap.add_argument("--json", action="store_true", help="emit per-case JSON results")
    add_pack_arg(ap)
    args = ap.parse_args()

    pack = load_pack(args.pack)
    config = pack.config
    if not args.cases:
        args.cases = str(pack.calibration_dir / "cases.jsonl")
    client = make_client(config)
    model = resolve_model(config, "gate")
    tracker = CostTracker(model)
    prompts = load_gate_prompts()
    workers = int(config["llm"].get("max_workers", 1))

    cases = [json.loads(l) for l in open(args.cases) if l.strip()]
    if not args.json:
        print(f"=== Gate calibration ({model}) — {len(cases)} cases ===")

    def run(case):
        idea = {k: v for k, v in case.items() if k not in CAL_KEYS}
        idea, approved, _ = validate_idea(client, config, copy.deepcopy(idea), prompts, model, tracker)
        exp_out = case["label"]
        act_out, act_gate = actual_outcome(idea)
        return {
            "id": case["id"],
            "expected": exp_out,
            "actual": act_out,
            "outcome_match": exp_out == act_out,
            "expected_fail_gate": case.get("expected_fail_gate"),
            "actual_fail_gate": act_gate,
            "gate_match": case.get("expected_fail_gate") == act_gate,
        }

    results = concurrent_map(run, cases, workers)

    passed = sum(1 for r in results if r["outcome_match"])
    if args.json:
        print(json.dumps({"model": model, "passed": passed, "total": len(results),
                          "results": results}, indent=2))
    else:
        print("\n| Case | Expected | Actual | Gate exp/act | Outcome |")
        print("|------|----------|--------|--------------|---------|")
        for r in results:
            mark = "✅" if r["outcome_match"] else "❌"
            gate = "" if r["gate_match"] else " ⚠︎"
            print(f"| {r['id']} | {r['expected']} | {r['actual']} "
                  f"| {r['expected_fail_gate']}/{r['actual_fail_gate']}{gate} | {mark} |")
        print(f"\n{passed}/{len(results)} outcomes correct.  {tracker.summary()}")
        wrong_gate = [r['id'] for r in results if r['outcome_match'] and not r['gate_match']]
        if wrong_gate:
            print(f"Note: right verdict, different gate (soft): {', '.join(wrong_gate)}")

    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
