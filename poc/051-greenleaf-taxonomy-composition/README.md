# PoC 051: Composed hard-category stack — legal taxonomy × GreenLeaf embedder × generator-free extractor (OP-1/OP-2)

| | |
|---|---|
| Status | Concluded — host stage (80 hard-contract sample, 103 items; span-F1 + recall@3, 2×2). |
| Verdict | **Reject the composition — the two levers are redundant (substitutes), not additive; ship the single best.** The full stack (GreenLeaf + taxonomy + extractor) reaches hard-mean span-F1 **30.1**, which does **not** beat the best single lever — **GreenLeaf-only = 32.3** (−2.2) — and misses H2 (+7.5 over the EG+generic baseline, < +12). Each lever is strong *alone* (taxonomy on EmbeddingGemma +7.0; GreenLeaf +9.7 = PoC-049), but they exploit the **same legal-domain signal** from complementary surfaces (the taxonomy spells out clause facets as text; GreenLeaf's legal embedding already encodes them), so stacking adds nothing and slightly antagonises on Non-Compete/Change-of-Control. H1 (full ≥ +3 over best single) FAIL, H2 FAIL → **REJECT (composition).** Production recommendation: **ship one lever — GreenLeaf (best, if on-device encode is feasible) or the legal taxonomy on EmbeddingGemma (no new model) as the cheap fallback — not both.** See Verdict. |
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

## Harness

`compose.py` forks `049/greenleaf-answerstep.py`: adds PoC-046's committed `taxonomy.json` as an alternate
sub-query set, embeds the generic (016) + taxonomy (046) sub-query texts with both embedders, runs the
PoC-036 generator-free extractor (N=10, ≤3-sent window) for all four embedder×query cells, and reports the
span-F1 + recall@3 grid. EmbeddingGemma via :8090; GreenLeaf via AutoModel/MPS. Heavy GL vectors gitignored;
committed inputs via `LAB_POC_ROOT`.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default` + GreenLeaf-Tiny AutoModel/MPS), **80
hard-contract sample, 103 items**, generator-free extractor N=10, span-F1 + recall@3.

| Cell (embedder + query-set) | hard-mean span-F1 | Exclusivity | Non-Compete | Change-of-Control | recall@3 |
|---|---|---|---|---|---|
| EG + generic (baseline, = PoC-036) | 22.6 | 14.4 | 26.7 | 26.7 | 43.9 |
| EG + taxonomy (PoC-046 lever) | 29.6 | 27.3 | 24.0 | 37.6 | 45.6 |
| GL + generic (PoC-045/049 lever) | **32.3** | 25.3 | 35.5 | 36.2 | 47.4 |
| **GL + taxonomy (full composition)** | 30.1 | 28.0 | 31.7 | 30.6 | 47.6 |

- **Single levers (control):** taxonomy alone +7.0 span-F1 (reproduces 046's direction at the answer step),
  GreenLeaf alone +9.7 (reproduces PoC-049). MEASURED.
- **H1 (full ≥ +3 over best single):** FAIL — full 30.1 vs best single (GL-only) 32.3 = **−2.2**. MEASURED.
- **H2 (full ≥ +12 over baseline):** FAIL — **+7.5** (22.6 → 30.1). MEASURED.
- **Per-category:** the levers *interfere* rather than add — on Non-Compete and Change-of-Control the full
  stack (31.7 / 30.6) is **below** GreenLeaf-only (35.5 / 36.2); only Exclusivity is roughly tied (28.0 vs
  27.3/25.3). recall@3 saturates ~45–48 across all cells. MEASURED.

Grid in `results/compose.json`.

## Verdict

**Reject the composition — the two adopted levers are substitutes, not complements.** Both move the hard
categories strongly *on their own* (legal taxonomy +7.0, GreenLeaf +9.7 span-F1), but combining them yields
30.1 — **below** GreenLeaf alone (32.3). They do not stack because they attack the **same underlying
deficit from two surfaces**: the hard-category failure is that the general-domain embedding under-represents
legal clause facets (exclusivity scope, non-compete duration, change-of-control triggers). The taxonomy
fixes this on the **query** side by naming those facets as extra sub-query text; GreenLeaf fixes it on the
**embedding** side by encoding them natively. Once GreenLeaf encodes the facets, spelling them out again in
the query is redundant — and the extra taxonomy sub-queries slightly dilute GreenLeaf's already-good ranking
on Non-Compete/Change-of-Control (−2 to −6 per-cat).

**Production recommendation: pick one lever, not both.** GreenLeaf-only (GL+generic) is the strongest answer
step (span-F1 32.3, recall@3 47.4) — adopt it if the on-device GreenLeaf embed-throughput gate (still open,
PoC-045/049) can be cleared. If GreenLeaf is not deployable on-device, the **legal taxonomy on
EmbeddingGemma** (EG+taxonomy, 29.6) is the no-new-model fallback and captures most of the gain with zero
extra model weight. The composed stack is not worth its cost. This closes the hard-category arc: the
bottleneck was legal-domain facet representation, addressable from *either* the query or the embedder — and
one is enough.

## Limits

- **80-contract sample (103 items)** — GreenLeaf full-corpus MPS encode infeasible; direction robust (both
  single-lever effects reproduce 046/049), exact magnitudes carry sample noise.
- **span-F1 proxy**, hard categories only, generator-free extractor.
- **One taxonomy + one generic set** at N=10; a smaller taxonomy paired with GreenLeaf (less dilution) was
  not swept — but since GreenLeaf-only already wins, it would at best tie.

## Reproduce

```bash
pip install -U transformers torch
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/051-greenleaf-taxonomy-composition
LAB_POC_ROOT=/path/to/lab-clone/poc python3 compose.py --contracts 80
```

---

### Engine provenance
- Lab-internal composition of the two session ADOPTs (046 + 045/049) with the adopted extractor (036) —
  the capstone of the hard-category arc. Verdict **REJECT (composition) — levers are substitutes; ship GreenLeaf-only (32.3) or taxonomy-on-EG (29.6), not both.** Feeds back to the ledger.
