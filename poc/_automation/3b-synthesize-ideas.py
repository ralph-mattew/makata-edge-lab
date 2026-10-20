#!/usr/bin/env python3
"""Stage 3b: Synthesize NOVEL PoC candidates by recombination / cross-pollination.

Per-paper extraction (Stage 3) produces single-source transfer ideas. This stage goes
one step further: it cross-pollinates THIS WEEK'S relevant papers with each other and with
the lab's OWN open problems (knowledge/open-problems.md), applying explicit innovation
techniques (problem×method, method×method, analogical transfer, constraint-driven) to
DERIVE candidates that no single paper proposes. This is how the lab's best PoCs arose
(attacking its own bottleneck, PoC 013→014/015) rather than from paper-scanning alone.

Output ideas use the same schema as Stage 3 (so Stage 4 gates them unchanged), plus
`technique`, `attacks_problem`, and `source_papers`. Grounding fields
(source_establishes / transfer_hypothesis / source_limits) are required, same as Stage 3.

Input: the relevant-research JSONL from Stage 2 (the batch to cross-pollinate).
"""
import argparse, json
from pathlib import Path
import yaml
import anthropic
from _client import (make_client, resolve_model, CostTracker,
                     load_split_prompt, call_json)
from _knowledge import load_open_problems, format_prior_results

SYNTH_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"ideas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "technique": {"type": "string"},
            "attacks_problem": {"type": "string"},
            "source_papers": {"type": "array", "items": {"type": "string"}},
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
        "required": ["technique", "attacks_problem", "source_papers", "question",
                     "why_matters", "source_establishes", "transfer_hypothesis",
                     "source_limits", "hypotheses", "setup", "decision_rule",
                     "estimated_effort", "expected_outcome", "confidence"],
    }}},
    "required": ["ideas"],
}


def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)


def paper_digest(papers, max_abstract=600):
    lines = []
    for p in papers:
        ab = (p.get("abstract") or "").strip().replace("\n", " ")
        lines.append(f"- [{p.get('id','?')}] {p['title']}\n    {ab[:max_abstract]}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Stage 3b: Synthesize ideas by recombination")
    ap.add_argument("--input", required=True, help="relevant-research JSONL (Stage 2 output)")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    config = load_config()
    client = make_client(config)
    model = resolve_model(config, "extraction")
    tracker = CostTracker(model)
    sys_tmpl, user_tmpl = load_split_prompt("idea-synthesis")

    papers = [json.loads(l) for l in open(args.input)]
    if not papers:
        print("No relevant papers to synthesize from."); Path(args.output).write_text(""); return 0

    sc = config['system_context']
    open_problems = load_open_problems() or "(no open-problems file)"
    # Use the strongest open problem as the retrieval key for prior lessons.
    prior = format_prior_results("hard category recall chunking query formulation on-device", config)

    fields = dict(
        device=sc['device'], ram_budget=sc['ram_budget'],
        embedding_model=sc['embedding_model'], llm_model=sc['llm_model'],
        retrieval=sc['retrieval'], dataset=sc['dataset'],
        current_recall=sc['current_recall'], current_key_fact_accuracy=sc['current_key_fact_accuracy'],
        completed_pocs='\n'.join(f"- {p}" for p in sc['completed_pocs']),
        open_problems=open_problems, prior_results=prior,
        paper_digest=paper_digest(papers),
    )
    system_text = sys_tmpl.format(**fields) if sys_tmpl else None
    user_text = user_tmpl.format(**fields)

    print(f"=== Stage 3b: Synthesis / cross-pollination ({model}) ===")
    print(f"  cross-pollinating {len(papers)} papers × lab open problems")
    try:
        result = call_json(client, model, system_text, user_text,
                           config['llm']['max_tokens'], tracker, SYNTH_SCHEMA)
        ideas = (result or {}).get('ideas', [])
    except (anthropic.APIError, json.JSONDecodeError) as e:
        print(f"Error: {e}"); ideas = []

    # Provenance: synthesized ideas aren't tied to one source paper. Record the batch
    # cited in source_papers; set source_title/abstract to a combined digest so Stage 4
    # can still ground the mechanism against the cited papers.
    by_id = {p.get('id'): p for p in papers}
    by_title = {p['title']: p for p in papers}
    out = []
    for i, idea in enumerate(ideas):
        cited = idea.get('source_papers', [])
        matched = [by_id.get(c) or by_title.get(c) for c in cited]
        matched = [m for m in matched if m]
        idea['source_paper'] = "synthesis:" + "+".join(str(m.get('id','?')) for m in matched) if matched else "synthesis"
        idea['source_title'] = " + ".join(m['title'] for m in matched) if matched else "(synthesized from this week's batch)"
        idea['source_abstract'] = "\n\n".join(
            f"[{m.get('id','?')}] {m['title']}: {(m.get('abstract') or '')[:500]}" for m in matched
        ) or "(synthesized; see source_establishes)"
        idea['source_url'] = matched[0].get('url', '') if matched else ''
        idea['idea_id'] = f"synth-idea-{i+1}"
        out.append(idea)
        print(f"  + [{idea.get('technique','?')}|{idea.get('attacks_problem','?')}] {idea['question'][:80]}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        for idea in out:
            f.write(json.dumps(idea) + '\n')
    print(f"\n Synthesized {len(out)} recombined candidates from {len(papers)} papers")
    print(f"Usage — {tracker.summary()}")
    return 0


if __name__ == "__main__":
    exit(main())
