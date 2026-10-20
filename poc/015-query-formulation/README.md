# PoC 015: Query formulation for the hard/weak categories (decomposition vs rewrites)

| | |
|---|---|
| Status | Concluded (Arm A, recall@3) — full corpus; Arm B (end-to-end key-fact) pending |
| Verdict | **Keyword expansion is the winner** (+4.8 overall, +8.8 weak-cat mean, Exclusivity 7%→32%) — beating and cheaper than decomposition; the natural-language gloss *hurts*. Adopt-candidate pending Arm B (key-fact conversion). See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None yet |
| Source idea | The lab's own chain of eliminations. [PoC 013](../013-weight-tuning)/[009](../009-retrieval-depth-qwen)/[014](../014-clause-aware-chunking)/[016](../016-crossref-decomposition) ruled out scoring, depth, chunk boundaries, generated context, and cross-references for the hard categories. [PoC 016](../016-crossref-decomposition) found the one thing that moved them: **template question decomposition (Exclusivity 7%→24%)**. This PoC generalizes that finding across the query side. |
| Registered | 2026-10-20 (refreshed before the first run) |

## Question

The hard-category bottleneck is now localized to **query formulation** (PoC 016). Two open
questions remain:
1. **Does template decomposition generalize** beyond the 3 hard categories to the other weak
   ones (Agreement Date 29%, Warranty Duration 48%, Liquidated Damages 50%, Cap On Liability
   51%), or is it Exclusivity-specific?
2. **Is decomposition the best deterministic query transform**, or do simpler rewrites (a
   category gloss, keyword expansion) capture the same gain more cheaply? And does the recall@3
   gain actually **convert to better answers** (key-fact accuracy), or is it a retrieval-only
   artifact?

All transforms must be **deployable at 6 GB**, which — given PoC 011 and PoC 016 both showed
on-device generation *hurts* retrieval — means **no on-device generation**: every transform
here is deterministic / template-based.

## Why it matters here

PoC 016 proved that for Exclusivity, a single averaged query vector misses evidence that 2–3
focused sub-queries recover (+17 pts recall@3), with zero generation. But 016 tested only 3
categories, only recall@3, and its hard-category *mean* gain (+6) fell short of its own +10 bar.
Before investing further, the lab needs to know whether query reformulation is a **general**
lever (worth building into the product's retrieval path) or a narrow one, and whether the
retrieval gain is **real end-to-end** (better Qwen answers) or just a recall@3 proxy.

The CUAD category questions are long, templated boilerplate ("Highlight the parts of this
contract related to…") shared across all categories — so the embedded query vector is dominated
by shared boilerplate, not the category's distinguishing facets. That is exactly what a
category-specific rewrite or decomposition should fix.

## Hypotheses

HYPOTHESIS until measured. A point is a percentage point of items. Baselines are the PoC 014/016
`page/raw` per-category recall@3 (overall 61.8%; the weak categories listed above).

1. **H1 (decomposition generalizes).** Template decomposition lifts recall@3 by **≥10 points**
   on at least **half** of the targeted weak categories (not just Exclusivity), with the
   weak-category mean up **≥6 points**.
2. **H2 (cheapest winner).** Among deterministic transforms (category gloss, keyword expansion,
   decomposition), **decomposition is the best**, or a cheaper rewrite is within its CI — the
   decision adopts the **cheapest transform within the top CI** per category.
3. **H3 (no collateral damage).** Overall recall@3 does not regress >1 point; easy categories
   (Governing Law, Insurance) move <2 points.
4. **H4 (end-to-end conversion — the decisive arm, see Scope).** On the key-fact items, the
   recall@3 gain from the best transform **converts** to a key-fact-accuracy gain of **≥½** the
   recall gain (i.e. retrieving the right clause actually makes Qwen answer better). If recall
   rises but key-fact does not, the retrieval win is largely cosmetic.

Descriptive: per-category recall for every transform; examples where a reformulation flips
miss→hit; the authored gloss/keyword/sub-query templates (committed for reproducibility).

## Method

**Host.** MacBook Pro (Mac16,8), M4 Pro, 24 GB, macOS 26.5.1, AC power (as PoC 009/014/016).

**Held fixed (only the query changes):** chunks = PoC 014 page chunks; chunk embeddings =
PoC 014 `emb-page`; hybrid 0.9 semantic + 0.1 BM25; top-3. Reuses the PoC 016 embed/score harness.

**Items.** PoC 007's 1,325 answerable items / 397 CUAD contracts.

**Conditions** (deterministic query transforms over the fixed page index; authored once per
category, amortized across all contracts — the PoC-016 "41-generations-not-1,325" property):

| Condition | Query that gets embedded |
|---|---|
| `raw` (baseline) | the CUAD category question verbatim (today's behaviour) |
| `gloss` | category label + a short canonical gloss, boilerplate stripped (deterministic) |
| `keywords` | category + a fixed per-category keyword/synonym set (deterministic) |
| `decomp` | 2–3 per-category sub-queries; retrieve top-3 per sub-query, union, re-rank by max hybrid, take top-3 (the PoC-016 mechanism, extended to all weak categories) |

On-device generation (HyDE / query2doc) is **excluded by prior evidence** (PoC 011 and PoC 016
both measured it to hurt), not re-tested — recorded as a closed question, not an arm.

**Measurements.**
1. Per-category + overall recall@3 for each condition, contract-level bootstrap CIs (seed 0).
2. Cheapest-within-CI transform per category (H2).
3. **(Arm B, end-to-end, see Scope)** key-fact accuracy on the key-fact items for `raw` vs the
   best transform, using the PoC 006 Qwen2.5-1.5B harness over the retrieved top-3 (H4).

## Scope

**Arm A (recall@3 sweep) — run now.** Deterministic, reuses the PoC 016 harness; fast.

**Arm B (end-to-end key-fact, H4) — the decisive follow-up.** Requires joining PoC 006's
per-category key facts to per-item gold and running Qwen generation over the retrieved context
(the PoC 006 `GGUFQA` harness). Registered here; run as a scoped `raw` vs best-transform
comparison on the key-fact items. If the join/generation is not completed in the same pass it is
explicitly marked pending — recall@3 alone does **not** settle the verdict (that is H4's point).

## Decision rule

Written before the first run.

- **Adopt a transform** (for the product retrieval path) if **H1** holds (decomposition
  generalizes) **and H3** holds (no regression) **and H4** holds (recall converts to key-fact).
- Among transforms that pass, **adopt the cheapest within the top CI per category** (H2) — e.g.
  if a gloss matches decomposition on a category, prefer the gloss there.
- **Reject query reformulation** as a general lever if the weak-category mean moves <2 points or
  H4 fails (recall gain doesn't convert).
- **Inconclusive** / narrow-win if it only helps Exclusivity (confirming PoC 016 without
  generalizing).
- Report per-category deltas prominently regardless.

## Results

Arm A (recall@3), full corpus: 397 contracts, 1,325 items, hybrid 0.9/0.1, top-3, chunks
fixed = PoC 014 page. `raw` reproduces PoC 014/016's 61.8% (harness validated). Raw in
`results/` (`recall-{raw,gloss,keywords,decomp}.json`, `comparison.txt`, `query-variants.json`).

**Recall@3 by transform (MEASURED, 1,325 items).**

| Condition | overall | 95% CI | Δ overall | weak-cat mean | Δ weak |
|---|---|---|---|---|---|
| `raw` (baseline) | 61.8% | — | — | 35.0% | — |
| `gloss` | 59.8% | — | −2.0 | 32.9% | −2.0 |
| **`keywords`** | **66.6%** | — | **+4.8** | **43.7%** | **+8.8** |
| `decomp` | 62.9% | — | +1.1 | 37.9% | +2.9 |

**Per-category recall@3, weak categories (MEASURED).**

| Category | raw | gloss | keywords | decomp | best |
|---|---|---|---|---|---|
| **Exclusivity** | 7% | 14% | **32%** | 24% | keywords |
| Non-Compete | 25% | 31% | **32%** | 30% | keywords |
| Agreement Date | 29% | 20% | **40%** | 34% | keywords |
| Warranty Duration | 48% | 49% | **62%** | 46% | keywords |
| Liquidated Damages | 50% | 33% | 44% | 37% | **raw** |
| Cap On Liability | 51% | 50% | 52% | **56%** | decomp |

**Observations.**
- **OBSERVED (keyword expansion wins):** adding the category's discriminative vocabulary to the
  query lifts overall recall +4.8 and the weak-cat mean +8.8, and raises **Exclusivity 7%→32%** —
  more than decomposition's 7%→24%, with a single query (no sub-query union). Best on 4 of 6 weak
  categories.
- **OBSERVED (decomposition confirmed but narrower):** decomp reproduces the PoC 016 Exclusivity
  lift (+17) but **does not generalize** (weak-mean only +2.9; ≥+10 on just 1/6 categories). The
  PoC 016 "decomposition" win is better explained as **vocabulary injection** — decomp's varied
  sub-queries incidentally add discriminative terms; keywords do it directly and better.
- **OBSERVED (the gloss hurts):** a fluent natural-language gloss *reduced* recall (−2.0). Fluency
  is not the lever; discriminative *terms* are. This is the cleanest evidence that the CUAD query
  problem is vocabulary mismatch, not phrasing.
- **OBSERVED:** Liquidated Damages regressed under every transform (raw best) — a category whose
  raw question already carries the right terms; forcing extra vocabulary hurt it.
- **INFERRED (mechanism caveat):** keywords boost both the semantic query *and* the BM25 (0.1)
  arm; part of the gain may be lexical (BM25) rather than semantic. Arm B and a weight-ablation
  would disentangle this. Also, aggressive keyword queries risk raising false retrieval on
  category-absent contracts (OP-4) — untested here (answerable-only).

## Verdict

**Arm A (recall@3): keyword expansion is the clear winner; decomposition a weaker second; gloss
rejected.** Against the decision rule:

- **H1 (decomposition generalizes): NO** (+2.9 weak-mean, 1/6 categories ≥+10). Decomposition is a
  narrow win, essentially the Exclusivity effect from PoC 016.
- **H2 (cheapest best transform): keyword expansion** — top on 4/6 weak categories and cheapest
  (one query, no union). The adopt-candidate per-category is in the `best` column (keywords
  mostly; decomp for Cap On Liability; raw for Liquidated Damages).
- **H3 (no regression): mixed** — `keywords` does not regress (+4.8), but `gloss` does (−2.0), so
  gloss is rejected.
- **H4 (end-to-end conversion): PENDING (Arm B).** Recall@3 is a proxy; the verdict is **not
  final** until key-fact accuracy confirms the retrieval gain produces better Qwen answers.

**Recommendation.** Reject the gloss. Treat **keyword expansion** as the lead query transform
(cheap, generalizes, biggest Exclusivity lift) and **run Arm B** (`raw` vs `keywords` key-fact
accuracy on the PoC 006 harness) before adopting it into the product retrieval path. Net finding
across PoC 015/016: the hard-category bottleneck is **query vocabulary mismatch** — the fix is
injecting discriminative category terms, not fluent rephrasing, not generation, not chunking.

## Deviations

- **2026-10-20 (the run):** Ran Arm A only (recall@3). `gloss`/`keywords` use one authored vector
  per category; `decomp` unions top-3 per sub-query. Reused PoC 014 `emb-page` + `emb-queries`;
  embedded only the 57 authored query variants. Arm B (end-to-end key-fact, H4) not yet run —
  verdict explicitly holds H4 open.

## Deviations

- **2026-10-20 (refresh, before first run):** Re-aimed from the original draft (raw vs gloss vs
  keywords vs **HyDE/query2doc** generation arms) in light of PoC 016. Changes: (1) **dropped the
  HyDE/on-device-generation arms** — PoC 011 and PoC 016 both measured generation to hurt
  retrieval, so it is excluded by evidence, not re-tested; (2) **centered template
  decomposition** (PoC 016's winner) and extended it from 3 hard categories to all weak ones to
  test generalization; (3) **added the end-to-end key-fact arm (H4)** — the original draft
  measured recall@3 only, which PoC 016 showed is a proxy. No run had occurred before this change.

## Limits

1. **Deterministic transforms only** — no on-device generation (by design; see Deviations).
2. **Hand-authored templates** may overfit CUAD's category phrasing; may not transfer to
   free-form user questions (conservative — free-form is likely harder).
3. **Answerable items only** — absence behaviour (PoC 008) not measured; decomposition could
   raise false retrieval on category-absent contracts (OP-4 risk).
4. **CUAD / EmbeddingGemma / top-3 / English only** — held fixed to isolate the query transform.
5. **Arm B** depends on the PoC 006 key-fact harness; if deferred, recall@3 is a proxy and the
   verdict stays open on H4 (stated, not hidden).
6. Composes with PoC 016 (same mechanism family); supersedes PoC 016's "tune/extend templates"
   follow-up.

## Reproduce

Requirements: Apple-silicon Mac (macOS 26.4+, Swift 6.3+), llama.cpp; PoC 006/007/014 run once.

```bash
cd poc/015-query-formulation
python3 build-queries.py       # author gloss / keyword / sub-query templates per category
llama-server --embedding --embd-gemma-default --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
python3 embed.py               # embed the transformed queries (per category, amortized)
for c in raw gloss keywords decomp; do python3 score.py --cond $c; done
python3 compare.py             # per-category deltas + CIs across transforms
# Arm B (end-to-end key-fact): python3 keyfact.py --conds raw decomp   (PoC 006 Qwen harness)
```

## Replications

| Date | Device | Authors | Outcome |
|---|---|---|---|
| 2026-10-20 | Mac16,8 M4 Pro | Ralph Mattew Palomaria | Arm A: keyword expansion +4.8 overall / +8.8 weak-mean (Exclusivity 7%→32%); gloss rejected; decomp narrow. Arm B pending |
