#!/usr/bin/env python3
"""implement.py — the PROPOSE phase of the PR-gated auto-experiment loop.

Takes a promoted PoC spec (`poc/NNN-slug/README.md`) and asks *headless Claude Code*
(`claude -p`) to write the experiment MECHANISM + a machine-readable `decision.json`,
then opens a **proposal PR**. This is the same Claude Code you'd drive by hand — so the
code is at your usual bar — just unattended and captured in a reviewable PR.

What this does NOT do: run the experiment or compute a verdict. That happens only after
YOU merge the PR (run_experiment.py, next daily tick). Claude Code writes only the
mechanism; the deterministic harness owns the metric and the verdict. See README.md.

Usage:
  python3 auto_experiment/implement.py poc/039-some-slug          # generate + open PR
  python3 auto_experiment/implement.py poc/039-some-slug --no-pr  # generate on a branch, no PR
  python3 auto_experiment/implement.py poc/039-some-slug --print-prompt   # inspect only
  python3 auto_experiment/implement.py poc/039-some-slug --dry-run        # show the claude cmd
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent

PROMPT = """You are implementing a single, self-contained research experiment for the \
makata-edge-lab, exactly as a careful engineer would. Work ONLY inside the directory \
`{poc_rel}/`. Do not modify any file outside it (especially not `auto_experiment/harness.py`).

## The spec to implement (its README)
{spec}

## The deterministic harness you must build on (read it, do not edit it)
`auto_experiment/harness.py` loads the CUAD corpus and owns the metric + verdict. Your job \
is ONLY to supply the retrieval/ranking MECHANISM. Contract:

- Create `{poc_rel}/experiment.py`. At the top, make the harness importable:
      import sys; from pathlib import Path
      sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
      from auto_experiment import harness
- Expose a mechanism, preferring the scores form:
      def candidate_scores(ctx, item, idxs):   # -> list[float] aligned to idxs
  or, if you must control the final set directly:
      def topk(ctx, item, idxs, k):            # -> list[int] of GLOBAL row indices from idxs
  `ctx` is harness.Corpus: use ctx.cvec (chunk vectors), ctx.qvec[item['qa_id']] (query \
  vector), ctx.rows[i]['chunk'] (chunk text), item['question']/['category'], and the \
  primitives ctx.cosine/ctx.bm25/ctx.norm01/ctx.hybrid_scores.
- If your idea uses NEW query/sub-query/template text (not the item's own question), you MUST \
  embed it with `ctx.embed_queries([...], cache=Path(__file__).parent/'results/raw/emb-cache.jsonl')` \
  so the vectors share the same space as ctx.qvec/ctx.cvec. NEVER reuse the question vector for \
  different query text and NEVER invent vectors — a reused/invented vector silently neuters the \
  semantic signal and invalidates the test. (This needs the local embed server running; if it \
  is down, the run will fail loudly rather than fake it, which is correct.)
- If your idea needs a different CHUNK embedder/quantization, that is likely out of scope for this \
  harness (it would need re-embedding the whole corpus with another model); say so in a comment \
  rather than approximate it.
- Keep import side-effect free: do heavy work inside the functions / under `if __name__`, \
  never at import time (the PR check imports your module).
- Add a `--smoke` mode under `if __name__ == '__main__'` that runs on a SMALL slice and \
  prints the mechanism's top-k for a couple of items, so a reviewer can sanity-check it. Do \
  NOT compute recall, CIs, or a verdict — the harness does that after merge.

## Non-recall measurements (only if the decision rule needs them)
If the decision rule references numbers the harness cannot compute (RAM, index size, \
latency), also expose `def measurements() -> dict` returning them with a short comment on \
HOW each was measured. If a number genuinely requires a physical device you cannot access \
here, return it as null — the verdict will then come back `needs-human` rather than guess.

## The pre-registered decision rule — `{poc_rel}/decision.json`
Translate the README's "Decision rule" into this exact schema (numbers only, no prose logic):
  {{
    "baseline": {{ "recall_at_3": 61.8 }},                 // enables *_delta vars; set the real baseline
    "adopt_if_all": [ {{"var": "...", "op": ">=", "value": 0, "note": "..."}} ],
    "reject_if_any": [ {{"var": "...", "op": "<", "value": 0, "note": "..."}} ]
  }}
Available vars: recall_at_3, hard_mean, weak_mean, n_items, any *_delta of those vs \
baseline (e.g. recall_at_3_delta, hard_mean_delta), per-category as `cat::<Category>`, and \
any key your `measurements()` returns. ops: >=, >, <=, <, ==, !=. The rule must faithfully \
encode the README's ADOPT / REJECT thresholds; INCONCLUSIVE is the implicit else.

## Integrity constraints (these are the point — do not violate)
- Never read the gold answer: `ctx.gold` and any gold span are OFF LIMITS to the mechanism. \
  `item` deliberately has no gold field. Ranking must use only query-time information.
- Do not compute the metric or the verdict anywhere; do not hardcode expected results.
- Touch only `{poc_rel}/`.

When done, briefly confirm the two files exist and that `experiment.py` imports cleanly.
"""


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=str(LAB), text=True, **kw)


def slug_of(poc_dir: Path) -> str:
    return poc_dir.name


def build_prompt(poc_dir: Path) -> str:
    readme = (poc_dir / "README.md")
    if not readme.exists():
        sys.exit(f"error: no README.md in {poc_dir} (promote an inbox stub first)")
    poc_rel = poc_dir.relative_to(LAB).as_posix()
    return PROMPT.format(poc_rel=poc_rel, spec=readme.read_text())


def dirty_paths() -> set[str]:
    """Paths currently dirty/untracked (the inbox is normally a firehose of untracked dirs)."""
    out = run(["git", "status", "--porcelain"], capture_output=True).stdout.splitlines()
    return {l[3:] for l in out if l.strip()}


def verify(poc_dir: Path, baseline: set[str]) -> None:
    """Fail loudly unless the generated output honors the contract and stayed in scope.
    `baseline` is the set of paths already dirty BEFORE Claude Code ran, so pre-existing
    untracked siblings (other inbox proposals) don't read as strays — only NEW out-of-scope
    changes do."""
    poc_rel = poc_dir.relative_to(LAB).as_posix()
    # 1. only NEW changes under the poc dir (harness + everything else untouched)
    stray = [p for p in dirty_paths() - baseline if not p.startswith(poc_rel + "/")]
    if stray:
        sys.exit("error: Claude Code changed files OUTSIDE the poc dir — aborting:\n"
                 + "\n".join(sorted(stray)))
    # 2. required files exist and parse
    exp, dec = poc_dir / "experiment.py", poc_dir / "decision.json"
    if not exp.exists(): sys.exit(f"error: {exp} was not created")
    if not dec.exists(): sys.exit(f"error: {dec} was not created")
    d = json.loads(dec.read_text())
    if not d.get("adopt_if_all") and not d.get("reject_if_any"):
        sys.exit("error: decision.json has no adopt_if_all / reject_if_any conditions")
    # 3. experiment imports cleanly and exposes a mechanism (no gold access at import)
    probe = (f"import sys; sys.path.insert(0, {str(LAB)!r}); "
             f"import importlib.util as u; "
             f"s=u.spec_from_file_location('exp', {str(exp)!r}); m=u.module_from_spec(s); "
             f"s.loader.exec_module(m); "
             f"assert hasattr(m,'candidate_scores') or hasattr(m,'topk'), "
             f"'experiment.py must expose candidate_scores or topk'; "
             f"print('mechanism OK:', [n for n in ('candidate_scores','topk','measurements') if hasattr(m,n)])")
    r = run(["python3", "-c", probe], capture_output=True)
    if r.returncode != 0:
        sys.exit("error: experiment.py failed import/contract check:\n" + r.stderr)
    print("verify:", r.stdout.strip())


def open_pr(poc_dir: Path, base: str) -> None:
    slug = slug_of(poc_dir); branch = f"exp/{slug}"
    poc_rel = poc_dir.relative_to(LAB).as_posix()
    run(["git", "checkout", "-B", branch])
    run(["git", "add", "--", poc_rel])            # ONLY this poc dir (inbox hygiene)
    msg = (f"exp({slug}): auto-implemented experiment mechanism + decision rule\n\n"
           "Generated by headless Claude Code (auto_experiment/implement.py). The mechanism\n"
           "and decision.json are proposals for review; the deterministic harness computes\n"
           "the verdict only after this PR is merged.\n\n"
           "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>")
    run(["git", "commit", "-m", msg])
    run(["git", "push", "-u", "origin", branch, "--force-with-lease"])
    body = (f"**Auto-implemented experiment** for `{poc_rel}` (headless Claude Code).\n\n"
            "## Review checklist\n"
            "- [ ] `experiment.py` mechanism is sound and uses only query-time info "
            "(no `ctx.gold`, no gold span)\n"
            "- [ ] `decision.json` faithfully encodes the README's **Decision rule**\n"
            "- [ ] any `measurements()` are honestly obtained (device numbers not fabricated)\n\n"
            "## What happens on merge\n"
            "The next daily tick runs `run_experiment.py`: the **deterministic harness** "
            "computes recall@3 + bootstrap and applies `decision.json` to produce the "
            "adopt/reject verdict. Claude Code wrote the mechanism; it does **not** judge it.\n\n"
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)")
    pr = run(["gh", "pr", "create", "--base", base, "--head", branch,
              "--title", f"exp({slug}): proposed experiment for review", "--body", body],
             capture_output=True)
    print(pr.stdout.strip() or pr.stderr.strip())


def main():
    ap = argparse.ArgumentParser(description="Propose an auto-implemented experiment as a PR.")
    ap.add_argument("poc_dir", help="path to a promoted PoC dir, e.g. poc/039-some-slug")
    ap.add_argument("--model", default="", help="claude model alias/id; empty uses the CLI default")
    ap.add_argument("--base", default="main", help="PR base branch (default: main)")
    ap.add_argument("--print-prompt", action="store_true", help="print the prompt and exit")
    ap.add_argument("--dry-run", action="store_true", help="show the claude command, do not run")
    ap.add_argument("--no-pr", action="store_true", help="generate + verify only; no branch/PR")
    args = ap.parse_args()

    poc_dir = (LAB / args.poc_dir).resolve() if not Path(args.poc_dir).is_absolute() else Path(args.poc_dir)
    prompt = build_prompt(poc_dir)
    if args.print_prompt:
        print(prompt); return

    claude_cmd = ["claude", "-p", prompt,
                  "--permission-mode", "acceptEdits",
                  "--allowedTools", "Read", "Write", "Edit", "Bash(python3:*)",
                  "--add-dir", str(LAB),
                  "--output-format", "text"]
    if args.model:
        claude_cmd[3:3] = ["--model", args.model]
    if args.dry_run:
        print("DRY RUN — would run headless Claude Code in", LAB, "\n")
        print(" ".join(claude_cmd[:1] + ["-p", "<prompt>"] + claude_cmd[3:]))
        return

    print(f"implement: invoking headless Claude Code for {poc_dir.name} …")
    baseline = dirty_paths()   # snapshot pre-existing strays (untracked inbox siblings, etc.)
    r = run(claude_cmd)
    if r.returncode != 0:
        sys.exit(f"error: claude exited {r.returncode}")
    verify(poc_dir, baseline)
    if args.no_pr:
        print("done (--no-pr): changes left in the working tree for review.")
        return
    open_pr(poc_dir, args.base)


if __name__ == "__main__":
    main()
