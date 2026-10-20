"""Shared 3-gate quality evaluation.

Imported by Stage 4 (`4-validate-quality-gate.py`) and by the calibration
harness (`calibrate.py`) so both exercise the identical gate logic — the harness
can't drift from production.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import anthropic

from _client import load_split_prompt, call_json, call_json_with_tools
from _knowledge import format_prior_results


def load_gate_prompts() -> Dict[int, Tuple]:
    return {
        1: load_split_prompt("gate1-validation"),
        2: load_split_prompt("gate2-validation"),
        3: load_split_prompt("gate3-validation"),
    }


def evaluate_gate(client, config, idea, gate_num, templates, model, tracker):
    """Evaluate a single gate. `templates` is a (system, user) pair."""
    completed_pocs_text = '\n'.join(f"- {poc}" for poc in config['system_context']['completed_pocs'])
    # Source grounding: the grader judges claims against the paper, not the
    # idea's self-description. Older idea records may lack these fields.
    source_title = idea.get('source_title', '')
    source_abstract = idea.get('source_abstract', '') or '(source abstract not available)'

    if gate_num == 1:
        fields = dict(
            question=idea['question'],
            why_matters='\n'.join(f"- {item}" for item in idea['why_matters']),
            hypotheses='\n'.join(f"- {h}" for h in idea['hypotheses']),
            completed_pocs=completed_pocs_text,
            source_title=source_title,
            source_abstract=source_abstract,
            # Feedback loop: the most relevant completed-PoC outcomes + lessons.
            prior_results=format_prior_results(idea['question'], config),
        )
    elif gate_num == 2:
        fields = dict(
            question=idea['question'],
            setup=idea['setup'],
            source_url=idea.get('source_url', ''),
            source_title=source_title,
            source_abstract=source_abstract,
        )
    else:  # gate 3
        fields = dict(
            question=idea['question'],
            estimated_effort=idea['estimated_effort'],
            expected_outcome=idea['expected_outcome'],
            confidence=idea['confidence'],
            device=config['system_context']['device'],
            ram_budget=config['system_context']['ram_budget'],
            source_title=source_title,
            source_abstract=source_abstract,
        )

    sys_tmpl, user_tmpl = templates
    system_text = sys_tmpl.format(**fields) if sys_tmpl else None
    user_text = user_tmpl.format(**fields)

    # Gate 2 (solution understanding) can use web_search to verify an
    # implementation actually exists / runs on-device, instead of guessing from
    # training data. Opt-in (costs extra) via quality_gate.gate2_web_search.
    qg = config.get('quality_gate', {})
    use_search = gate_num == 2 and qg.get('gate2_web_search')

    try:
        # Gate schemas are nested/complex; rely on the centralized robust JSON
        # parse (schema=None) rather than structured outputs here.
        if use_search:
            tools = [{"type": "web_search_20260209", "name": "web_search",
                      "max_uses": int(qg.get('gate2_web_search_max_uses', 3))}]
            result = call_json_with_tools(client, model, system_text, user_text,
                                          config['llm']['max_tokens'], tracker, tools)
        else:
            result = call_json(client, model, system_text, user_text,
                               config['llm']['max_tokens'], tracker, schema=None)
        if result:
            return _apply_threshold(result.get(f'gate{gate_num}', {}), gate_num, config)
    except anthropic.APIError as e:
        print(f"  Error evaluating gate {gate_num}: {e}")
        return {"verdict": "FAIL", "overall_score": 0.0, "reason": f"Error: {e}"}

    return {"verdict": "FAIL", "overall_score": 0.0, "reason": "No JSON found in response"}


def _apply_threshold(gate: dict, gate_num: int, config: dict) -> dict:
    """The pipeline owns the verdict, not the model. Derive PASS/FAIL (Gate 3:
    APPROVE/REJECT) from overall_score vs the config threshold, so the decision
    is consistent with the score and the `quality_gate.*_min_score` knobs are
    actually enforced (previously the model's self-declared verdict was trusted,
    which could contradict its own score)."""
    thr = float(config.get("quality_gate", {}).get(f"gate{gate_num}_min_score", 6.0))
    score = gate.get("overall_score")
    if isinstance(score, (int, float)):
        passed = score >= thr
        if gate_num == 3:
            gate["verdict"] = "APPROVE" if passed else "REJECT"
        else:
            gate["verdict"] = "PASS" if passed else "FAIL"
    gate["threshold"] = thr
    return gate


def validate_idea(client, config, idea, prompts, model, tracker):
    """Run the 3 gates for one idea. Returns (idea, approved, stats). Gate
    results (incl. evidence/red_flags) are attached to `idea` whether it passes
    or fails, so the caller can record rejects — the lab publishes those too."""
    stats = {f"gate{n}": {"reached": 0, "passed": 0} for n in (1, 2, 3)}
    label = idea['question'][:60]

    stats["gate1"]["reached"] = 1
    gate1 = evaluate_gate(client, config, idea, 1, prompts[1], model, tracker)
    idea['gate1'] = gate1
    print(f"  [{label}] Gate 1: {gate1.get('verdict', 'UNKNOWN')} ({gate1.get('overall_score', 0):.1f})")
    if gate1.get('verdict') == 'FAIL':
        idea['overall_verdict'] = 'REJECTED_GATE1'
        return idea, False, stats
    stats["gate1"]["passed"] = 1

    stats["gate2"]["reached"] = 1
    gate2 = evaluate_gate(client, config, idea, 2, prompts[2], model, tracker)
    idea['gate2'] = gate2
    print(f"  [{label}] Gate 2: {gate2.get('verdict', 'UNKNOWN')} ({gate2.get('overall_score', 0):.1f})")
    if gate2.get('verdict') == 'FAIL':
        idea['overall_verdict'] = 'REJECTED_GATE2'
        return idea, False, stats
    stats["gate2"]["passed"] = 1

    stats["gate3"]["reached"] = 1
    gate3 = evaluate_gate(client, config, idea, 3, prompts[3], model, tracker)
    idea['gate3'] = gate3
    print(f"  [{label}] Gate 3: {gate3.get('verdict', 'UNKNOWN')} ({gate3.get('overall_score', 0):.1f})")
    if gate3.get('verdict') in ['APPROVE', 'PASS']:
        stats["gate3"]["passed"] = 1
        idea['overall_verdict'] = 'APPROVED'
        return idea, True, stats
    idea['overall_verdict'] = 'REJECTED_GATE3'
    return idea, False, stats
