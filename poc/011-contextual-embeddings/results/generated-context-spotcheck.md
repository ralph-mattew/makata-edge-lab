# PoC 011 — generated-context spot-check (pre-run)

**This is a spot-check, not the registered run.** It exercises only the first step
of the revised PoC 011 — *generating* per-chunk context with a language model — to
get an early read on **H2** (can an on-device 1.5B model generate useful context?)
and **H3** (does generation add more than a static template?). **No recall@3 is
measured here** — the embedding → contextual-BM25 → retrieval → scoring pipeline
(and the EmbeddingGemma model) are still to be built. Verdict stays TBD.

## Setup

- **Sample:** 10 short, ambiguous chunks (~25 words each) drawn from 3 CUAD v1
  contracts — the kind of chunk the method is meant to help (party names, places,
  cross-references, clause fragments).
- **Generators:** both run locally via `llama-server`:
  - `qwen` — **Qwen2.5-1.5B-Instruct Q4_K_M** (the on-device generator, H2).
  - `gemma` — **Gemma-4-E2B-it Q4_K_M** (a stronger "host-ish" generator, for contrast).
- **Prompt:** Anthropic's "situate this chunk within the document" prompt; whole
  document truncated to ~6000 chars to fit an 8k context; `temperature 0.1`,
  `n_predict 90`.
- **Raw outputs:** [`results/raw/generated-contexts.jsonl`](raw/generated-contexts.jsonl)
  (per chunk: naive-prepend string, Qwen context, Gemma context).

## What was OBSERVED (10/10 chunks)

Both models produced a relevant situating context for **every** chunk. Examples:

| Chunk | Qwen2.5-1.5B (on-device) | Gemma-4-E2B |
|---|---|---|
| "INC., with its principal place of business at 1730 S. Amphlett Blvd., …" | "…refers to the parties involved in the CO-BRANDING AND ADVERTISING AGREEMENT, specifically I-ESCROW and 2THEMART.COM, INC." | "identifies the parties to the agreement: i-Escrow and 2TheMart." |
| "…the 'Joint Venture' in this Agreement. The principal office and place of…" | "…the principal office and place of business of the Joint Venture, located at 1600 Lower State Road, Doylestown, PA 18901." | "specifies the principal office and place of business for the Joint Venture." |

Simple tallies over the 10 (OBSERVED, not a graded metric):

- **Qwen situates the chunk** (names the agreement / clause / party): **8/10**.
- **Qwen adds a "This chunk refers to…" preamble**: **8/10** — it does not obey
  "answer only with the context." A prompt tweak or a post-strip would fix this; it
  matters because the preamble is dead weight in the embedded text.
- **Gemma is more structurally precise** (cites section numbers, e.g. "Section 1.2
  Standard of Service") but **leaked a chat-template tag** (`</start_of_turn>`) or
  echoed chunk text in **3/10** — a tooling artifact of running Gemma-4 through
  this `llama-server` build (its OpenAI chat endpoint returned empty content; the
  raw `/completion` endpoint with Gemma's template worked, with occasional tag leakage).

## Early read (OBSERVED, not a verdict)

- **H2 (on-device generator) looks viable at the generation step.** A 1.5B model
  that fits on-device produced on-point, document-grounded context for ambiguous
  CUAD chunks at ~140 tok/s. Its main weakness is form (the preamble), not
  substance — easily cleaned up before embedding.
- **H3 (generation vs static template) looks directionally supported.** Both models
  added real, chunk-specific information (parties, clause type, section, address)
  that the naive `"Document: X. Chunk: Y"` template cannot produce. Whether that
  translates into recall@3 is exactly what the full run must measure.
- **Caveat worth carrying into the run:** force bare-context output (strip the
  "This chunk…" preamble), and sort out a clean Gemma-4 generation path (raw
  `/completion` + template, or a different build) so the host-generator comparison
  isn't polluted by template leakage.

## Not shown here

Recall@3, key-fact accuracy, per-chunk-size breakdown, indexing cost — i.e. every
decision-rule metric. This spot-check only establishes that the generation step
runs on-device and produces plausible context. The registered run (generate →
re-embed with EmbeddingGemma → contextual BM25 → retrieve → score) is still to be
implemented.
