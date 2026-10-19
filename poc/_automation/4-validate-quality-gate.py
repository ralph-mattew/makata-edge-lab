#!/usr/bin/env python3
"""Stage 4: Validate ideas through 3-gate quality process"""
import argparse, json, os
from pathlib import Path
import yaml
from anthropic import Anthropic

def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)

def load_prompt(name):
    return (Path(__file__).parent / "prompts" / f"{name}.txt").read_text()

def evaluate_gate(client, config, idea, gate_num, prompt_template):
    """Evaluate a single gate"""
    completed_pocs_text = '\n'.join(f"- {poc}" for poc in config['system_context']['completed_pocs'])

    if gate_num == 1:
        prompt = prompt_template.format(
            question=idea['question'],
            why_matters='\n'.join(f"- {item}" for item in idea['why_matters']),
            hypotheses='\n'.join(f"- {h}" for h in idea['hypotheses']),
            completed_pocs=completed_pocs_text
        )
    elif gate_num == 2:
        prompt = prompt_template.format(
            question=idea['question'],
            setup=idea['setup'],
            source_url=idea.get('source_url', '')
        )
    elif gate_num == 3:
        prompt = prompt_template.format(
            question=idea['question'],
            estimated_effort=idea['estimated_effort'],
            expected_outcome=idea['expected_outcome'],
            confidence=idea['confidence'],
            device=config['system_context']['device'],
            ram_budget=config['system_context']['ram_budget']
        )

    try:
        response = client.messages.create(
            model=config['llm']['model'],
            max_tokens=config['llm']['max_tokens'],
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text
        start, end = text.find('{'), text.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            return result.get(f'gate{gate_num}', {})
    except Exception as e:
        print(f"  Error evaluating gate {gate_num}: {e}")
        return {"verdict": "FAIL", "overall_score": 0.0, "reason": f"Error: {e}"}

    return {"verdict": "FAIL", "overall_score": 0.0, "reason": "No JSON found in response"}

def main():
    parser = argparse.ArgumentParser(description="Stage 4: Quality gate validation")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config = load_config()
    api_key = os.getenv(config['llm']['api_key_env'])
    if not api_key:
        print(f"Error: Set {config['llm']['api_key_env']}")
        return 1

    # Support user-scoped API keys with workspace ID
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_01QUXXVWdV2avEfw6N37vSkC")
    client = Anthropic(
        api_key=api_key,
        default_headers={"anthropic-workspace-id": workspace_id} if api_key.startswith("sk-ant-usr-") else {}
    )
    prompts = {
        1: load_prompt("gate1-validation"),
        2: load_prompt("gate2-validation"),
        3: load_prompt("gate3-validation")
    }

    print("=== Stage 4: Quality Gate Validation ===")

    ideas = [json.loads(line) for line in open(args.input)]
    approved = []

    for i, idea in enumerate(ideas):
        print(f"\n[{i+1}/{len(ideas)}] Validating: {idea['question'][:60]}")

        # Evaluate 3 gates
        gate1 = evaluate_gate(client, config, idea, 1, prompts[1])
        print(f"  Gate 1: {gate1.get('verdict', 'UNKNOWN')} ({gate1.get('overall_score', 0):.1f}/10)")

        if gate1.get('verdict') == 'FAIL':
            print(f"    Reason: {gate1.get('reason', '')[:100]}")
            continue

        gate2 = evaluate_gate(client, config, idea, 2, prompts[2])
        print(f"  Gate 2: {gate2.get('verdict', 'UNKNOWN')} ({gate2.get('overall_score', 0):.1f}/10)")

        if gate2.get('verdict') == 'FAIL':
            print(f"    Reason: {gate2.get('reason', '')[:100]}")
            continue

        gate3 = evaluate_gate(client, config, idea, 3, prompts[3])
        print(f"  Gate 3: {gate3.get('verdict', 'UNKNOWN')} ({gate3.get('overall_score', 0):.1f}/10)")

        if gate3.get('verdict') in ['APPROVE', 'PASS']:
            idea['gate1'] = gate1
            idea['gate2'] = gate2
            idea['gate3'] = gate3
            idea['overall_verdict'] = 'APPROVED'
            approved.append(idea)
            print(f"  ✓ APPROVED")
        else:
            print(f"    Reason: {gate3.get('reason', '')[:100]}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        for idea in approved:
            f.write(json.dumps(idea) + '\n')

    print(f"\n=== Results ===")
    print(f"Ideas validated: {len(ideas)}")
    print(f"Approved: {len(approved)} ({100*len(approved)/len(ideas) if ideas else 0:.1f}%)")
    return 0

if __name__ == "__main__":
    exit(main())
