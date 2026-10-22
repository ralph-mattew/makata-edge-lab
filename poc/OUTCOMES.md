# Concluded-PoC outcomes ledger (engine ground truth)

`OUTCOMES.jsonl` is the open-science **ground-truth ledger** of concluded PoCs that the private
`idea-evolution-engine` consumes in **Gate 1**: before accepting a new idea, the engine retrieves the
most relevant prior outcomes (token-overlap or embedding similarity over `topic` + `question` +
`lesson`) and refuses ideas that re-ask a settled question or repeat a rejected approach, with the
lesson in hand. (The ingestion code — `_knowledge.py` — now lives in the private engine; this file is
the public artifact it reads.)

## Schema (one JSON object per line)

| field | meaning |
|---|---|
| `id` | `PoC-NNN` |
| `topic` | short mechanism/theme label (matched against new ideas) |
| `question` | the settled question, phrased so a near-duplicate idea collides with it |
| `verdict` | `adopt` · `reject` · `inconclusive` · `mixed` · `baseline` |
| `lesson` | the actionable takeaway — what is settled and what NOT to re-propose |

## Scope

Covers the RAG-era PoCs **006–027** (doc-QA model choice, retrieval, chunking, query formulation,
answer step, abstention, embedder). Pre-RAG PoCs 001–005 (kv-cache, sampler, summary formatting) are
a different problem space and out of the engine's current idea domain. The original private ledger
held only 007–011 and 013; this export adds **006, 012, 014–027** — the batches not previously fed
back.

## Standing lessons for idea generation (2026-10-22)

- **Hard categories (Exclusivity / Non-Compete / Change-of-Control) are not fixable at the retrieval
  *scoring* layer.** Global weight (013), per-category weight (023), a stronger embedder (022), and
  cross-encoder reranking (027) have all failed or only redistributed. Stop proposing retrieval-weight
  / reranker / embedder-swap fixes for them unless a *legal-domain fine-tuned* component is involved.
- **The durable hard-category movers are query decomposition (016) and the answer step (018).**
- **OP-1 is two problems (025):** Non-Compete = ranking (gold retrieved, mis-ranked); Exclusivity =
  representation (gold at rank 21+, not retrieved).
- **OP-4 is largely handled (020/026):** Qwen abstains on absent clauses at ~86% CAR; a cosine gate is
  far worse. Keep the generator for the absent decision.
- **EmbeddingGemma already runs 4-bit QAT (~270 MB), not fp16 600 MB (024).** Do not propose
  "quantize EmbeddingGemma to save RAM".
- **Engine calibration note:** both HIGH-priority picks this cycle (022 UIBK, 024 PTQ) under-delivered
  vs MEDIUM picks; reranking (027) was greenlit by a diagnostic yet still failed on off-the-shelf
  models — weight "transfer from general/scientific benchmarks to CUAD legal clauses" down.

Regenerate/extend from the per-PoC `README.md` Verdict fields when new PoCs conclude.
