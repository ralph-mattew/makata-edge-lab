#!/usr/bin/env python3
"""Stage 3: Extract PoC ideas from relevant papers using LLM"""
import argparse, json, os, re
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # put engine/ on sys.path
from pack import load_pack, add_pack_arg
import yaml
import requests
import anthropic
from _client import (make_client, resolve_model, CostTracker,
                     load_split_prompt, call_json, concurrent_map)

# Structured-outputs schema for the extracted ideas.
IDEAS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "question": {"type": "string"},
                    "why_matters": {"type": "array", "items": {"type": "string"}},
                    "source_establishes": {"type": "array", "items": {"type": "string"}},
                    "transfer_hypothesis": {"type": "string"},
                    "source_limits": {"type": "array", "items": {"type": "string"}},
                    "hypotheses": {"type": "array", "items": {"type": "string"}},
                    "setup": {"type": "string"},
                    "decision_rule": {"type": "string"},
                    "estimated_effort": {"type": "string"},
                    "expected_outcome": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["question", "why_matters", "source_establishes",
                             "transfer_hypothesis", "source_limits", "hypotheses", "setup",
                             "decision_rule", "estimated_effort", "expected_outcome", "confidence"],
            },
        }
    },
    "required": ["ideas"],
}


def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)


def fetch_fulltext(url: str, char_budget: int) -> str:
    """Best-effort arXiv full text via ar5iv HTML, truncated to a char budget.
    Returns '' on any failure (caller falls back to the abstract alone)."""
    m = re.search(r'(\d{4}\.\d{4,5})(v\d+)?', url or '')
    if not m:
        return ""
    arxiv_id = m.group(1)
    try:
        resp = requests.get(f"https://ar5iv.org/abs/{arxiv_id}", timeout=20)
        resp.raise_for_status()
        html = resp.text
        text = re.sub(r'(?is)<(script|style).*?</\1>', ' ', html)  # drop script/style
        text = re.sub(r'(?s)<[^>]+>', ' ', text)                   # strip tags
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:char_budget]
    except Exception as e:
        print(f"  (full text fetch failed for {arxiv_id}: {e}; using abstract)")
        return ""


def extract_ideas(client, config, paper, sys_tmpl, user_tmpl, model, tracker):
    fulltext = ""
    if config.get('sources', {}).get('fetch_fulltext'):
        budget = int(config.get('sources', {}).get('fulltext_char_budget', 20000))
        body = fetch_fulltext(paper.get('url', ''), budget)
        if body:
            fulltext = f"\nFULL TEXT (truncated):\n{body}"

    fields = dict(
        device=config['system_context']['device'],
        ram_budget=config['system_context']['ram_budget'],
        embedding_model=config['system_context']['embedding_model'],
        llm_model=config['system_context']['llm_model'],
        retrieval=config['system_context']['retrieval'],
        dataset=config['system_context']['dataset'],
        current_recall=config['system_context']['current_recall'],
        current_key_fact_accuracy=config['system_context']['current_key_fact_accuracy'],
        completed_pocs='\n'.join(f"- {poc}" for poc in config['system_context']['completed_pocs']),
        title=paper['title'],
        url=paper['url'],
        abstract=paper['abstract'],
        fulltext=fulltext,
    )
    system_text = sys_tmpl.format(**fields) if sys_tmpl else None
    user_text = user_tmpl.format(**fields)

    try:
        result = call_json(client, model, system_text, user_text,
                           config['llm']['max_tokens'], tracker, IDEAS_SCHEMA)
        return (result or {}).get('ideas', [])
    except (anthropic.APIError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
    return []


def main():
    parser = argparse.ArgumentParser(description="Stage 3: Extract PoC ideas")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    add_pack_arg(parser)
    args = parser.parse_args()

    config = load_pack(args.pack).config
    client = make_client(config)
    model = resolve_model(config, "extraction")
    tracker = CostTracker(model)
    workers = int(config['llm'].get('max_workers', 1))
    sys_tmpl, user_tmpl = load_split_prompt("idea-extraction")

    print(f"=== Stage 3: Idea Extraction ({model}, {workers} worker(s)) ===")

    papers = [json.loads(line) for line in open(args.input)]

    def work(paper):
        return paper, extract_ideas(client, config, paper, sys_tmpl, user_tmpl, model, tracker)

    results = concurrent_map(work, papers, workers)

    all_ideas = []
    for paper, ideas in results:
        for idea in ideas:
            idea['source_paper'] = paper['id']
            idea['source_title'] = paper['title']
            idea['source_url'] = paper['url']
            # Carry the source abstract so Stage 4 can grade claims against the
            # paper itself (ground truth), not just the idea's self-description.
            idea['source_abstract'] = paper.get('abstract', '')
            idea['idea_id'] = f"{paper['id']}-idea-{len(all_ideas)+1}"
            all_ideas.append(idea)
            print(f"  + {idea['question'][:80]}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        for idea in all_ideas:
            f.write(json.dumps(idea) + '\n')

    print(f"\n Extracted {len(all_ideas)} ideas from {len(papers)} papers")
    print(f"Usage — {tracker.summary()}")
    return 0

if __name__ == "__main__":
    exit(main())
