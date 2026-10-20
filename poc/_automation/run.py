#!/usr/bin/env python3
"""Ideation engine orchestrator — runs the full discover→gate→bank pipeline for a pack.

  python3 run.py --pack edge-ai-rag [--days N] [--dry-run]

Replaces run-weekly-scan.sh; selects a domain pack under packs/ and writes outputs to
scans/<pack>/<date>/. Stages live in engine/stages/ and each takes --pack. The idea-bank
write target is per-pack (pack.yaml `idea_bank`, relative to the pack dir).
"""
from __future__ import annotations
import argparse, subprocess, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGES = HERE / "engine" / "stages"
sys.path.insert(0, str(HERE / "engine"))
from pack import load_pack  # noqa: E402


def run_stage(script, pack, *cli, fatal=True):
    cmd = [sys.executable, str(STAGES / script), "--pack", pack, *cli]
    print(f"\n=== {script} ===")
    rc = subprocess.run(cmd).returncode
    if rc != 0 and fatal:
        print(f"[{script}] failed (rc={rc}); stopping."); sys.exit(rc)
    return rc


def count(p: Path) -> int:
    return sum(1 for _ in open(p)) if p.exists() else 0


def main():
    ap = argparse.ArgumentParser(description="Run the ideation pipeline for a domain pack")
    ap.add_argument("--pack", default="edge-ai-rag")
    ap.add_argument("--days", type=int, help="override last-scan window")
    ap.add_argument("--dry-run", action="store_true", help="Stage 6 writes nothing")
    args = ap.parse_args()

    pack = load_pack(args.pack)
    scan = pack.scans_dir / date.today().isoformat()
    scan.mkdir(parents=True, exist_ok=True)
    P = args.pack
    print(f"=== Ideation scan — pack={P} — {scan} ===")

    day_args = (["--days", str(args.days)] if args.days else [])
    run_stage("1-discover-research.py", P, "--output", f"{scan}/research-candidates.jsonl", *day_args)
    if count(scan / "research-candidates.jsonl") == 0:
        print("No candidates. Exiting."); return

    run_stage("2-filter-relevance.py", P, "--input", f"{scan}/research-candidates.jsonl",
              "--output", f"{scan}/relevant-research.jsonl")
    if count(scan / "relevant-research.jsonl") == 0:
        print("No relevant research. Exiting."); return

    run_stage("3-extract-ideas.py", P, "--input", f"{scan}/relevant-research.jsonl",
              "--output", f"{scan}/extracted-ideas.jsonl")
    run_stage("3b-synthesize-ideas.py", P, "--input", f"{scan}/relevant-research.jsonl",
              "--output", f"{scan}/synthesized-ideas.jsonl", fatal=False)

    all_ideas = scan / "all-ideas.jsonl"
    with open(all_ideas, "w") as out:
        for f in ("extracted-ideas.jsonl", "synthesized-ideas.jsonl"):
            if (scan / f).exists():
                out.write((scan / f).read_text())
    if count(all_ideas) == 0:
        print("No ideas. Exiting."); return
    print(f"Total candidates to gate: {count(all_ideas)}")

    run_stage("4-validate-quality-gate.py", P, "--input", str(all_ideas),
              "--output", f"{scan}/validated-ideas.jsonl")
    if count(scan / "validated-ideas.jsonl") == 0:
        print("No ideas passed the gates. Exiting."); return

    run_stage("5-prioritize-ideas.py", P, "--input", f"{scan}/validated-ideas.jsonl",
              "--output", f"{scan}/prioritized-ideas.jsonl")

    idea_bank = (pack.dir / pack.config.get("idea_bank", "IDEA-BANK.md")).resolve()
    bank_args = ["--input", f"{scan}/prioritized-ideas.jsonl", "--idea-bank", str(idea_bank),
                 "--summary", f"{scan}/weekly-summary.md"]
    if args.dry_run:
        bank_args.append("--dry-run")
    run_stage("6-update-idea-bank.py", P, *bank_args)

    if not args.dry_run:
        run_stage("1-discover-research.py", P, "--commit-date-only")
    print(f"\n=== Done. Results in {scan}/ ===")


if __name__ == "__main__":
    main()
