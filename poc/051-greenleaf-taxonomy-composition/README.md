# PoC 051: Composed hard-category stack — legal taxonomy × GreenLeaf embedder × generator-free extractor (OP-1/OP-2)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Lab follow-up composing the session's two hard-category ADOPTs — **PoC-046** (legal-taxonomy query expansion, recall@3 +10.3) and **PoC-045/049** (GreenLeaf legal embedder, recall@3 +14.3 / span-F1 +9.7) — with the adopted **PoC-036** generator-free extractor. The candidate hard-category production stack. |
| Registered | 2026-10-27 (before the first run). |

## Question

Do the two independently-adopted hard-category levers **stack**? Running the generator-free extractor
(PoC-036) with **both** the legal clause taxonomy (PoC-046 query side) **and** the GreenLeaf legal embedder
(PoC-045/049 embedding side), does hard-mean span-F1 exceed **each single lever alone** by **≥ +3 pp**, and
how much of the two retrieval gains converts end-to-end?

## Why it matters here

- The two ADOPTs attack the hard categories from **complementary** sides — PoC-046 improves *the query*
  (legal clause-element sub-queries), PoC-045/049 improves *the embedding* (legal-domain vectors). They have
  never been combined. If additive, the composition is the candidate production stack; if redundant (both
  exploit the same legal-domain signal), the simpler/cheaper single lever wins.
- PoC-049 already showed GreenLeaf's retrieval gain **converts** to answer quality (span-F1 +9.7, ratio
  2.77 vs PoC-040's ~0). The open question is whether the taxonomy's additional recall (+10.3 on
  EmbeddingGemma) also converts, and whether it adds *on top of* GreenLeaf.

## Hypothesis

The levers are complementary (query vs embedding), so composing them should beat either alone; but there
is overlap risk (a legal embedder may already capture the facets the taxonomy spells out).

- **H1:** full stack (GreenLeaf + taxonomy + extractor) hard-mean span-F1 ≥ **+3 pp** over the better single
  lever (GreenLeaf-only extractor, PoC-049 ≈ 32).
- **H2:** full stack ≥ **+12 pp** over the EmbeddingGemma + generic-decomp baseline (PoC-036 ≈ 22) — i.e.
  the two gains are at least partly additive end-to-end.
- **H3 (diagnosis):** report the 2×2 (embedder × query) span-F1 + recall@3 grid to quantify additive vs
  redundant.

## Method

Fork the PoC-049 harness (generator-free ≤3-sentence extractor, N=10, span-F1, hard-contract sample).
Run a **2×2**: embedder ∈ {EmbeddingGemma, GreenLeaf} × query ∈ {PoC-016 generic decomposition, PoC-046
legal taxonomy}. For each cell: decomposed/taxonomy sub-queries (embedded with that cell's embedder) →
per-sub-query pool → union → top-N=10 → sentence split → max-cosine ≤3-sentence window → span-F1; also
recall@3. The taxonomy is PoC-046's committed `taxonomy.json` (7 sub-queries/hard-cat); generic is PoC-016's
3/cat. EmbeddingGemma sub-queries/sentences via :8090; GreenLeaf via AutoModel/MPS (as PoC-049).

- **Varies:** embedder × query-set (2×2). **Held fixed:** the generator-free extractor, N=10, window=3,
  span-F1 scorer, the hard-contract sample, pool N=2. **Measurements:** per-cat + hard-mean span-F1 and
  recall@3 for all four cells; additivity (full − best-single). **Repetitions:** deterministic → single pass.
- Sample: hard-category contracts (`--contracts 80`, as PoC-049; GreenLeaf full-corpus MPS encode infeasible).

## Decision rule

Adopt the composed stack if **H1 (full ≥ +3 over best single) ∧ H2 (full ≥ +12 over EG+generic baseline)**.
Reject the *composition* (ship the single best lever) if full ≤ best single (redundant). Inconclusive between.
Report the 2×2 grid regardless.

## Expected outcome (engine estimate)

inconclusive · confidence ~0.5 · est. effort 1 week

## Harness (to be written at run time)

`compose.py` forks `049/greenleaf-answerstep.py`: adds the PoC-046 taxonomy as an alternate sub-query set,
embeds taxonomy + generic sub-queries with both embedders, runs the extractor for all four embedder×query
cells, and reports the span-F1 + recall@3 grid + additivity. Heavy GreenLeaf vectors gitignored; committed
vectors via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
pip install -U transformers torch
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/051-greenleaf-taxonomy-composition
LAB_POC_ROOT=/path/to/lab-clone/poc python3 compose.py --contracts 80
```

---

### Engine provenance
- Lab-internal composition of the two session ADOPTs (046 + 045/049) with the adopted extractor (036) —
  the capstone of the hard-category arc. Verdict feeds back to the ledger.
