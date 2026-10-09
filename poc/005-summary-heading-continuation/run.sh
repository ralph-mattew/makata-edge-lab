#!/usr/bin/env bash
# PoC 005 host run. See README.md for the protocol.
# PoC 003's inputs and settings; this PoC's harness (PoC 003's plus the interventions in arms.json).
set -euo pipefail
cd "$(dirname "$0")"

MODEL=models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
MODEL_URL=https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/9eadc66189c7641e1ddd226b8267a9119b2ce2d4/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
MODEL_SHA=1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370
DATA_URL=https://zenodo.org/api/records/4595826/files/CUAD_v1.zip/content
DATA=data/CUAD_v1.zip
DATA_SHA=88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e
POC003=../003-qwen-sampler-stop-behavior
OUT=${OUT:-results/raw}   # replications: OUT=replications/<name>/results/raw

if [[ ! -f $MODEL ]]; then
  echo "missing $MODEL; download with:"
  echo "  mkdir -p models && curl -L -C - -o $MODEL $MODEL_URL"
  echo "(or copy PoC 003's file: it is the same model)"
  exit 1
fi
mkdir -p "$OUT" data

echo "checking model hash ..."
[[ $(shasum -a 256 "$MODEL" | cut -d' ' -f1) == "$MODEL_SHA" ]] || { echo "model hash mismatch"; exit 1; }

if [[ ! -f $DATA ]]; then
  echo "downloading CUAD v1 (106 MB) ..."
  curl -sSL -C - -o "$DATA" "$DATA_URL"
fi
echo "checking data hash ..."
[[ $(shasum -a 256 "$DATA" | cut -d' ' -f1) == "$DATA_SHA" ]] || { echo "data hash mismatch"; exit 1; }

echo "building the harness ..."
swift build -c release --package-path harness
BIN="$(swift build -c release --package-path harness --show-bin-path)/SamplerRun"

# Xylo's Summary prompt on PoC 003's 20 contracts, built by PoC 003's own prepare.py.
python3 "$POC003/prepare.py" "$DATA" "$OUT/inputs.jsonl"

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "harness=poc/005-summary-heading-continuation/harness"
  echo "llama_swift=$(python3 -c 'import json; p = [p for p in json.load(open("harness/Package.resolved"))["pins"] if p["identity"] == "llama.swift"][0]["state"]; print(p["version"], p["revision"])') (llama.cpp b8901)"
  echo "swift=$(swift --version 2>&1 | head -1)"
  echo "host=$(sysctl -n hw.model) $(sysctl -n machdep.cpu.brand_string) $(( $(sysctl -n hw.memsize) / 1073741824 ))GB"
  echo "os=$(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "power=$(pmset -g batt | head -1)"
  echo "model_sha256=$MODEL_SHA"
  echo "data_sha256=$DATA_SHA"
  echo "inputs_sha256=$(shasum -a 256 "$OUT/inputs.jsonl" | cut -d' ' -f1)"
} > "$OUT/conditions.txt"
cat "$OUT/conditions.txt"
if ! pmset -g batt | head -1 | grep -q "AC Power"; then
  echo "warning: not on AC power; the protocol requires it (see README, Method)"
fi

# Arms are interleaved inside each (document, seed), as in PoC 003.
cp arms.json "$OUT/arms.json"
# caffeinate keeps the host awake for the run (PoC 004's run slept on battery).
caffeinate -i "$BIN" --model "$MODEL" --arms "$OUT/arms.json" --inputs "$OUT/inputs.jsonl" \
  --out "$OUT/generations.jsonl" 2>&1 | tee "$OUT/harness.log"
echo "done; summarize with: python3 summarize.py $(dirname "$OUT")"
