#!/bin/bash
# Weekly research scan entry point (cron). Thin wrapper over the engine orchestrator.
# Pack-agnostic: pass --pack to scan a different domain (default: edge-ai-rag).
#   ./run-weekly-scan.sh                      # edge-ai-rag
#   ./run-weekly-scan.sh --pack agentic-research
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/run.py" "$@"
