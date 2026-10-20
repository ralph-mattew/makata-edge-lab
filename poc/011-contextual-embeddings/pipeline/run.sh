#!/usr/bin/env bash
# PoC 011 pipeline orchestrator. Generated contextual retrieval, end to end.
# Stages 1-2 are verified; stage 3's recall scorer is provisional (see README).
set -euo pipefail
cd "$(dirname "$0")"

QWEN="${QWEN_GGUF:-../../006-doc-qa-fm-gemma-qwen/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf}"
GEMMA="${GEMMA_GGUF:-../../006-doc-qa-fm-gemma-qwen/models/google_gemma-4-E2B-it-Q4_K_M.gguf}"
LIMIT="${LIMIT:-0}"   # 0 = full corpus; set small for a scoped run

echo "== Stage 1: generate contexts =="
llama-server -m "$QWEN" -c 8192 -ngl 99 --host 127.0.0.1 --port 8099 --log-disable >/tmp/p011-qwen.log 2>&1 & QPID=$!
llama-server -m "$GEMMA" -c 8192 -ngl 99 --host 127.0.0.1 --port 8098 --log-disable >/tmp/p011-gemma.log 2>&1 & GPID=$!
trap 'kill $QPID $GPID 2>/dev/null || true' EXIT
for p in 8099 8098; do for _ in $(seq 1 90); do curl -s "http://127.0.0.1:$p/health" 2>/dev/null | grep -q ok && break; sleep 1; done; done
python3 01-generate-contexts.py --limit "$LIMIT"
kill $QPID $GPID 2>/dev/null || true; trap - EXIT

echo "== Stage 2: embed (queries + each condition) =="
# NOTE: llama-server splits context across --parallel slots, so per-input context
# is n_ctx / parallel. Use -c 16384 --parallel 8 => 2048 tokens/input (matches
# PoC 007); a bare -c 2048 gives only 256/input and 400s on long chunks.
llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 --host 127.0.0.1 --port 8090 --log-disable >/tmp/p011-emb.log 2>&1 & EPID=$!
trap 'kill $EPID 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do curl -s http://127.0.0.1:8090/health 2>/dev/null | grep -q ok && break; sleep 1; done
for cond in queries standard naive ctx_qwen ctx_gemma; do
  python3 02-embed.py --condition "$cond" --batch 8
done
kill $EPID 2>/dev/null || true; trap - EXIT

echo "== Stage 3: retrieve + recall (PROVISIONAL scorer) =="
echo "Validate standard first:"
python3 03-retrieve-score.py --condition standard
for cond in naive ctx_qwen ctx_gemma; do
  python3 03-retrieve-score.py --condition "$cond"
done
