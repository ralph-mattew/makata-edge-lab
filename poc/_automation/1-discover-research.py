#!/usr/bin/env python3
"""
Stage 1: Research Discovery
Searches arXiv, HuggingFace, and blogs for recent papers/posts since last scan.
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict

import requests
import yaml

from _semantic import search_semantic
from _hf_models import search_hf_models

# Try to import arxiv library
try:
    import arxiv
    HAS_ARXIV = True
except ImportError:
    HAS_ARXIV = False
    print("Warning: arxiv library not installed. Install with: pip3 install arxiv")


def load_config() -> Dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_last_scan_date() -> datetime:
    """Get date of last scan, or 7 days ago if first run"""
    last_scan_file = Path(__file__).parent / "scans" / "last-scan-date.txt"
    if last_scan_file.exists():
        date_str = last_scan_file.read_text().strip()
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    else:
        # First run: scan last 7 days
        return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_scan_date(date: datetime):
    """Save date of successful scan"""
    last_scan_file = Path(__file__).parent / "scans" / "last-scan-date.txt"
    last_scan_file.write_text(date.isoformat())


def _seen_papers_file() -> Path:
    return Path(__file__).parent / "scans" / "seen-papers.txt"


def load_seen_papers() -> set:
    """IDs of papers surfaced in prior scans — so the same HuggingFace daily
    paper (or an arXiv revision) isn't re-extracted week after week."""
    f = _seen_papers_file()
    if not f.exists():
        return set()
    return {line.strip() for line in f.read_text().splitlines() if line.strip()}


def save_seen_papers(ids: set):
    _seen_papers_file().write_text("\n".join(sorted(ids)) + "\n")


def search_arxiv(config: Dict, start_date: datetime) -> List[Dict]:
    """Search arXiv for recent papers"""
    if not HAS_ARXIV or not config['sources']['arxiv']['enabled']:
        return []

    print(f"[arXiv] Searching papers since {start_date.date()}...")

    keywords = config['sources']['arxiv']['keywords']
    categories = config['sources']['arxiv']['categories']

    # Build search query: (keyword1 OR keyword2) AND (cat:cs.CL OR cat:cs.LG)
    keyword_query = ' OR '.join(f'"{kw}"' for kw in keywords)
    cat_query = ' OR '.join(f'cat:{cat}' for cat in categories)
    query = f'({keyword_query}) AND ({cat_query})'

    # Search arXiv
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=100,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    results = []
    for paper in client.results(search):
        # Filter by date
        if paper.published < start_date:
            continue

        results.append({
            "id": f"arxiv-{paper.entry_id.split('/')[-1]}",
            "source": "arxiv",
            "title": paper.title,
            "authors": [author.name for author in paper.authors],
            "date": paper.published.isoformat(),
            "abstract": paper.summary.replace('\n', ' ').strip(),
            "url": paper.entry_id,
            "pdf_url": paper.pdf_url
        })

    print(f"[arXiv] Found {len(results)} papers")
    return results


def search_huggingface_papers(config: Dict, start_date: datetime) -> List[Dict]:
    """Search HuggingFace Papers for recent papers"""
    if not config['sources']['huggingface']['enabled']:
        return []

    print(f"[HuggingFace] Searching papers since {start_date.date()}...")

    # HuggingFace Papers daily list
    url = "https://huggingface.co/api/daily_papers"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        papers = response.json()
    except Exception as e:
        print(f"[HuggingFace] Error: {e}")
        return []

    results = []
    keywords = [kw.lower() for kw in config['sources']['huggingface']['keywords']]

    for paper in papers:
        # Check if paper is recent
        pub_date_str = paper.get('publishedAt', '').split('T')[0]
        if not pub_date_str:
            continue
        pub_date = datetime.fromisoformat(pub_date_str).replace(tzinfo=timezone.utc)
        if pub_date < start_date:
            continue

        # Check if any keyword matches
        title_lower = paper.get('title', '').lower()
        abstract_lower = paper.get('summary', '').lower()
        if not any(kw in title_lower or kw in abstract_lower for kw in keywords):
            continue

        arxiv_id = paper.get('paper', {}).get('id', '')
        results.append({
            "id": f"hf-{arxiv_id or paper.get('id', '')}",
            "source": "huggingface",
            "title": paper.get('title', ''),
            "authors": [a.get('name', '') for a in paper.get('paper', {}).get('authors', [])],
            "date": paper.get('publishedAt', ''),
            "abstract": paper.get('summary', '').replace('\n', ' ').strip(),
            "url": f"https://huggingface.co/papers/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""
        })

    print(f"[HuggingFace] Found {len(results)} papers")
    return results


def search_blogs(config: Dict, start_date: datetime) -> List[Dict]:
    """Search configured blogs for recent posts"""
    if not config['sources']['blogs']['enabled']:
        return []

    print(f"[Blogs] Searching posts since {start_date.date()}...")

    # Simple implementation: just note that blog scanning is available
    # Full implementation would use feedparser or web scraping
    print("[Blogs] Note: Blog scanning requires feedparser. Skipping for now.")
    return []


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Discover recent research")
    parser.add_argument("--output", help="Output JSONL file")
    parser.add_argument("--days", type=int, help="Days to scan (overrides last scan date)")
    parser.add_argument("--commit-date-only", action="store_true",
                        help="Record today as the last-scan date and exit "
                             "(call this only after the full pipeline succeeds).")
    args = parser.parse_args()

    # The last-scan date is committed by the orchestrator *after* the whole run
    # succeeds — committing it here would permanently skip papers whenever a
    # later stage fails. This mode is that post-success commit.
    if args.commit_date_only:
        save_last_scan_date(datetime.now(timezone.utc))
        print("Recorded last-scan date.")
        return
    if not args.output:
        parser.error("--output is required unless --commit-date-only is given")

    config = load_config()

    # Determine start date
    if args.days:
        start_date = datetime.now(timezone.utc) - timedelta(days=args.days)
    else:
        start_date = get_last_scan_date()

    print(f"=== Stage 1: Research Discovery ===")
    print(f"Scanning from {start_date.date()} to {datetime.now(timezone.utc).date()}")

    # Search all sources
    candidates = []
    candidates.extend(search_arxiv(config, start_date))
    candidates.extend(search_huggingface_papers(config, start_date))
    candidates.extend(search_blogs(config, start_date))
    # Semantic arm: papers close in meaning to the lab's open problems, even when
    # they don't match the keyword list. Dedups against what we already have.
    kw_titles = {c['title'].lower().strip() for c in candidates}
    candidates.extend(search_semantic(config, start_date, existing_titles=kw_titles))
    # Model releases (new quantized embedders/rerankers/LLMs) — often more
    # immediately PoC-worthy for an edge lab than a paper.
    candidates.extend(search_hf_models(config, start_date))

    # Remove duplicates: within this run (same paper from multiple sources) and
    # across runs (papers already surfaced in a prior scan).
    seen_prior = load_seen_papers()
    seen_titles = {}
    unique_candidates = []
    cross_run_skipped = 0
    for candidate in candidates:
        title_normalized = candidate['title'].lower().strip()
        if title_normalized in seen_titles:
            continue
        seen_titles[title_normalized] = True
        if candidate['id'] in seen_prior:
            cross_run_skipped += 1
            continue
        unique_candidates.append(candidate)

    print(f"\n=== Results ===")
    print(f"Total candidates: {len(candidates)}")
    print(f"Skipped (seen in a prior scan): {cross_run_skipped}")
    print(f"Unique new candidates: {len(unique_candidates)}")

    # Record every id we surfaced this run so future scans skip them.
    save_seen_papers(seen_prior | {c['id'] for c in unique_candidates})

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        for candidate in unique_candidates:
            f.write(json.dumps(candidate) + '\n')

    print(f"Wrote {len(unique_candidates)} candidates to {output_path}")
    # NOTE: the last-scan date is intentionally NOT saved here. The orchestrator
    # commits it via `--commit-date-only` after Stage 6 succeeds, so a failure in
    # stages 2-6 doesn't permanently skip this window's papers.


if __name__ == "__main__":
    main()
