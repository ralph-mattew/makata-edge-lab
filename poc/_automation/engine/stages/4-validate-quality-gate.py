#!/usr/bin/env python3
"""Stage 4: Validate ideas through 3-gate quality process"""
import argparse, json, os
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # put engine/ on sys.path
from pack import load_pack, add_pack_arg
import yaml
from _client import make_client, resolve_model, CostTracker, concurrent_map
from _gates import load_gate_prompts, validate_idea

def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Stage 4: Quality gate validation")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    add_pack_arg(parser)
    args = parser.parse_args()

    config = load_pack(args.pack).config
    client = make_client(config)
    model = resolve_model(config, "gate")
    tracker = CostTracker(model)
    workers = int(config['llm'].get('max_workers', 1))
    prompts = load_gate_prompts()

    print(f"=== Stage 4: Quality Gate Validation ({model}, {workers} worker(s)) ===")

    ideas = [json.loads(line) for line in open(args.input)]

    # Validate ideas concurrently; each idea's 3 gates run sequentially inside.
    def work(idea):
        return validate_idea(client, config, idea, prompts, model, tracker)

    results = concurrent_map(work, ideas, workers)

    approved = [idea for idea, ok, _ in results if ok]
    all_graded = [idea for idea, _, _ in results]
    # Aggregate the per-idea funnel counters — a lopsided funnel (e.g. 36→1)
    # means a gate is likely miscalibrated; gate-stats.json makes it data-driven.
    gate_stats = {f"gate{n}": {"reached": 0, "passed": 0} for n in (1, 2, 3)}
    for _, _, stats in results:
        for n in (1, 2, 3):
            gate_stats[f"gate{n}"]["reached"] += stats[f"gate{n}"]["reached"]
            gate_stats[f"gate{n}"]["passed"] += stats[f"gate{n}"]["passed"]

    out_dir = Path(args.output).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        for idea in approved:
            f.write(json.dumps(idea) + '\n')

    # Every graded idea (approved AND rejected, with gate evidence/red_flags) —
    # the audit trail and the lab's published-rejects material.
    graded_path = out_dir / "graded-all.jsonl"
    with open(graded_path, 'w') as f:
        for idea in all_graded:
            f.write(json.dumps(idea) + '\n')

    # Gate-calibration stats land next to the run's other artifacts.
    stats_path = Path(args.output).parent / "gate-stats.json"
    stats_path.write_text(json.dumps({
        "model": model,
        "ideas_in": len(ideas),
        "approved": len(approved),
        "gates": gate_stats,
    }, indent=2))

    print(f"\n=== Results ===")
    print(f"Ideas validated: {len(ideas)}")
    print(f"Approved: {len(approved)} ({100*len(approved)/len(ideas) if ideas else 0:.1f}%)")
    for n in (1, 2, 3):
        g = gate_stats[f"gate{n}"]
        rate = f"{100*g['passed']//g['reached']}%" if g['reached'] else "—"
        print(f"  Gate {n}: {g['passed']}/{g['reached']} passed ({rate})")
    print(f"Wrote gate stats: {stats_path}")
    print(f"Wrote all graded (incl. rejects): {graded_path}")
    print(f"Usage — {tracker.summary()}")
    return 0

if __name__ == "__main__":
    exit(main())
