#!/usr/bin/env bash
# PoC 008 host run. See README.md for the protocol.
set -euo pipefail
cd "$(dirname "$0")"
exec </dev/null   # nothing here reads stdin; a background run must not depend on its terminal

# PoC 006's harness, unchanged: its two programs take the prompts from an inputs file.
HARNESS=../006-doc-qa-fm-gemma-qwen/harness
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
VARIANTS="base rule rule-q"

for pair in "$GEMMA $GEMMA_URL" "$QWEN $QWEN_URL"; do
  set -- $pair
  if [[ ! -f $1 ]]; then
    echo "missing $1; download with:"
    echo "  mkdir -p models && curl -L -C - -o $1 $2"
    echo "(PoC 006 has both files; on APFS, cp -c clones them)"
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

echo "building PoC 006's harness ..."
swift build -c release --package-path "$HARNESS"
BIN="$(swift build -c release --package-path "$HARNESS" --show-bin-path)"

python3 prepare.py "$DATA" "$OUT"
cmp "$OUT/items.jsonl" ../006-doc-qa-fm-gemma-qwen/results/raw/items.jsonl \
  || { echo "items differ from PoC 006's"; exit 1; }
cmp arms.json ../006-doc-qa-fm-gemma-qwen/arms.json || { echo "arms differ from PoC 006's"; exit 1; }

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "harness=poc/006-doc-qa-fm-gemma-qwen/harness (unchanged)"
  echo "llama_swift=$(python3 -c 'import json; p = [p for p in json.load(open("'"$HARNESS"'/Package.resolved"))["pins"] if p["identity"] == "llama.swift"][0]["state"]; print(p["version"], p["revision"])') (llama.cpp b8901)"
  echo "swift=$(swift --version 2>&1 | head -1)"
  echo "host=$(sysctl -n hw.model) $(sysctl -n machdep.cpu.brand_string) $(( $(sysctl -n hw.memsize) / 1073741824 ))GB"
  echo "os=$(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "power=$(pmset -g batt | head -1)"
  echo "gemma_sha256=$GEMMA_SHA"
  echo "qwen_sha256=$QWEN_SHA"
  echo "data_sha256=$DATA_SHA"
  echo "items_sha256=$(shasum -a 256 "$OUT/items.jsonl" | cut -d' ' -f1)"
  for v in $VARIANTS; do
    echo "inputs_${v//-/_}_sha256=$(shasum -a 256 "$OUT/inputs-$v.jsonl" | cut -d' ' -f1)"
  done
} > "$OUT/conditions.txt"
cat "$OUT/conditions.txt"
if ! pmset -g batt | head -1 | grep -q "AC Power"; then
  echo "warning: not on AC power; the protocol requires it (see README, Method)"
fi
cp arms.json "$OUT/arms.json"

# One stage per (backend, variant), in this order: Gemma, Qwen, FoundationModels, each over base, rule
# and rule-q. The power source is logged before every stage. caffeinate keeps the host awake.
: > "$OUT/power.log"
for b in gemma-e2b qwen-1.5b fm; do
  for v in $VARIANTS; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $b $v $(pmset -g batt | head -1)" >> "$OUT/power.log"
    if [[ $b == fm ]]; then
      caffeinate -i "$BIN/FMQA" --arms "$OUT/arms.json" --arm fm --run 1 --inputs "$OUT/inputs-$v.jsonl" \
        --out "$OUT/gen-fm-$v.jsonl" 2>&1 | tee "$OUT/harness-fm-$v.log" | grep -v '^\['
    else
      caffeinate -i "$BIN/GGUFQA" --arms "$OUT/arms.json" --arm $b --inputs "$OUT/inputs-$v.jsonl" \
        --out "$OUT/gen-$b-$v.jsonl" 2>&1 | tee "$OUT/harness-$b-$v.log" | grep -v '^\['
    fi
  done
done
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) end $(pmset -g batt | head -1)" >> "$OUT/power.log"
echo "done; summarize with: python3 summarize.py $(dirname "$OUT")"
