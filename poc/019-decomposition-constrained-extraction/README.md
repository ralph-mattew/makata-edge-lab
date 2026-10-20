# PoC 019: Template decomposition + constrained substring extraction

| | |
|---|---|
| Status | Concluded — host stage (300 hard-category items, full run) |
| Verdict | **Adopt (host stage).** Decomposed retrieval + constrained verbatim-extraction prompt + substring validator lifts hard-mean span-F1 to 22.1 — **+6.6** over the same-retrieval free-generation arm (15.4, which reproduces the 16.1 baseline) — clearing H1 (≥ +5). Exclusivity rises 3.3 → 15.1 (**+11.8**). Validator reject rate 61.7%: the verbatim constraint rarely held, so the first-sentence fallback carries most of the gain — see Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Synthesized by the lab's ideation engine (2026-10-20 edge-ai scan, MAP-Elites `novelty-push`, attacks OP-2). Combines PoC-008 + PoC-016 (decomposition) + PoC-017 (span quality). |
| Registered | 2026-10-20 (this draft, before the first run) |

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
- Varies: the generation step — constrained extractive prompt + substring validator vs the PoC-017 free-generation baseline. Held fixed: PoC-016 decomposition, EmbeddingGemma retrieval, Qwen2.5-1.5B Q4, the CUAD eval set.
- Measurements: hard-mean span-F1, Exclusivity key_fact recall@3, fact-category recall@3, validator reject rate, category-absent false-positive rate (50-item spot-check). Repetitions: Qwen decoding greedy (temp 0) for determinism → single pass; H4 validator fidelity on the 50-item spot-check. Host run first, then on-device replication.

## Decision rule

Adopt if H1 (hard-mean span-F1 ≥+5) AND H3 (no fact-category regression >2 points). Reject if H1 <+2 points improvement. Inconclusive if H1 is +2 to +4.9 points. In all cases, report H4 validator fidelity and OP-4 false-positive rate for downstream use.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.38  ·  est. effort 1-2 weeks

## Harness

`constrained-extract.py` implements the host stage. Retrieval is held fixed to PoC-016
decomposed sub-queries (max-pool hybrid 0.9/0.1) → top-3 chunks, reusing committed vectors
(`007/items.jsonl`, `007/contracts.jsonl`, `014/chunks-page.jsonl`, `014/emb-page.jsonl`,
`016/emb-subqueries.jsonl`, `016/decomp-templates.json`) — no re-embedding, and only the Qwen
server is needed.

Two arms on identical retrieved chunks:

- `constrained`: Qwen gets the constrained prompt (*"Return only the exact sentence(s)… Do not
  paraphrase… If none apply, output NONE."*). A substring validator then accepts the output only
  if its normalized form (lowercase, collapsed whitespace, ≥ 8 chars) appears verbatim in a
  top-3 chunk; otherwise — NONE, empty, or a paraphrase — it falls back to the first sentence of
  the highest-scored chunk. Validator accept/reject counts are logged.
- `free`: the PoC-017 free-generation baseline, same prompt/sampling, run here so the span-F1 Δ
  is a clean same-retrieval contrast (rather than comparing to 017's 16.1 under different retrieval).

Both use greedy decoding (temperature 0) for determinism.

## Results

MEASURED on the host (Mac, Qwen2.5-1.5B-Instruct Q4_K_M, greedy temp 0), 300 hard-category
items (100 each), single pass. Span-F1 is SQuAD token-overlap vs the gold span; contract-level
bootstrap CI (10k, seed 0). Both arms share identical PoC-016 decomposed retrieval.

Hard-category span-F1:

| Arm | Exclusivity | Non-Compete | Change Of Control | hard-mean | 95% CI |
|---|---|---|---|---|---|
| `free` (same-retrieval baseline) | 3.3 | 16.1 | 26.8 | **15.4** | 12.6–18.4 |
| `constrained` (+ substring validator) | 15.1 | 17.3 | 33.8 | **22.1** | 18.4–25.9 |

- The `free` arm reproduces the registration's 16.1 baseline (15.4) under identical retrieval —
  the control holds. MEASURED.
- **H1 (hard-mean span-F1 ≥ +5):** constrained 22.1 vs free 15.4 = **+6.6**. PASS. MEASURED.
- Exclusivity 3.3 → 15.1 (**+11.8**), Change Of Control 26.8 → 33.8 (+7.0), Non-Compete +1.2.
- **H3 (fact-category regression):** retrieval is identical across arms → fact recall@3 unchanged
  by construction. OBSERVED (cite PoC-016/007, not re-scored).
- **H4 (validator fidelity):** reject rate **61.7%** (185/300) — Qwen's output was a verbatim
  substring of a top-3 chunk in only 38% of items; the other 62% fell back to the highest-scored
  chunk's first sentence. AUTOMATED reject rate only; whether each reject was a true hallucination
  vs a correct paraphrase still needs the ~50-item manual spot-check. MEASURED (rate).

Raw per-item answers (with the raw model output + `accepted` flag) in
`results/raw/{constrained,free}-answers.jsonl`; summary in `results/constrained-both.json`.

## Verdict

**Adopt (host stage) — with an important mechanism caveat.** The combination clears H1 (+6.6) and
delivers the largest Exclusivity gain in the series (+11.8). **But the 61.7% validator reject rate
means the first-sentence fallback — not Qwen's constrained generation — produces most answers.** In
effect this result is closer to a *retrieval-anchored extractive* method (pick the decomposed-query
top chunk, return its lead sentence) than to "constrained generation": the tiny generator rarely
emitted a usable verbatim span. That is itself the finding — consistent with PoC-017's conclusion
that Qwen2.5-1.5B is the answer-step bottleneck — and it overlaps heavily with PoC-018's
generator-free extractive result (hard-mean 20.7). Recommend promoting the **cheaper** of the two
to the device stage: PoC-018 needs no generator at all. Before a device build, run the H4 manual
fidelity spot-check and an ablation that replaces Qwen with a pure "first sentence of top chunk" to
quantify how much (if any) the generation step adds over the fallback alone.

## Limits

- **Span-F1 is the answer-quality metric.** H2 is written as "Exclusivity key_fact recall@3", but
  the hard categories have `key_fact = None` in PoC-006 (not key-fact-scorable) and recall@3 is a
  retrieval quantity unchanged by the answer step (fixed at PoC-016's 24% for Exclusivity). So the
  constrained answer step is evaluated by Exclusivity **span-F1**; recall@3 is reported as the
  retrieval reference only. Reconcile H2's wording on promotion to a verdict.
- **H3 (fact-category regression) is a retrieval sanity check** — retrieval is identical across
  arms, so fact recall@3 is unchanged by construction; cite PoC-016/007, not re-run here.
- **H4 (validator fidelity) is partly manual.** The harness logs the validator reject rate
  automatically, but judging whether a rejected output was a true hallucination vs a correct
  paraphrase needs a human spot-check on ~50 items (the registration's H4). The 50-item
  category-absent false-positive probe (OP-4) needs a CUAD negative/unanswerable set (cf. PoC-008)
  and is not wired in this scaffold.
- **Off-the-shelf substring matching.** Normalization is lowercase + whitespace collapse; OCR
  artifacts in CUAD text may cause a few false rejects (then the fallback applies).

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &

cd poc/019-decomposition-constrained-extraction
python3 constrained-extract.py --arm both      # constrained + validator vs free baseline, prints Δ
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g1-1` · technique: novelty-push · attacks: OP-2
- Gates (0–10): G1 7.25 · G2 6.5 · G3 6.0 · null-control Δ6.25 (real 6.5 vs null 0.25)
- Tournament: rank 2, elo 1016.0 · priority 📊 MEDIUM (7.469534368070956)
- Provenance: idea-evolution-engine (private) scan 2026-10-20. Gate-approved + null-control-screened, NOT yet empirically validated.
