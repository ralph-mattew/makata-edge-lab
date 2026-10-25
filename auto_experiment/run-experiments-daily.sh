#!/bin/bash
# Daily PR-gated auto-experiment runner for makata-edge-lab (launchd/cron). Two phases:
#
#   Phase B (run):     for each MERGED experiment (experiment.py + decision.json on main, no
#                      results yet, no open results PR) -> run the deterministic harness and open
#                      a results PR with the verdict.
#   Phase A (propose): for up to --max-propose PROMOTED specs (poc/NNN with Status: planned, no
#                      experiment.py yet, no open proposal PR) -> headless Claude Code implements
#                      the mechanism + decision rule and opens a proposal PR.
#
# Your merges are the gates: promote (what to try) -> merge proposal (code/rule ok) -> merge
# results (accept the numbers). Nothing is model-judged; the verdict is harness.py. See README.md.
#
#   ./auto_experiment/run-experiments-daily.sh [--max-propose 1]
set -uo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"          # lab root
cd "$DIR"
MAX_PROPOSE=1
while [ $# -gt 0 ]; do case "$1" in
  --max-propose) MAX_PROPOSE="$2"; shift 2;; *) shift;; esac; done

TODAY="$(date +%Y-%m-%d)"
LOGDIR="$DIR/auto_experiment/daily-logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/$TODAY.log"
LOCK="$DIR/.autoexp.lock"

[ -f "$DIR/STOP" ] && { echo "[$(date)] STOP sentinel present; exiting" >> "$LOG"; exit 0; }
# Single-flight: a run (esp. Claude Code) can take many minutes.
mkdir "$LOCK" 2>/dev/null || { echo "[$(date)] another run holds the lock; exiting" >> "$LOG"; exit 0; }
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

pr_open() { gh pr list --head "$1" --state open --json number --jq 'length' 2>/dev/null || echo 0; }

{
  echo "============================================================"
  echo "[$(date)] auto-experiment daily start — max_propose=$MAX_PROPOSE"
  git checkout --quiet main 2>&1 || true
  git pull --quiet --rebase --autostash origin main 2>&1 || echo "WARN: pull failed (continuing)"

  # --- Phase B: run merged-but-unrun experiments (the human already merged the proposal PR) ---
  for d in poc/[0-9]*/; do
    d="${d%/}"
    [ -f "$d/experiment.py" ] && [ -f "$d/decision.json" ] || continue
    [ -f "$d/results/metrics.json" ] && continue
    slug="$(basename "$d")"
    if [ "$(pr_open "results/$slug")" != "0" ]; then echo "[B] results/$slug PR already open — skip"; continue; fi
    echo "[B] RUN $d"
    git checkout --quiet main
    python3 auto_experiment/run_experiment.py "$d" --base main 2>&1 || echo "WARN: run $d failed"
    git checkout --quiet main
  done

  # --- Phase A: propose new experiments from promoted, un-implemented specs ---
  n=0
  for d in poc/[0-9]*/; do
    d="${d%/}"
    [ "$n" -ge "$MAX_PROPOSE" ] && break
    [ -f "$d/README.md" ] || continue
    [ -f "$d/experiment.py" ] && continue
    grep -qiE '^\|[[:space:]]*Status[[:space:]]*\|[[:space:]]*planned' "$d/README.md" || continue
    slug="$(basename "$d")"
    if [ "$(pr_open "exp/$slug")" != "0" ]; then echo "[A] exp/$slug PR already open — skip"; continue; fi
    echo "[A] PROPOSE $d"
    git checkout --quiet main
    python3 auto_experiment/implement.py "$d" --base main 2>&1 || echo "WARN: implement $d failed"
    git checkout --quiet main
    n=$((n + 1))
  done

  echo "[$(date)] auto-experiment daily done (proposed=$n)"
} >> "$LOG" 2>&1
