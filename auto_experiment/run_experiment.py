#!/usr/bin/env python3
"""run_experiment.py — the RUN phase of the PR-gated auto-experiment loop.

Runs a merged experiment's MECHANISM through the deterministic harness, applies its
pre-registered `decision.json`, and records the verdict. NOTHING here is judged by a
model: the metric is the harness's recall@3 + bootstrap, the verdict is the no-eval
comparator, and the OUTCOMES `lesson` is templated from the numbers. Then it opens a
results PR for a final glance before the verdict flows back to the engine.

Run this only AFTER the proposal PR is merged (the human gate). Usage:
  python3 auto_experiment/run_experiment.py poc/039-some-slug
  python3 auto_experiment/run_experiment.py poc/039-some-slug --no-pr   # write results, no PR
  python3 auto_experiment/run_experiment.py poc/039-some-slug --dry-run # compute, print, write nothing
"""
from __future__ import annotations
import argparse, importlib.util, json, re, subprocess, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
from auto_experiment import harness  # noqa: E402


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=str(LAB), text=True, **kw)


def load_mechanism(poc_dir: Path):
    exp = poc_dir / "experiment.py"
    if not exp.exists():
        sys.exit(f"error: {exp} not found (merge the proposal PR first)")
    spec = importlib.util.spec_from_file_location(f"exp_{poc_dir.name}", exp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    if not (hasattr(mod, "candidate_scores") or hasattr(mod, "topk")):
        sys.exit("error: experiment.py exposes neither candidate_scores nor topk")
    return mod


def parse_spec(poc_dir: Path) -> dict:
    """Pull id/topic/question from the README (best-effort, deterministic)."""
    text = (poc_dir / "README.md").read_text() if (poc_dir / "README.md").exists() else ""
    m = re.match(r"(\d+)", poc_dir.name)
    pid = f"PoC-{m.group(1)}" if m else poc_dir.name
    title = next((l[1:].strip() for l in text.splitlines() if l.startswith("# ")), poc_dir.name)
    qm = re.search(r"##\s*Question\s*\n+(.+?)(?:\n##|\Z)", text, re.S)
    question = " ".join(qm.group(1).split()) if qm else ""
    return {"id": pid, "topic": title, "question": question}


def make_lesson(v: dict, metrics: dict, decision: dict) -> str:
    """A factual, templated summary of the numbers — NOT a model judgment."""
    b = (decision.get("baseline") or {}).get("recall_at_3")
    r = metrics["recall_at_3"]; lo, hi = metrics["ci95"]
    delta = f", Δ{r - b:+.2f} vs baseline {b}%" if isinstance(b, (int, float)) else ""
    def fmt(checks):
        return "; ".join(f"{c['var']}{c['op']}{c['value']} -> {c['actual']} "
                         f"({'pass' if c['pass'] else 'fail'})" for c in checks) or "none"
    parts = [f"Auto-run ({v['reason']}): verdict={v['verdict'].upper()}.",
             f"recall@3={r}% (CI {lo}-{hi}{delta}); hard_mean={metrics['hard_mean']}%, "
             f"weak_mean={metrics['weak_mean']}%, n={metrics['n_items']}.",
             f"adopt-checks: {fmt(v.get('adopt_checks', []))}.",
             f"reject-checks: {fmt(v.get('reject_checks', []))}."]
    if v.get("missing_vars"):
        parts.append(f"NEEDS-HUMAN: decision rule references vars the harness/experiment "
                     f"did not provide: {', '.join(v['missing_vars'])}.")
    return " ".join(parts)


def evaluate(poc_dir: Path, k: int) -> tuple[dict, dict, dict]:
    mech = load_mechanism(poc_dir)
    decision = json.loads((poc_dir / "decision.json").read_text())
    ctx = harness.load()
    if hasattr(mech, "candidate_scores"):
        metrics = harness.evaluate_scores(ctx, mech.candidate_scores, k)
    else:
        metrics = harness.evaluate(ctx, mech.topk, k)
    # merge any non-recall measurements the experiment reports (RAM, index size, …)
    measurements = {}
    if hasattr(mech, "measurements"):
        measurements = {k2: v2 for k2, v2 in (mech.measurements() or {}).items()}
    ns = {**metrics, **{k2: v2 for k2, v2 in measurements.items() if isinstance(v2, (int, float))}}
    v = harness.verdict(ns, decision)
    full = {**metrics, "measurements": measurements, "verdict": v,
            "decision": decision, "harness_baseline_recall_at_3": harness.RAW_BASELINE_RECALL}
    return full, metrics, decision


def write_results(poc_dir: Path, full: dict, metrics: dict, decision: dict) -> dict:
    spec = parse_spec(poc_dir)
    v = full["verdict"]
    (poc_dir / "results").mkdir(parents=True, exist_ok=True)
    (poc_dir / "results" / "metrics.json").write_text(json.dumps(full, indent=2))
    lesson = make_lesson(v, metrics, decision)
    entry = {"id": spec["id"], "topic": spec["topic"], "question": spec["question"],
             "verdict": v["verdict"], "lesson": lesson}
    with open(LAB / "poc" / "OUTCOMES.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    # best-effort README stamp (Verdict + Status cells)
    rm = poc_dir / "README.md"
    if rm.exists():
        t = rm.read_text()
        t = re.sub(r"(\|\s*Verdict\s*\|)[^|]*(\|)", rf"\1 {v['verdict']} \2", t, count=1)
        t = re.sub(r"(\|\s*Status\s*\|)[^|]*(\|)", rf"\1 host run ({date.today()}) \2", t, count=1)
        rm.write_text(t)
    return entry


def open_pr(poc_dir: Path, entry: dict, base: str) -> None:
    slug = poc_dir.name; branch = f"results/{slug}"
    poc_rel = poc_dir.relative_to(LAB).as_posix()
    run(["git", "checkout", "-B", branch])
    run(["git", "add", "--", poc_rel, "poc/OUTCOMES.jsonl"])   # only this poc + the ledger
    msg = (f"results({slug}): {entry['verdict']} — deterministic harness verdict\n\n"
           f"{entry['lesson']}\n\n"
           "Verdict computed by auto_experiment/harness.py (recall@3 + bootstrap + the\n"
           "pre-registered decision.json). No model judged this result.\n\n"
           "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>")
    run(["git", "commit", "-m", msg])
    run(["git", "push", "-u", "origin", branch, "--force-with-lease"])
    body = (f"**Deterministic result** for `{poc_rel}`.\n\n"
            f"**Verdict: `{entry['verdict']}`**\n\n> {entry['lesson']}\n\n"
            "Computed by `auto_experiment/harness.py` (recall@3 + contract bootstrap) applying "
            "the pre-registered `decision.json`. No model judged this — merge to accept the "
            "verdict into the ledger the engine imports.\n\n"
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)")
    pr = run(["gh", "pr", "create", "--base", base, "--head", branch,
              "--title", f"results({slug}): {entry['verdict']}", "--body", body],
             capture_output=True)
    print(pr.stdout.strip() or pr.stderr.strip())


def main():
    ap = argparse.ArgumentParser(description="Run a merged experiment and record its verdict.")
    ap.add_argument("poc_dir", help="path to the merged PoC dir, e.g. poc/039-some-slug")
    ap.add_argument("--k", type=int, default=3, help="top-k for recall (default 3)")
    ap.add_argument("--base", default="main", help="PR base branch (default main)")
    ap.add_argument("--dry-run", action="store_true", help="compute + print; write nothing")
    ap.add_argument("--no-pr", action="store_true", help="write results + ledger; no PR")
    args = ap.parse_args()

    poc_dir = (LAB / args.poc_dir).resolve() if not Path(args.poc_dir).is_absolute() else Path(args.poc_dir)
    full, metrics, decision = evaluate(poc_dir, args.k)
    v = full["verdict"]
    print(f"[{poc_dir.name}] verdict={v['verdict']} ({v['reason']})  "
          f"recall@3={metrics['recall_at_3']}%  hard={metrics['hard_mean']}%")
    if args.dry_run:
        print(json.dumps(v, indent=2)); return
    entry = write_results(poc_dir, full, metrics, decision)
    print("ledger:", json.dumps(entry)[:200])
    if args.no_pr:
        print("done (--no-pr): results written, no PR opened."); return
    open_pr(poc_dir, entry, args.base)


if __name__ == "__main__":
    main()
