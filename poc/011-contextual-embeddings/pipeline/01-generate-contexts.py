#!/usr/bin/env python3
"""Stage 1 — generate a per-chunk context with a language model (the PoC 011 method).

For each chunk, prompt a generator (on-device Qwen2.5-1.5B, and/or host Gemma-4-E2B)
with the whole document + the chunk, asking it to situate the chunk — Anthropic's
Contextual Retrieval prompt. The document prefix is reused across a document's
chunks (prompt caching) to bound cost. Output one row per chunk with the plain
text, the naive-template string (ablation), and each generator's context.

Generators are driven through a local `llama-server`; start one per model. Example:
  llama-server -m <qwen.gguf>  -c 8192 -ngl 99 --port 8099 --log-disable &   # device
  llama-server -m <gemma.gguf> -c 8192 -ngl 99 --port 8098 --log-disable &   # host (use /completion + gemma template)

Verified: the generation step runs and produces usable context (see
../results/generated-context-spotcheck.md). This script generalizes that spot-check
to the full chunk corpus.
"""
from __future__ import annotations
import argparse, json, re, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent.parent / "007-embedding-retrieval-recall" / "results" / "raw"
OUT = HERE.parent / "results" / "raw" / "contextual-chunks.jsonl"

SITUATE = ("<document>\n{doc}\n</document>\n"
           "Here is the chunk we want to situate within the whole document:\n"
           "<chunk>\n{chunk}\n</chunk>\n"
           "Give a short, succinct context to situate this chunk within the overall document "
           "for the purposes of improving search retrieval of the chunk. Answer only with the "
           "succinct context and nothing else.")


def chat_openai(url, prompt, n=90):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}],
                       "n_predict": n, "temperature": 0.1, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"].strip()


def completion_gemma(url, prompt, n=90):
    # Gemma-4's OpenAI chat endpoint returns empty content in current llama builds;
    # use raw /completion with the Gemma turn template instead.
    gp = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
    body = json.dumps({"prompt": gp, "n_predict": n, "temperature": 0.1, "cache_prompt": True}).encode()
    req = urllib.request.Request(url + "/completion", data=body,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=180))["content"].replace("<end_of_turn>", "").strip()


def load_contracts():
    """007's contracts.jsonl → {contract: {contract, language_sample, pages[]}}."""
    return {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}


def iter_chunks():
    """Yield (contract, page, chunk_text) from 007's chunks.jsonl."""
    for line in open(P007 / "chunks.jsonl"):
        rec = json.loads(line)
        for ch in rec["chunks"]:
            yield rec["contract"], ch.get("page"), ch["own"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qwen-url", default="http://127.0.0.1:8099")
    ap.add_argument("--gemma-url", default="http://127.0.0.1:8098")
    ap.add_argument("--doc-char-budget", type=int, default=6000)
    ap.add_argument("--limit", type=int, default=0, help="cap chunks (0 = all)")
    ap.add_argument("--skip-gemma", action="store_true")
    args = ap.parse_args()

    contracts = load_contracts()
    docs = {name: " ".join(c.get("pages", []) or []) for name, c in contracts.items()}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(OUT, "w") as f:
        for title, page, own in iter_chunks():
            doc = (docs.get(title, "") or "")[:args.doc_char_budget]
            prompt = SITUATE.format(doc=doc, chunk=own)
            row = {"contract": title, "page": page, "chunk": own,
                   "naive": f"Document: {title}. Chunk: {own}"}
            try:
                row["ctx_qwen"] = chat_openai(args.qwen_url, prompt)
            except Exception as e:
                row["ctx_qwen"] = ""; row["qwen_error"] = str(e)[:120]
            if not args.skip_gemma:
                try:
                    row["ctx_gemma"] = completion_gemma(args.gemma_url, prompt)
                except Exception as e:
                    row["ctx_gemma"] = ""; row["gemma_error"] = str(e)[:120]
            f.write(json.dumps(row) + "\n")
            n += 1
            if n % 25 == 0:
                print(f"  …{n} chunks")
            if args.limit and n >= args.limit:
                break
    print(f"wrote {n} contextual chunks -> {OUT}")


if __name__ == "__main__":
    main()
