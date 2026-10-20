#!/usr/bin/env python3
"""Stage 4: Validate ideas through 3-gate quality process"""
import argparse, json, os
from pathlib import Path
import yaml
import anthropic
from _client import (make_client, resolve_model, CostTracker,
                     load_split_prompt, call_json, concurrent_map)

def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)

def evaluate_gate(client, config, idea, gate_num, templates, model, tracker):
    """Evaluate a single gate. `templates` is a (system, user) pair."""
    completed_pocs_text = '\n'.join(f"- {poc}" for poc in config['system_context']['completed_pocs'])

    if gate_num == 1:
        fields = dict(
            question=idea['question'],
            why_matters='\n'.join(f"- {item}" for item in idea['why_matters']),
            hypotheses='\n'.join(f"- {h}" for h in idea['hypotheses']),
            completed_pocs=completed_pocs_text,
        )
    elif gate_num == 2:
        fields = dict(
            question=idea['question'],
            setup=idea['setup'],
            source_url=idea.get('source_url', ''),
        )
    else:  # gate 3
        fields = dict(
            question=idea['question'],
            estimated_effort=idea['estimated_effort'],
            expected_outcome=idea['expected_outcome'],
            confidence=idea['confidence'],
            device=config['system_context']['device'],
            ram_budget=config['system_context']['ram_budget'],
        )

    sys_tmpl, user_tmpl = templates
    system_text = sys_tmpl.format(**fields) if sys_tmpl else None
    user_text = user_tmpl.format(**fields)

    try:
        # Gate schemas are nested/complex; rely on the centralized robust JSON
        # parse (schema=None) rather than structured outputs here.
        result = call_json(client, model, system_text, user_text,
                           config['llm']['max_tokens'], tracker, schema=None)
        if result:
            return result.get(f'gate{gate_num}', {})
    except anthropic.APIError as e:
        print(f"  Error evaluating gate {gate_num}: {e}")
        return {"verdict": "FAIL", "overall_score": 0.0, "reason": f"Error: {e}"}

    return {"verdict": "FAIL", "overall_score": 0.0, "reason": "No JSON found in response"}


def validate_idea(client, config, idea, prompts, model, tracker):
    """Run the 3 gates for one idea. Returns (approved_idea_or_None, stats)
    where stats records which gates were reached/passed (aggregated later)."""
    stats = {f"gate{n}": {"reached": 0, "passed": 0} for n in (1, 2, 3)}
    label = idea['question'][:60]

    stats["gate1"]["reached"] = 1
    gate1 = evaluate_gate(client, config, idea, 1, prompts[1], model, tracker)
    print(f"  [{label}] Gate 1: {gate1.get('verdict', 'UNKNOWN')} ({gate1.get('overall_score', 0):.1f})")
    if gate1.get('verdict') == 'FAIL':
        return None, stats
    stats["gate1"]["passed"] = 1

    stats["gate2"]["reached"] = 1
    gate2 = evaluate_gate(client, config, idea, 2, prompts[2], model, tracker)
    print(f"  [{label}] Gate 2: {gate2.get('verdict', 'UNKNOWN')} ({gate2.get('overall_score', 0):.1f})")
    if gate2.get('verdict') == 'FAIL':
        return None, stats
    stats["gate2"]["passed"] = 1

    stats["gate3"]["reached"] = 1
    gate3 = evaluate_gate(client, config, idea, 3, prompts[3], model, tracker)
    print(f"  [{label}] Gate 3: {gate3.get('verdict', 'UNKNOWN')} ({gate3.get('overall_score', 0):.1f})")
    if gate3.get('verdict') in ['APPROVE', 'PASS']:
        stats["gate3"]["passed"] = 1
        idea['gate1'] = gate1
        idea['gate2'] = gate2
        idea['gate3'] = gate3
        idea['overall_verdict'] = 'APPROVED'
        return idea, stats
    return None, stats


def main():
    parser = argparse.ArgumentParser(description="Stage 4: Quality gate validation")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config = load_config()
    client = make_client(config)
    model = resolve_model(config, "gate")
    tracker = CostTracker(model)
    workers = int(config['llm'].get('max_workers', 1))
    prompts = {
        1: load_split_prompt("gate1-validation"),
        2: load_split_prompt("gate2-validation"),
        3: load_split_prompt("gate3-validation"),
    }

    print(f"=== Stage 4: Quality Gate Validation ({model}, {workers} worker(s)) ===")

    ideas = [json.loads(line) for line in open(args.input)]

    # Validate ideas concurrently; each idea's 3 gates run sequentially inside.
    def work(idea):
        return validate_idea(client, config, idea, prompts, model, tracker)

    results = concurrent_map(work, ideas, workers)

    approved = [idea for idea, _ in results if idea is not None]
    # Aggregate the per-idea funnel counters — a lopsided funnel (e.g. 36→1)
    # means a gate is likely miscalibrated; gate-stats.json makes it data-driven.
    gate_stats = {f"gate{n}": {"reached": 0, "passed": 0} for n in (1, 2, 3)}
    for _, stats in results:
        for n in (1, 2, 3):
            gate_stats[f"gate{n}"]["reached"] += stats[f"gate{n}"]["reached"]
            gate_stats[f"gate{n}"]["passed"] += stats[f"gate{n}"]["passed"]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        for idea in approved:
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
    print(f"Usage — {tracker.summary()}")
    return 0

if __name__ == "__main__":
    exit(main())
