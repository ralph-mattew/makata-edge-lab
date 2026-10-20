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

from _client import make_client, resolve_model, CostTracker, load_split_prompt, call_json, concurrent_map

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    print("Warning: anthropic library not installed. Install with: pip3 install anthropic")

# Structured-outputs schema for the relevance verdict (no numeric min/max allowed).
RELEVANCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "score": {"type": "number", "description": "Relevance 0-10"},
        "reason": {"type": "string"},
        "key_contribution": {"type": "string"},
        "applicable": {"type": "boolean"},
    },
    "required": ["score", "reason", "key_contribution", "applicable"],
}


def load_config() -> Dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def evaluate_relevance(client, config: Dict, candidate: Dict, sys_tmpl, user_tmpl,
                       model: str, tracker: CostTracker) -> Dict:
    """Use LLM to evaluate paper relevance (cached system block + structured output)."""
    fields = dict(
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
        abstract=candidate['abstract'],
    )
    system_text = sys_tmpl.format(**fields) if sys_tmpl else None
    user_text = user_tmpl.format(**fields)

    try:
        result = call_json(client, model, system_text, user_text,
                           config['llm']['max_tokens'], tracker, RELEVANCE_SCHEMA)
        if not result:
            raise ValueError("no JSON in response")
        return result
    except (anthropic.APIError, ValueError, json.JSONDecodeError) as e:
        print(f"Error evaluating {candidate['title']}: {e}")
        return {"score": 0.0, "reason": f"Error: {e}", "key_contribution": "", "applicable": False}


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
    workers = int(config['llm'].get('max_workers', 1))

    sys_tmpl, user_tmpl = load_split_prompt("relevance-filter")

    print(f"=== Stage 2: Relevance Filtering ({model}, {workers} worker(s)) ===")

    # Load candidates
    candidates = []
    with open(args.input) as f:
        for line in f:
            candidates.append(json.loads(line))

    print(f"Loaded {len(candidates)} candidates")
    print(f"Min relevance score: {config['relevance']['min_score']}/10")

    # Evaluate candidates concurrently (order preserved).
    def work(candidate):
        return candidate, evaluate_relevance(client, config, candidate, sys_tmpl, user_tmpl, model, tracker)

    results = concurrent_map(work, candidates, workers)

    relevant = []
    for candidate, result in results:
        candidate['relevance_score'] = result['score']
        candidate['relevance_reason'] = result['reason']
        candidate['key_contribution'] = result.get('key_contribution', '')
        candidate['applicable'] = result.get('applicable', False)
        if result['score'] >= config['relevance']['min_score']:
            relevant.append(candidate)
            print(f"  ✓ RELEVANT ({result['score']}/10): {candidate['title'][:55]}")
        else:
            print(f"  ✗ ({result['score']}/10): {candidate['title'][:55]}")

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
