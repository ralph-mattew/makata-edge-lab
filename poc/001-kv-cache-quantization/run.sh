#!/usr/bin/env bash
# PoC 001 host run. See README.md for the protocol.
set -euo pipefail
cd "$(dirname "$0")"

MODEL=models/google_gemma-4-E2B-it-Q4_K_M.gguf
MODEL_URL=https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF/resolve/main/google_gemma-4-E2B-it-Q4_K_M.gguf
MODEL_SHA=923c4c86177d2ee173a7f5b4fa3d0ac65f5962ab15e6d6a5bc250aec4fd7bf7e
TEXT_URL=https://www.gutenberg.org/cache/epub/20228/pg20228.txt
TEXT=data/noli-me-tangere-tl.txt
OUT=${OUT:-results/raw}   # replications: OUT=replications/<name>/results/raw
TMP=tmp

COMMON=(-ngl 99 -t 2 -b 2048 -ub 128)
# name  K cache  V cache  flash attention
ARMS=(
  "f16-nofa f16 f16 off"
  "f16-fa f16 f16 on"
  "q8k-nofa q8_0 f16 off"
  "q8-fa q8_0 q8_0 on"
  "q4-fa q4_0 q4_0 on"
)

if [[ ! -f $MODEL ]]; then
  echo "missing $MODEL; download with:"
  echo "  curl -L -C - -o $MODEL $MODEL_URL"
  exit 1
fi
mkdir -p "$OUT" data "$TMP"

echo "checking model hash ..."
[[ $(shasum -a 256 "$MODEL" | cut -d' ' -f1) == "$MODEL_SHA" ]] || { echo "model hash mismatch"; exit 1; }

if [[ ! -f $TEXT ]]; then
  curl -sSL "$TEXT_URL" -o data/pg20228.txt
  awk '/\*\*\* START OF/{f=1; next} /\*\*\* END OF/{f=0} f' data/pg20228.txt > "$TEXT"
fi

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "llama_cpp=$(llama-cli --version 2>&1 | grep -m1 '^version:' || true)"
  echo "host=$(sysctl -n hw.model) $(sysctl -n machdep.cpu.brand_string) $(( $(sysctl -n hw.memsize) / 1073741824 ))GB"
  echo "os=$(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "power=$(pmset -g batt | head -1)"
  echo "model_sha256=$MODEL_SHA"
  echo "text_sha256=$(shasum -a 256 "$TEXT" | cut -d' ' -f1)"
} > "$OUT/conditions.txt"
cat "$OUT/conditions.txt"

only=${ONLY:-all}   # ONLY=bench or ONLY=kld to run one part

if [[ $only == all || $only == bench ]]; then
  for arm in "${ARMS[@]}"; do
    read -r name ctk ctv fa <<< "$arm"
    for ctx in 2048 4096 8192; do
      depth=$(( ctx - 512 - 128 ))
      echo "bench $name ctx=$ctx ..."
      /usr/bin/time -l llama-bench -m "$MODEL" "${COMMON[@]}" -ctk "$ctk" -ctv "$ctv" -fa "$fa" \
        -p 512 -n 128 -d "$depth" -r 3 -o json -v \
        > "$OUT/bench-$name-$ctx.json" 2> "$OUT/bench-$name-$ctx.log" \
        || echo "  failed (see $OUT/bench-$name-$ctx.log)"
    done
  done
fi

if [[ $only == all || $only == kld ]]; then
  for ctx in 2048 4096; do
    chunks=$(( 16384 / ctx ))
    base="$TMP/base-$ctx.kld"
    read -r _ ctk ctv fa <<< "${ARMS[0]}"
    echo "kld base ctx=$ctx ..."
    llama-perplexity -m "$MODEL" -f "$TEXT" -c "$ctx" --chunks "$chunks" "${COMMON[@]}" \
      -ctk "$ctk" -ctv "$ctv" -fa "$fa" --kl-divergence-base "$base" \
      > "$OUT/kld-base-$ctx.log" 2>&1
    for arm in "${ARMS[@]}"; do
      read -r name ctk ctv fa <<< "$arm"
      echo "kld $name ctx=$ctx ..."
      llama-perplexity -m "$MODEL" -c "$ctx" --chunks "$chunks" "${COMMON[@]}" \
        -ctk "$ctk" -ctv "$ctv" -fa "$fa" --kl-divergence-base "$base" --kl-divergence \
        > "$OUT/kld-$name-$ctx.log" 2>&1 \
        || echo "  failed (see $OUT/kld-$name-$ctx.log)"
    done
    rm -f "$base"   # several GB; regenerated on the next run
  done
fi
echo done
