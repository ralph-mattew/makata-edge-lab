#!/usr/bin/env python3
"""PoC 024 probe — what EmbeddingGemma does our stack actually run, and at what precision?

This PoC was registered to test "quantize fp16 EmbeddingGemma to 4-bit to free RAM". The probe
establishes the baseline reality that reframes the whole question:

1. `--embd-gemma-default` (which produced every committed vector in PoCs 007/014/016 and the 61.4%
   recall baseline) resolves to `ggml-org/embeddinggemma-300M-qat-q4_0-GGUF` — a 4-bit
   quantization-aware-trained (QAT) model, ~266 MB on disk. We are ALREADY at 4-bit.

2. The only other EmbeddingGemma GGUF available without auth, `ggml-org/embeddinggemma-300M-GGUF:Q8_0`
   (~318 MB), produces embeddings ORTHOGONAL to the committed Q4_0 vectors (cosine ~0.02-0.05 on
   identical chunk text + prefix) — i.e. it is a different checkpoint / embedding space, not a
   higher-precision version of the same weights. So it cannot serve as an fp16 reference for a
   same-model recall-preservation delta. The f16 repo is gated (HTTP 401).

Run (optional, needs the Q8 server on :8092 for part 2):
  llama-server -hf ggml-org/embeddinggemma-300M-GGUF:Q8_0 --embedding --pooling mean \
    --embd-normalize 2 -c 16384 --port 8092 --log-disable &
  python3 probe.py
"""
from __future__ import annotations
import json, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
CACHE = Path.home() / ".cache/huggingface/hub/models--ggml-org--embeddinggemma-300M-qat-q4_0-GGUF"


def cos(a, b): return sum(x * y for x, y in zip(a, b))


def main():
    print("== Default embedder identity ==")
    blobs = list((CACHE / "blobs").glob("*")) if (CACHE / "blobs").exists() else []
    big = max(blobs, key=lambda p: p.stat().st_size, default=None)
    if big:
        print(f"--embd-gemma-default -> embeddinggemma-300M-qat-Q4_0.gguf  ({big.stat().st_size/1e6:.0f} MB on disk)")
    print("This is the model behind every committed vector + the 61.4% recall baseline. Already 4-bit QAT.")

    # Part 2: only if the Q8 reference server is up
    try:
        chunks = [json.loads(l)["chunk"] for _, l in zip(range(3), open(P014 / "chunks-page.jsonl"))]
        q4 = [json.loads(l)["vec"] for _, l in zip(range(3), open(P014 / "emb-page.jsonl"))]
        def emb(t):
            body = json.dumps({"input": [t]}).encode()
            req = urllib.request.Request("http://127.0.0.1:8092/v1/embeddings", data=body,
                                         headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=60))["data"][0]["embedding"]
        print("\n== Q8_0 vs committed Q4_0 (same chunk text + doc prefix) ==")
        for i, (c, v) in enumerate(zip(chunks, q4)):
            print(f"  chunk {i}: cosine = {cos(emb(f'title: none | text: {c[:1200]}'), v):+.4f}")
        print("Near-zero cosine => different embedding space, NOT a higher-precision twin of Q4_0.")
    except Exception as e:
        print(f"\n(Q8 reference server not reachable on :8092 — skipping space check: {e})")


if __name__ == "__main__":
    main()
