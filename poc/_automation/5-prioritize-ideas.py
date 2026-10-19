#!/usr/bin/env python3
"""Stage 5: Prioritize approved ideas by ROI"""
import argparse, json
from pathlib import Path
import yaml

def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)

def calculate_priority_score(idea, config):
    """Calculate priority score from impact, effort, confidence"""
    weights = config['prioritization']

    # Extract scores from Gate 3
    impact = idea.get('gate3', {}).get('roi_calculation', {}).get('impact_if_adopt', 5.0)
    confidence = idea.get('confidence', 0.5)

    # Convert effort to 0-10 scale (inverse: less effort = higher score)
    effort_str = idea.get('estimated_effort', '1 week').lower()
    if 'hour' in effort_str or 'day' in effort_str and int(effort_str.split()[0]) <= 3:
        effort_score = 9.0
    elif 'day' in effort_str:
        effort_score = 7.0
    elif 'week' in effort_str and int(effort_str.split()[0]) == 1:
        effort_score = 5.0
    elif 'week' in effort_str:
        effort_score = 3.0
    else:
        effort_score = 2.0

    score = (
        weights['impact_weight'] * impact +
        weights['effort_weight'] * effort_score +
        weights['confidence_weight'] * (confidence * 10)
    )

    return score

def assign_priority_label(score, effort_str):
    """Assign priority label based on score and effort"""
    if score >= 8.0 and ('hour' in effort_str or 'day' in effort_str):
        return "🔥 HIGH"
    elif score >= 6.0:
        return "📊 MEDIUM"
    else:
        return "🟠 LOW"

def main():
    parser = argparse.ArgumentParser(description="Stage 5: Prioritize ideas")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config = load_config()

    print("=== Stage 5: Prioritization ===")

    ideas = [json.loads(line) for line in open(args.input)]

    # Calculate priority scores
    for idea in ideas:
        idea['priority_score'] = calculate_priority_score(idea, config)
        idea['priority'] = assign_priority_label(idea['priority_score'], idea['estimated_effort'])

    # Sort by score (descending)
    ideas.sort(key=lambda x: x['priority_score'], reverse=True)

    # Write output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        for idea in ideas:
            f.write(json.dumps(idea) + '\n')

    print(f"Prioritized {len(ideas)} ideas:")
    for i, idea in enumerate(ideas[:10]):  # Show top 10
        print(f"  {i+1}. [{idea['priority']}] {idea['question'][:70]}")
        print(f"     Score: {idea['priority_score']:.2f}, Effort: {idea['estimated_effort']}")

    return 0

if __name__ == "__main__":
    exit(main())
