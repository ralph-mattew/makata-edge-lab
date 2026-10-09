#!/usr/bin/env bash
# PoC 004 host run. See README.md for the protocol.
# Reuses PoC 003's harness unchanged (same source, same llama.swift pin), once per prompt variant.
set -euo pipefail
cd "$(dirname "$0")"

MODEL=models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
MODEL_URL=https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/9eadc66189c7641e1ddd226b8267a9119b2ce2d4/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
MODEL_SHA=1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370
DATA_URL=https://zenodo.org/api/records/4595826/files/CUAD_v1.zip/content
DATA=data/CUAD_v1.zip
DATA_SHA=88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e
HARNESS=../003-qwen-sampler-stop-behavior/harness
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

echo "building PoC 003's harness ..."
swift build -c release --package-path "$HARNESS"
BIN="$(swift build -c release --package-path "$HARNESS" --show-bin-path)/SamplerRun"

python3 prepare.py "$DATA" "$OUT"

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "harness=poc/003-qwen-sampler-stop-behavior/harness (unchanged)"
  echo "llama_swift=$(python3 -c 'import json; p = [p for p in json.load(open("'"$HARNESS"'/Package.resolved"))["pins"] if p["identity"] == "llama.swift"][0]["state"]; print(p["version"], p["revision"])') (llama.cpp b8901)"
  echo "swift=$(swift --version 2>&1 | head -1)"
  echo "host=$(sysctl -n hw.model) $(sysctl -n machdep.cpu.brand_string) $(( $(sysctl -n hw.memsize) / 1073741824 ))GB"
  echo "os=$(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "power=$(pmset -g batt | head -1)"
  echo "model_sha256=$MODEL_SHA"
  echo "data_sha256=$DATA_SHA"
  for v in xylo no-end-line; do
    echo "inputs_${v}_sha256=$(shasum -a 256 "$OUT/inputs-$v.jsonl" | cut -d' ' -f1)"
  done
} > "$OUT/conditions.txt"
cat "$OUT/conditions.txt"

# One harness run per prompt variant; inside a run, arms are interleaved per (document, seed).
: > "$OUT/harness.log"
for v in xylo no-end-line; do
  python3 -c 'import json, sys; json.dump([a for a in json.load(open("arms.json")) if a["prompt"] == sys.argv[1]], open(sys.argv[2], "w"), indent=2)' \
    "$v" "$OUT/arms-$v.json"
  "$BIN" --model "$MODEL" --arms "$OUT/arms-$v.json" --inputs "$OUT/inputs-$v.jsonl" \
    --out "$OUT/generations-$v.jsonl" 2>&1 | tee -a "$OUT/harness.log"
done
echo "done; summarize with: python3 summarize.py $(dirname "$OUT")"
