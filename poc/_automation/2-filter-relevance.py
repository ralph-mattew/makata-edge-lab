#!/usr/bin/env python3
"""
Stage 2: Relevance Filtering
Uses LLM to score each paper's relevance to mobile/edge RAG.
"""
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

import yaml

from _client import make_client, resolve_model, CostTracker

try:
    import anthropic
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    print("Warning: anthropic library not installed. Install with: pip3 install anthropic")


def load_config() -> Dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_prompt_template(name: str) -> str:
    """Load prompt template from prompts/ directory"""
    prompt_path = Path(__file__).parent / "prompts" / f"{name}.txt"
    return prompt_path.read_text()


def evaluate_relevance(client: Anthropic, config: Dict, candidate: Dict, prompt_template: str,
                       model: str, tracker: CostTracker) -> Dict:
    """Use LLM to evaluate paper relevance"""
    # Fill in prompt template
    prompt = prompt_template.format(
        device=config['system_context']['device'],
        ram_budget=config['system_context']['ram_budget'],
        embedding_model=config['system_context']['embedding_model'],
        llm_model=config['system_context']['llm_model'],
        retrieval=config['system_context']['retrieval'],
        dataset=config['system_context']['dataset'],
        current_recall=config['system_context']['current_recall'],
        current_key_fact_accuracy=config['system_context']['current_key_fact_accuracy'],
        title=candidate['title'],
        authors=', '.join(candidate['authors'][:3]),  # First 3 authors
        date=candidate['date'],
        abstract=candidate['abstract']
    )

    # Call LLM
    try:
        response = client.messages.create(
            model=model,
            max_tokens=config['llm']['max_tokens'],
            messages=[{"role": "user", "content": prompt}]
        )
        tracker.add(response.usage)

        # Parse JSON response
        response_text = response.content[0].text
        # Extract JSON from response (sometimes LLM adds explanation before/after JSON)
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_text = response_text[start_idx:end_idx]
            result = json.loads(json_text)
            return result
        else:
            raise ValueError(f"No JSON found in response: {response_text}")

    except (anthropic.APIError, ValueError, json.JSONDecodeError) as e:
        print(f"Error evaluating {candidate['title']}: {e}")
        return {
            "score": 0.0,
            "reason": f"Error: {e}",
            "key_contribution": "",
            "applicable": False
        }


def main():
    parser = argparse.ArgumentParser(description="Stage 2: Filter papers by relevance")
    parser.add_argument("--input", required=True, help="Input JSONL from Stage 1")
    parser.add_argument("--output", required=True, help="Output JSONL")
    parser.add_argument("--batch-size", type=int, default=10, help="Papers to process per batch")
    args = parser.parse_args()

    if not HAS_ANTHROPIC:
        print("Error: anthropic library required. Install with: pip3 install anthropic")
        return 1

    config = load_config()

    client = make_client(config)
    model = resolve_model(config, "relevance")
    tracker = CostTracker(model)

    # Load prompt template
    prompt_template = load_prompt_template("relevance-filter")

    print(f"=== Stage 2: Relevance Filtering ({model}) ===")

    # Load candidates
    candidates = []
    with open(args.input) as f:
        for line in f:
            candidates.append(json.loads(line))

    print(f"Loaded {len(candidates)} candidates")
    print(f"Min relevance score: {config['relevance']['min_score']}/10")

    # Evaluate each candidate
    relevant = []
    for i, candidate in enumerate(candidates):
        print(f"[{i+1}/{len(candidates)}] Evaluating: {candidate['title'][:60]}...")

        result = evaluate_relevance(client, config, candidate, prompt_template, model, tracker)

        # Add relevance info to candidate
        candidate['relevance_score'] = result['score']
        candidate['relevance_reason'] = result['reason']
        candidate['key_contribution'] = result.get('key_contribution', '')
        candidate['applicable'] = result.get('applicable', False)

        # Filter by threshold
        if result['score'] >= config['relevance']['min_score']:
            relevant.append(candidate)
            print(f"  ✓ RELEVANT ({result['score']}/10): {result['reason'][:80]}")
        else:
            print(f"  ✗ NOT RELEVANT ({result['score']}/10): {result['reason'][:80]}")

    print(f"\n=== Results ===")
    print(f"Candidates evaluated: {len(candidates)}")
    print(f"Relevant papers: {len(relevant)} ({100*len(relevant)/len(candidates):.1f}%)")
    print(f"Usage — {tracker.summary()}")

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        for paper in relevant:
            f.write(json.dumps(paper) + '\n')

    print(f"Wrote {len(relevant)} relevant papers to {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
