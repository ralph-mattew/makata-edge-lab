#!/usr/bin/env python3
"""Stage 3: Extract PoC ideas from relevant papers using LLM"""
import argparse, json, os
from pathlib import Path
import yaml
import anthropic
from _client import make_client, resolve_model, CostTracker

def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)

def load_prompt():
    return (Path(__file__).parent / "prompts" / "idea-extraction.txt").read_text()

def extract_ideas(client, config, paper, prompt_template, model, tracker):
    prompt = prompt_template.format(
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
        abstract=paper['abstract']
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=config['llm']['max_tokens'],
            messages=[{"role": "user", "content": prompt}]
        )
        tracker.add(response.usage)
        text = response.content[0].text
        start, end = text.find('{'), text.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            return result.get('ideas', [])
    except (anthropic.APIError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
    return []

def main():
    parser = argparse.ArgumentParser(description="Stage 3: Extract PoC ideas")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config = load_config()
    client = make_client(config)
    model = resolve_model(config, "extraction")
    tracker = CostTracker(model)
    prompt = load_prompt()

    print(f"=== Stage 3: Idea Extraction ({model}) ===")

    papers = [json.loads(line) for line in open(args.input)]
    all_ideas = []

    for i, paper in enumerate(papers):
        print(f"[{i+1}/{len(papers)}] Extracting ideas from: {paper['title'][:60]}...")
        ideas = extract_ideas(client, config, paper, prompt, model, tracker)

        for idea in ideas:
            idea['source_paper'] = paper['id']
            idea['source_title'] = paper['title']
            idea['source_url'] = paper['url']
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
