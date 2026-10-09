#!/usr/bin/env bash
# PoC 007 host run. See README.md for the protocol.
set -euo pipefail
cd "$(dirname "$0")"
exec </dev/null   # nothing here reads stdin; a background run must not depend on its terminal

EG=models/embeddinggemma-300M-Q8_0.gguf
EG_URL=https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF/resolve/0f741b5a6585bd53aeb15cd1372c56f2a0f65e12/embeddinggemma-300M-Q8_0.gguf
EG_SHA=b5ce9d77a3fc4b3b39ccb5643c36777911cc4eb46a66962eadfa3f5f60490d63
DATA_URL=https://zenodo.org/api/records/4595826/files/CUAD_v1.zip/content
DATA=data/CUAD_v1.zip
DATA_SHA=88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e
OUT=${OUT:-results/raw}   # replications: OUT=replications/<name>/results/raw
# The keyword tables are Xylo's and are not published; see generic/README.md.
KW=${LAB_PRIVATE_DIR:-../../private}/keywords.json
if [[ ! -f $KW ]]; then
  KW=../../generic/keywords.json
  echo "warning: private keyword tables not found; using the generic stand-in. Results will not match the registered run."
fi

mkdir -p models data "$OUT"
if [[ ! -f $EG ]]; then
  echo "downloading EmbeddingGemma 300M Q8_0 (334 MB) ..."
  curl -sSL -C - -o "$EG" "$EG_URL"
fi
echo "checking hashes ..."
[[ $(shasum -a 256 "$EG" | cut -d' ' -f1) == "$EG_SHA" ]] || { echo "EmbeddingGemma hash mismatch"; exit 1; }
if [[ ! -f $DATA ]]; then
  echo "downloading CUAD v1 (106 MB) ... (PoC 006 has the file; on APFS, cp -c clones it)"
  curl -sSL -C - -o "$DATA" "$DATA_URL"
fi
[[ $(shasum -a 256 "$DATA" | cut -d' ' -f1) == "$DATA_SHA" ]] || { echo "data hash mismatch"; exit 1; }

echo "building the harness ..."
swift build -c release --package-path harness
BIN="$(swift build -c release --package-path harness --show-bin-path)"

python3 prepare.py "$DATA" "$OUT"
"$BIN/Chunker" --contracts "$OUT/contracts.jsonl" --out "$OUT/chunks.jsonl"

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "harness=poc/007-embedding-retrieval-recall/harness"
  echo "llama_swift=$(python3 -c 'import json; p = [p for p in json.load(open("harness/Package.resolved"))["pins"] if p["identity"] == "llama.swift"][0]["state"]; print(p["version"], p["revision"])') (llama.cpp b8901)"
  echo "swift=$(swift --version 2>&1 | head -1)"
  echo "host=$(sysctl -n hw.model) $(sysctl -n machdep.cpu.brand_string) $(( $(sysctl -n hw.memsize) / 1073741824 ))GB"
  echo "os=$(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "power=$(pmset -g batt | head -1)"
  echo "embeddinggemma_sha256=$EG_SHA"
  echo "data_sha256=$DATA_SHA"
  echo "keywords_sha256=$(shasum -a 256 "$KW" | cut -d' ' -f1) ($(basename "$(dirname "$KW")"))"
  echo "items_sha256=$(shasum -a 256 "$OUT/items.jsonl" | cut -d' ' -f1)"
  echo "chunks_sha256=$(shasum -a 256 "$OUT/chunks.jsonl" | cut -d' ' -f1)"
} > "$OUT/conditions.txt"
cat "$OUT/conditions.txt"
if ! pmset -g batt | head -1 | grep -q "AC Power"; then
  echo "warning: not on AC power; the protocol requires it (see README, Method)"
fi

# Keyword scores first (cheap), then NLEmbedding, then EmbeddingGemma. Scores are deterministic, so
# there is one pass; the per-chunk times come from the same pass. caffeinate keeps the host awake.
for mode in kw nl eg; do
  caffeinate -i "$BIN/Scores" --mode $mode --contracts "$OUT/contracts.jsonl" --chunks "$OUT/chunks.jsonl" \
    --items "$OUT/items.jsonl" --model "$EG" --keywords "$KW" --out "$OUT/scores-$mode.jsonl" \
    $([[ $mode == kw ]] || echo --timing "$OUT/timing-$mode.jsonl") \
    2>&1 | tee "$OUT/harness-$mode.log" | grep -v '^\['
done

python3 index.py "$OUT"
echo "done; summarize with: python3 summarize.py $OUT"
