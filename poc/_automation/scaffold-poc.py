#!/usr/bin/env python3
"""Scaffold a PoC folder from an approved idea.

Bridges ideation -> execution: turns an approved idea (from Stage 4's
validated-ideas.jsonl) into `poc/NNN-slug/README.md` pre-filled in the lab's
_template format, with a pre-registration draft the author just has to refine
before the first run (per POC-GENERATION-WORKFLOW.md).

  ./scaffold-poc.py --input scans/<date>/validated-ideas.jsonl           # first approved idea
  ./scaffold-poc.py --input validated-ideas.jsonl --idea-id <id>         # a specific one
  ./scaffold-poc.py --input validated-ideas.jsonl --all                  # one folder per idea
  ./scaffold-poc.py --input validated-ideas.jsonl --dry-run              # print, don't write
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parent.parent  # .../poc
STOPWORDS = {"does", "do", "can", "the", "a", "an", "of", "to", "for", "on", "in",
             "with", "and", "or", "is", "are", "while", "without", "by", "at", "vs",
             "using", "into", "from", "that", "this", "it", "its", "than", "as"}


def next_poc_number() -> int:
    nums = [int(m.group(1)) for p in POC_ROOT.iterdir()
            if p.is_dir() and (m := re.match(r"(\d{3})-", p.name))]
    return (max(nums) + 1) if nums else 1


def slugify(question: str, max_words: int = 6) -> str:
    words = re.findall(r"[a-z0-9]+", question.lower())
    keep = [w for w in words if w not in STOPWORDS] or words
    return "-".join(keep[:max_words]) or "idea"


def title_from(question: str) -> str:
    t = question.strip().rstrip("?").strip()
    return t[0].upper() + t[1:] if t else "Untitled PoC"


def _bullets(items) -> str:
    if isinstance(items, str):
        items = [items]
    return "\n".join(f"- {x}" for x in (items or [])) or "- (fill in)"


def render_readme(idea: dict, number: int) -> str:
    n = f"{number:03d}"
    today = datetime.date.today().isoformat()
    src = idea.get("source_title") or "(source)"
    src_url = idea.get("source_url") or ""
    src_line = f"[{src}]({src_url})" if src_url else src
    hyps = idea.get("hypotheses") or []
    # Strip any leading "H1:"/"H2." the extractor already put on the hypothesis,
    # so we don't render "H1: H1: ...".
    def _strip_h(h):
        return re.sub(r'^\s*H\d+[:.)]\s*', '', h)
    hyp_block = "\n".join(
        f"- **H{i+1}**: {_strip_h(h)}  _(HYPOTHESIS)_" for i, h in enumerate(hyps)
    ) or "- (fill in) _(HYPOTHESIS)_"

    # Carry the grader's pre-registration reasoning (evidence / red flags) so the
    # author sees why it was approved and what to watch.
    notes = []
    for g in ("gate1", "gate2", "gate3"):
        d = idea.get(g) or {}
        if d.get("red_flags"):
            notes.append(f"- {g} red flags: " + "; ".join(d["red_flags"][:3]))
    notes_block = ("\n".join(notes)) if notes else "- (none recorded)"

    return f"""# PoC {n}: {title_from(idea['question'])}

| | |
|---|---|
| Status | planned |
| Verdict | — (pre-registration) |
| Authors | (your name) |
| Reviewers | none |
| Source idea | {src_line} |
| Registered | {today}, commit of this file before the first run |

## Question

{idea['question']}

## Why it matters here

{_bullets(idea.get('why_matters'))}

## Hypothesis

{hyp_block}

## Method

{idea.get('setup', '(fill in)')}

- Models: exact files, source URL, SHA-256, license.
- Tooling: versions or commits.
- Devices: host and target, OS build, memory, power state.
- Settings: what varies, what is held fixed.
- Measurements: what is recorded, how, how many repetitions.
- Data: CUAD (1,325 items / 397 contracts) unless stated otherwise.

## Decision rule

{idea.get('decision_rule', '(fill in — written before the first run)')}

Expected outcome at registration: **{idea.get('expected_outcome', '?')}** (confidence {int(float(idea.get('confidence', 0)) * 100)}%). This is a prior, not a result.

## Results

Link the raw files in `results/`. Every number tagged MEASURED, OBSERVED or INFERRED.

## Verdict

Adopt, reject or inconclusive, against the decision rule.

## Limits

What this does not show.

## Reproduce

Commands from a clean checkout.

---

<!-- Auto-scaffolded from the ideation pipeline (automated quality gate).
     Pre-registration notes from the grader — refine/verify before running: -->
{notes_block}
"""


def write_poc(idea: dict, number: int, dry_run: bool) -> Path:
    slug = slugify(idea["question"])
    folder = POC_ROOT / f"{number:03d}-{slug}"
    readme = folder / "README.md"
    content = render_readme(idea, number)
    if dry_run:
        print(f"\n----- [dry-run] {readme.relative_to(POC_ROOT.parent)} -----\n{content}")
    else:
        (folder / "results" / "raw").mkdir(parents=True, exist_ok=True)
        (folder / "results" / "raw" / ".gitkeep").touch()
        readme.write_text(content, encoding="utf-8")
        print(f"Scaffolded {readme.relative_to(POC_ROOT.parent)}")
    return folder


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a PoC folder from an approved idea.")
    ap.add_argument("--input", required=True, help="validated-ideas.jsonl (approved ideas)")
    ap.add_argument("--idea-id", help="scaffold only this idea_id")
    ap.add_argument("--all", action="store_true", help="scaffold every idea in the file")
    ap.add_argument("--dry-run", action="store_true", help="print the README, don't write")
    args = ap.parse_args()

    ideas = [json.loads(l) for l in open(args.input) if l.strip()]
    if args.idea_id:
        ideas = [i for i in ideas if i.get("idea_id") == args.idea_id] or ideas[:0]
    elif not args.all:
        ideas = ideas[:1]
    if not ideas:
        print("No matching approved ideas in input.")
        return 1

    n = next_poc_number()
    for offset, idea in enumerate(ideas):
        write_poc(idea, n + offset, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
