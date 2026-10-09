#!/usr/bin/env bash
# PoC 006 host run. See README.md for the protocol.
set -euo pipefail
cd "$(dirname "$0")"
exec </dev/null   # nothing here reads stdin; a background run must not depend on its terminal

GEMMA=models/google_gemma-4-E2B-it-Q4_K_M.gguf
GEMMA_URL=https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF/resolve/81012ba3538e061d5ee003f11f25335b17f82e2d/google_gemma-4-E2B-it-Q4_K_M.gguf
GEMMA_SHA=923c4c86177d2ee173a7f5b4fa3d0ac65f5962ab15e6d6a5bc250aec4fd7bf7e
QWEN=models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
QWEN_URL=https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/9eadc66189c7641e1ddd226b8267a9119b2ce2d4/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
QWEN_SHA=1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370
DATA_URL=https://zenodo.org/api/records/4595826/files/CUAD_v1.zip/content
DATA=data/CUAD_v1.zip
DATA_SHA=88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e
OUT=${OUT:-results/raw}   # replications: OUT=replications/<name>/results/raw

for pair in "$GEMMA $GEMMA_URL" "$QWEN $QWEN_URL"; do
  set -- $pair
  if [[ ! -f $1 ]]; then
    echo "missing $1; download with:"
    echo "  mkdir -p models && curl -L -C - -o $1 $2"
    echo "(PoC 001 has the Gemma file and PoC 003 the Qwen file; on APFS, cp -c clones them)"
    exit 1
  fi
done
mkdir -p "$OUT" data

echo "checking model hashes ..."
[[ $(shasum -a 256 "$GEMMA" | cut -d' ' -f1) == "$GEMMA_SHA" ]] || { echo "Gemma hash mismatch"; exit 1; }
[[ $(shasum -a 256 "$QWEN" | cut -d' ' -f1) == "$QWEN_SHA" ]] || { echo "Qwen hash mismatch"; exit 1; }

if [[ ! -f $DATA ]]; then
  echo "downloading CUAD v1 (106 MB) ..."
  curl -sSL -C - -o "$DATA" "$DATA_URL"
fi
echo "checking data hash ..."
[[ $(shasum -a 256 "$DATA" | cut -d' ' -f1) == "$DATA_SHA" ]] || { echo "data hash mismatch"; exit 1; }

echo "building the harness ..."
swift build -c release --package-path harness
BIN="$(swift build -c release --package-path harness --show-bin-path)"

python3 prepare.py "$DATA" "$OUT"

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "harness=poc/006-doc-qa-fm-gemma-qwen/harness"
  echo "llama_swift=$(python3 -c 'import json; p = [p for p in json.load(open("harness/Package.resolved"))["pins"] if p["identity"] == "llama.swift"][0]["state"]; print(p["version"], p["revision"])') (llama.cpp b8901)"
  echo "swift=$(swift --version 2>&1 | head -1)"
  echo "host=$(sysctl -n hw.model) $(sysctl -n machdep.cpu.brand_string) $(( $(sysctl -n hw.memsize) / 1073741824 ))GB"
  echo "os=$(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "power=$(pmset -g batt | head -1)"
  echo "gemma_sha256=$GEMMA_SHA"
  echo "qwen_sha256=$QWEN_SHA"
  echo "data_sha256=$DATA_SHA"
  echo "items_sha256=$(shasum -a 256 "$OUT/items.jsonl" | cut -d' ' -f1)"
  echo "inputs_sha256=$(shasum -a 256 "$OUT/inputs.jsonl" | cut -d' ' -f1)"
} > "$OUT/conditions.txt"
cat "$OUT/conditions.txt"
if ! pmset -g batt | head -1 | grep -q "AC Power"; then
  echo "warning: not on AC power; the protocol requires it (see README, Method)"
fi
cp arms.json "$OUT/arms.json"

# Run 1 of every arm, then run 2 (Gemma and Qwen with seed 2; FoundationModels again).
# caffeinate keeps the host awake for the whole run.
for run in 1 2; do
  if [[ $run == 2 ]]; then
    python3 -c 'import json; a = json.load(open("arms.json")); [x.update(seed=2) for x in a if "seed" in x]; json.dump(a, open("'"$OUT"'/arms-run2.json", "w"), indent=2)'
    ARMS="$OUT/arms-run2.json"
  else
    ARMS="$OUT/arms.json"
  fi
  for arm in gemma-e2b qwen-1.5b; do
    caffeinate -i "$BIN/GGUFQA" --arms "$ARMS" --arm $arm --inputs "$OUT/inputs.jsonl" \
      --out "$OUT/gen-$arm-run$run.jsonl" 2>&1 | tee "$OUT/harness-$arm-run$run.log" | grep -v '^\['
  done
  caffeinate -i "$BIN/FMQA" --arms "$ARMS" --arm fm --run $run --inputs "$OUT/inputs.jsonl" \
    --out "$OUT/gen-fm-run$run.jsonl" 2>&1 | tee "$OUT/harness-fm-run$run.log" | grep -v '^\['
done
echo "done; summarize with: python3 summarize.py $(dirname "$OUT")"
