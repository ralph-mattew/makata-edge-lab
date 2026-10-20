# Open Problems — Makata AI Edge Lab

The lab's live research frontier: the unsolved bottlenecks our own PoCs have surfaced.
The synthesis stage (3b) uses these as the "problem" side of problem×method matching —
it looks for mechanisms in new papers that could attack one of these, including by
*combining* two papers. Keep this current as PoCs conclude.

Each problem has an id (used in synthesized-idea provenance), the evidence behind it,
and why it is still open.

## OP-1: Hard categories are invariant to retrieval scoring
- **Evidence:** PoC 013 swept the semantic/BM25 weight 0.1→0.9. Overall recall moved,
  but **Exclusivity stayed ~11% at every weight**, and Non-Compete / Change-of-Control
  barely moved. PoC 009 showed extra retrieval depth doesn't help either.
- **Why open:** the limiter for these categories is NOT retrieval scoring or depth. It is
  chunk boundaries (PoC 014, running) and/or query formulation (PoC 015, registered) —
  neither concluded yet. A *mechanism that specifically lifts Exclusivity/Non-Compete/
  Change-of-Control recall@3* is the single highest-value target.
- **Metric:** per-category recall@3 on the hard categories.

## OP-2: On-device generators are too weak to improve their own retrieval
- **Evidence:** PoC 011 — Qwen2.5-1.5B-generated per-chunk context *reduced* recall@3
  (62.7%→52.2%, bounded run). The generic "This chunk refers to…" preamble dilutes the
  embedding.
- **Why open:** generation-based retrieval enhancement (HyDE, contextual retrieval,
  query2doc) all assume a capable generator; at 6GB we only have a 1.5B. Open question:
  which generation-based tricks, if any, survive a tiny generator — or can be made to
  (constrained decoding, extract-don't-generate, template-free)?
- **Metric:** recall@3 (and key-fact) vs the no-generation baseline.

## OP-3: EmbeddingGemma's 600 MB is the biggest fixed RAM cost
- **Evidence:** of the 6GB budget, the embedder (600 MB) + LLM (1.0 GB) dominate.
  Freeing embedder RAM would allow a bigger LLM or longer context.
- **Why open:** no measured recall/RAM tradeoff for compressing the stored vectors or the
  embedder itself. (int8/PQ of stored vectors is the cheap, grounded first step; more
  aggressive embedder compression is unproven for *retrieval* — see the rejected
  frozen-table idea.)
- **Metric:** recall@3 regression vs RAM freed (MB).

## OP-4: Absent-clause behaviour is unmeasured in most PoCs
- **Evidence:** PoC 008 touched it; most PoCs test answerable items only. A HyDE/generated
  query could *increase* false retrieval on categories a contract does not contain.
- **Why open:** no systematic measure of over-retrieval / false-positive clause surfacing.
- **Metric:** false-positive rate on unanswerable (category-absent) items.

## OP-5: Cross-references break small chunks
- **Evidence:** PoC 007 found the median chunk is 25 words; "as described in Section 3.2"
  is meaningless alone. StrucChunk (arXiv) resolves cross-references *before* embedding and
  reports gains on legal corpora.
- **Why open:** we have not tested resolving/appending referenced-clause text before
  embedding on CUAD. Composes with PoC 014 (clause boundaries).
- **Metric:** recall@3 on items whose gold span contains a cross-reference.

## OP-6: Everything is English-only
- **Evidence:** Xylo's Filipino/Cebuano use case is untested across the retrieval stack;
  Apple Intelligence can't generate Filipino.
- **Why open:** no multilingual retrieval/generation measurement on-device.
- **Metric:** recall@3 + key-fact on a Filipino contract set (does not yet exist).
