#!/usr/bin/env bash
# PoC 009 host run. See README.md for the protocol.
set -euo pipefail
cd "$(dirname "$0")"
exec </dev/null   # nothing here reads stdin; a background run must not depend on its terminal

# PoC 006's harness, unchanged: GGUFQA takes the prompts from an inputs file.
HARNESS=../006-doc-qa-fm-gemma-qwen/harness
QWEN=models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
QWEN_URL=https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/9eadc66189c7641e1ddd226b8267a9119b2ce2d4/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
QWEN_SHA=1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370
DATA_URL=https://zenodo.org/api/records/4595826/files/CUAD_v1.zip/content
DATA=data/CUAD_v1.zip
DATA_SHA=88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e
OUT=${OUT:-results/raw}   # replications: OUT=replications/<name>/results/raw
CONDITIONS="eg-k3 eg-k1 eg-k5 nl-k3 nl-k5"
RUN2="eg-k3 eg-k5"
LIMIT_ARGS=()
[[ -n ${LIMIT:-} ]] && LIMIT_ARGS=(--limit "$LIMIT")   # smoke tests only; the registered run has none
RAW7=../007-embedding-retrieval-recall/results/raw

if [[ ! -f $QWEN ]]; then
  echo "missing $QWEN; download with:"
  echo "  mkdir -p models && curl -L -C - -o $QWEN $QWEN_URL"
  echo "(PoC 006 has the file; on APFS, cp -c clones it)"
  exit 1
fi
mkdir -p "$OUT" data

echo "checking model hash ..."
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
cmp arms.json ../006-doc-qa-fm-gemma-qwen/arms.json || { echo "arms differ from PoC 006's"; exit 1; }
python3 - "$OUT" <<'EOF'
import json, sys
arms = json.load(open("arms.json"))
for a in arms:
    if a["backend"] == "gguf":
        a["seed"] = 2
json.dump(arms, open(sys.argv[1] + "/arms-run2.json", "w"), indent=2)
EOF

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "harness=poc/006-doc-qa-fm-gemma-qwen/harness (unchanged)"
  echo "llama_swift=$(python3 -c 'import json; p = [p for p in json.load(open("'"$HARNESS"'/Package.resolved"))["pins"] if p["identity"] == "llama.swift"][0]["state"]; print(p["version"], p["revision"])') (llama.cpp b8901)"
  echo "swift=$(swift --version 2>&1 | head -1)"
  echo "host=$(sysctl -n hw.model) $(sysctl -n machdep.cpu.brand_string) $(( $(sysctl -n hw.memsize) / 1073741824 ))GB"
  echo "os=$(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "power=$(pmset -g batt | head -1)"
  echo "qwen_sha256=$QWEN_SHA"
  echo "data_sha256=$DATA_SHA"
  for f in items chunks-index scores-kw scores-nl scores-eg; do
    echo "poc007_${f//-/_}_sha256=$(shasum -a 256 "$RAW7/$f.jsonl" | cut -d' ' -f1)"
  done
  echo "items_sha256=$(shasum -a 256 "$OUT/items.jsonl" | cut -d' ' -f1)"
  for c in $CONDITIONS; do
    echo "selection_${c//-/_}_sha256=$(shasum -a 256 "$OUT/selection-$c.jsonl" | cut -d' ' -f1)"
    echo "inputs_${c//-/_}_sha256=$(shasum -a 256 "$OUT/inputs-$c.jsonl" | cut -d' ' -f1)"
  done
} > "$OUT/conditions.txt"
cat "$OUT/conditions.txt"
if ! pmset -g batt | head -1 | grep -q "AC Power"; then
  echo "warning: not on AC power; the protocol requires it (see README, Method)"
fi
cp arms.json "$OUT/arms.json"

# One stage per condition and run. Run 1 is the result; run 2 repeats two conditions with seed 2.
# The power source is logged before every stage. caffeinate keeps the host awake.
: > "$OUT/power.log"
stage() {   # run, arms file, condition
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) run$1 $3 $(pmset -g batt | head -1)" >> "$OUT/power.log"
  caffeinate -i "$BIN/GGUFQA" --arms "$2" --arm qwen-1.5b --inputs "$OUT/inputs-$3.jsonl" \
    --out "$OUT/gen-$3-run$1.jsonl" ${LIMIT_ARGS[@]+"${LIMIT_ARGS[@]}"} 2>&1 \
    | tee "$OUT/harness-$3-run$1.log" | grep -v '^\['
}
for c in $CONDITIONS; do stage 1 "$OUT/arms.json" "$c"; done
for c in $RUN2; do stage 2 "$OUT/arms-run2.json" "$c"; done
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) end $(pmset -g batt | head -1)" >> "$OUT/power.log"
echo "done; summarize with: python3 summarize.py $(dirname "$OUT")"
