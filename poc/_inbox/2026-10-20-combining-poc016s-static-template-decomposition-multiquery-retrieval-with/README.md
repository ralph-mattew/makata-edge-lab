# PoC (proposed): Does combining PoC-016's static template decomposition (multi-query re…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | PoC-008 + PoC-016 + PoC-017 |
| Registered | not yet — proposed 2026-10-20 |

## Question

Does combining PoC-016's static template decomposition (multi-query retrieval) with a constrained span-extraction answer step — where Qwen2.5-1.5B is forced to output only a verbatim substring of the retrieved chunk rather than free text — lift hard-category key_fact recall@3 and span-F1 by ≥+5 points (key_fact) and ≥+5 points (hard-mean span-F1) over the PoC-017 keyword-expanded baseline, without regressing fact categories?

## Why it matters here

- PoC-016 found that static template decomposition lifted Exclusivity recall 7%→24% (+17) and hard-mean recall +6 without any on-device generation — the first mechanism ever to move hard categories. PoC-017 showed that once the right chunk is retrieved, Qwen2.5-1.5B's free-form generation squanders the retrieval win (hard-mean span-F1 flat at 16.1, Non-Compete and Change-of-Control regressed). Combining PoC-016's retrieval gain with a constrained extraction step attacks both bottlenecks simultaneously — retrieval quality AND generation fidelity — in a single deployable experiment.
- Constrained substring extraction (forcing the model to return text that must appear verbatim in the retrieved chunk, validated by string-matching post-hoc) is a zero-extra-RAM technique compatible with the 6 GB budget and avoids the hallucinated paraphrase failure mode documented in PoC-017. If it converts PoC-016's latent retrieval gains into proportional answer-quality gains, it directly addresses the generator-bound bottleneck for hard categories without requiring a bigger model.

## Hypothesis

Constraining Qwen2.5-1.5B to perform extractive span selection — via a prompt template that instructs the model to copy a continuous substring from the provided retrieved chunk verbatim (e.g., 'Return only the exact sentence(s) from the passage below that answer the question. Do not paraphrase. If none apply, output NONE.'), combined with a post-generation string-match validator that rejects any output not found as a substring in the top-3 chunks and falls back to the highest-scoring chunk's first sentence — will convert PoC-016's retrieval recall gains into proportionally higher key_fact scores and span-F1 for hard categories. This combination (decomposed retrieval + constrained extractive generation) has NOT been demonstrated on our stack or for CUAD hard categories.

- H1: Hard-mean span-F1 increases by ≥+5 points over the PoC-017 keyword-expanded baseline (current hard-mean: 16.1) — i.e., reaches ≥21.1.
- H2: Exclusivity key_fact recall@3 increases by ≥+10 percentage points over PoC-016's decomposition-only baseline (current: 24%) — reaching ≥34%.
- H3: Fact-category overall recall@3 does not regress by more than 2 points vs the PoC-017 baseline (current overall: ~64%).
- H4: The string-match validator successfully rejects hallucinated outputs in ≥80% of cases where the model output is not a substring of any top-3 chunk (measured on a 50-item spot-check).

## Method

Reuse the existing experiment harness and CUAD dataset (300 hard-category items + fact-category items for regression check). Step 1: Apply PoC-016 static template decomposition to retrieve union top-3 chunks per hard category (already validated). Step 2: Feed the top-3 chunks + question to Qwen2.5-1.5B with a constrained extraction prompt ('Return only the exact sentence(s) from the passages below that answer the question. Do not paraphrase or add words. If no passage answers the question, output NONE.'). Step 3: Post-generation, run a string-match validator — if the model output is not a substring of any retrieved chunk, fall back to returning the first sentence of the highest-scored chunk. Step 4: Measure span-F1 (SQuAD token overlap vs gold span), key_fact (exact/fuzzy match), and recall@3 across hard and fact categories. Compare to PoC-017 keyword-expanded baseline and PoC-016 retrieval-only baseline. Also measure false-positive rate on 50 category-absent items (OP-4 proxy).

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

Adopt if H1 (hard-mean span-F1 ≥+5) AND H3 (no fact-category regression >2 points). Reject if H1 <+2 points improvement. Inconclusive if H1 is +2 to +4.9 points. In all cases, report H4 validator fidelity and OP-4 false-positive rate for downstream use.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.38  ·  est. effort 1-2 weeks

## Results

Link raw files in `results/` once run. Tag every number MEASURED / OBSERVED / INFERRED.

## Verdict

Adopt / reject / inconclusive, against the decision rule.

## Limits

What this does not show.

## Reproduce

Commands from a clean checkout.

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g1-1` · technique: novelty-push · attacks: OP-2
- Gates (0–10): G1 7.25 · G2 6.5 · G3 6.0 · null-control Δ6.25 (real 6.5 vs null 0.25)
- Tournament: rank 2, elo 1016.0 · priority 📊 MEDIUM (7.469534368070956)
- Provenance: idea-evolution-engine (private) scan 2026-10-20. Gate-approved + null-control-screened, NOT yet empirically validated.
