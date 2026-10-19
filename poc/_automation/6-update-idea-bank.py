#!/usr/bin/env python3
"""Stage 6: Update POC-IDEAS.md and generate weekly summary"""
import argparse, json
from pathlib import Path
from datetime import datetime

def generate_weekly_summary(ideas, scan_date):
    """Generate weekly summary markdown"""
    summary = f"""# Weekly Research Scan: {scan_date}

**Scan period**: Last 7 days
**New approved ideas**: {len(ideas)}

---

## ✅ New Approved Ideas ({len(ideas)})

"""

    for i, idea in enumerate(ideas):
        priority = idea.get('priority', 'MEDIUM')
        summary += f"""### {i+1}. {idea['question']}
**Source**: [{idea['source_title']}]({idea['source_url']})
**Priority**: {priority}
**Expected outcome**: {idea['expected_outcome']} ({int(idea['confidence']*100)}% confidence)
**Estimated effort**: {idea['estimated_effort']}
**ROI**: {idea.get('gate3', {}).get('roi_calculation', {}).get('expected_value', 0):.1f}

**Why it matters**:
{chr(10).join(f'- {item}' for item in idea['why_matters'])}

---

"""

    summary += f"""## 📊 Scan Statistics

| Metric | Value |
|--------|-------|
| New approved ideas | {len(ideas)} |
| Automation time | ~60-90 minutes |

## 🎯 Recommended Next Steps

"""
    if ideas:
        summary += f"1. Review ideas above\n2. Execute highest priority idea first\n"
    else:
        summary += "No new approved ideas this week. Continue with existing queue.\n"

    return summary

def main():
    parser = argparse.ArgumentParser(description="Stage 6: Update idea bank")
    parser.add_argument("--input", required=True)
    parser.add_argument("--idea-bank", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    print("=== Stage 6: Idea Bank Update ===")

    ideas = [json.loads(line) for line in open(args.input)]
    scan_date = datetime.now().strftime("%Y-%m-%d")

    # Generate summary
    summary = generate_weekly_summary(ideas, scan_date)

    # Write summary
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    with open(args.summary, 'w') as f:
        f.write(summary)

    print(f"Generated weekly summary: {args.summary}")
    print(f"\nNew approved ideas: {len(ideas)}")

    # Note: Actual merging to POC-IDEAS.md would require parsing existing MD
    # For now, just print instructions
    print(f"\nTo update POC-IDEAS.md:")
    print(f"1. Review {args.summary}")
    print(f"2. Manually add approved ideas to {args.idea-bank}")
    print(f"3. Commit changes")

    return 0

if __name__ == "__main__":
    exit(main())
