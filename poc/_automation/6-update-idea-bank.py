#!/usr/bin/env python3
"""Stage 6: Update POC-IDEAS.md and generate weekly summary.

Dedupes approved ideas against the existing idea bank (and against each other)
using a fuzzy title match, then inserts the survivors into a dated
"Recently Discovered" section of POC-IDEAS.md. `--dry-run` previews without
writing the bank.
"""
import argparse, json, re
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime

import yaml


def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)


def _norm(s: str) -> str:
    """Lowercase, strip non-alphanumerics → for fuzzy title comparison."""
    return re.sub(r'[^a-z0-9 ]', '', (s or '').lower()).strip()


def existing_idea_titles(idea_bank_path: Path) -> list[str]:
    """Every `### ...` heading in the bank, normalized. Covers both the
    `### PoC-X:` entries and the `### Idea: ...` auto-added ones, so a question
    we added in a prior week is matched and not re-added."""
    if not idea_bank_path.exists():
        return []
    titles = []
    for line in idea_bank_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            heading = line[4:].strip()
            heading = re.sub(r'^(PoC-[A-Z]*\d+|Idea):\s*', '', heading)  # drop label prefix
            titles.append(_norm(heading))
    return titles


def is_duplicate(question: str, known: list[str], threshold: float) -> tuple[bool, str]:
    """True if `question` fuzzily matches any known title at/above threshold."""
    q = _norm(question)
    for k in known:
        if not k:
            continue
        if q == k or SequenceMatcher(None, q, k).ratio() >= threshold:
            return True, k
    return False, ""


def dedupe_ideas(ideas, idea_bank_path, threshold):
    """Split ideas into (new, duplicates). Checks against the bank and against
    earlier ideas in this same batch."""
    known = existing_idea_titles(idea_bank_path)
    new, dupes = [], []
    for idea in ideas:
        dup, against = is_duplicate(idea["question"], known, threshold)
        if dup:
            idea["_duplicate_of"] = against
            dupes.append(idea)
        else:
            new.append(idea)
            known.append(_norm(idea["question"]))  # dedupe within the batch too
    return new, dupes


def format_bank_entry(idea) -> str:
    """One `### Idea:` block matching the existing Recently-Discovered style."""
    why = idea.get("why_matters") or []
    roi = idea.get("gate3", {}).get("roi_calculation", {}).get("expected_value", 0)
    return (
        f"### Idea: {idea['question']}\n"
        f"**Status**: 🔬 Approved by automated quality gate — ready to register\n\n"
        f"**Source**: [{idea.get('source_title', '')}]({idea.get('source_url', '')})\n\n"
        f"**Why interesting**: {why[0] if why else 'see source'}\n\n"
        f"**Priority**: {idea.get('priority', 'MEDIUM')} · "
        f"**Effort**: {idea.get('estimated_effort', '?')} · "
        f"**Expected**: {idea.get('expected_outcome', '?')} "
        f"({int(idea.get('confidence', 0) * 100)}% confidence) · "
        f"**ROI**: {roi:.1f}\n\n"
        f"**Next step**: Register as a PoC following POC-GENERATION-WORKFLOW.md\n"
    )


def update_idea_bank(new_ideas, idea_bank_path: Path, scan_date: str, dry_run: bool) -> int:
    """Insert new ideas into a dated Recently-Discovered section. Returns count
    written. If the section for today exists, appends to it; else creates it."""
    if not new_ideas:
        return 0
    block = "\n---\n\n".join(format_bank_entry(i) for i in new_ideas)
    section_header = f"## Recently Discovered ({scan_date}) — Needs Further Research"

    text = idea_bank_path.read_text(encoding="utf-8") if idea_bank_path.exists() else "# PoC Idea Bank\n"
    if section_header in text:
        # Append under today's existing section header.
        insert_at = text.index(section_header) + len(section_header)
        # skip the blank line(s) right after the header
        tail = text[insert_at:]
        text = text[:insert_at] + "\n\n" + block + "\n\n---\n" + tail.lstrip("\n")
    else:
        text = text.rstrip() + f"\n\n---\n\n{section_header}\n\n{block}\n\n---\n"

    if dry_run:
        print(f"[dry-run] would write {len(new_ideas)} idea(s) to {idea_bank_path}")
    else:
        idea_bank_path.write_text(text, encoding="utf-8")
        print(f"Wrote {len(new_ideas)} idea(s) to {idea_bank_path}")
    return len(new_ideas)


def generate_weekly_summary(ideas, dupes, scan_date):
    """Generate weekly summary markdown"""
    summary = f"""# Weekly Research Scan: {scan_date}

**Scan period**: Last 7 days
**New approved ideas**: {len(ideas)}  ·  **Duplicates skipped**: {len(dupes)}

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

    if dupes:
        summary += f"## ♻️ Skipped as Duplicates ({len(dupes)})\n\n"
        for idea in dupes:
            summary += f"- {idea['question']}  _(matches: {idea.get('_duplicate_of', '?')})_\n"
        summary += "\n"

    summary += f"""## 📊 Scan Statistics

| Metric | Value |
|--------|-------|
| New approved ideas | {len(ideas)} |
| Duplicates skipped | {len(dupes)} |
| Automation time | ~60-90 minutes |

## 🎯 Recommended Next Steps

"""
    if ideas:
        summary += "1. Review ideas above\n2. Execute highest priority idea first\n"
    else:
        summary += "No new approved ideas this week. Continue with existing queue.\n"

    return summary

def main():
    parser = argparse.ArgumentParser(description="Stage 6: Update idea bank")
    parser.add_argument("--input", required=True)
    parser.add_argument("--idea-bank", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview; do not modify the idea bank.")
    args = parser.parse_args()

    config = load_config()
    threshold = config.get("duplicates", {}).get("similarity_threshold", 0.8)
    check_dupes = config.get("duplicates", {}).get("check_against_existing", True)

    print("=== Stage 6: Idea Bank Update ===")

    ideas = [json.loads(line) for line in open(args.input)]
    scan_date = datetime.now().strftime("%Y-%m-%d")
    idea_bank_path = Path(args.idea_bank)

    if check_dupes:
        new_ideas, dupes = dedupe_ideas(ideas, idea_bank_path, threshold)
        print(f"Deduped: {len(new_ideas)} new, {len(dupes)} duplicate(s) "
              f"(threshold {threshold})")
    else:
        new_ideas, dupes = ideas, []

    # Generate + write summary
    summary = generate_weekly_summary(new_ideas, dupes, scan_date)
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    with open(args.summary, 'w') as f:
        f.write(summary)
    print(f"Generated weekly summary: {args.summary}")

    # Insert the non-duplicate ideas into the bank
    update_idea_bank(new_ideas, idea_bank_path, scan_date, args.dry_run)

    return 0

if __name__ == "__main__":
    exit(main())
