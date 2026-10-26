# PoC 048: Hierarchical parent-section context for clause chunks (OP-1)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox `2026-10-26-combining-structureaware-chunking-navembedstyle-with-hisccg-hierarchical` (engine `synth-idea-1`, method×method, OP-1; source oa-W7167682060). |
| Registered | 2026-10-26 (before the first run). |

## Question

Does prepending **parent-section context** (section heading + path) to each clause chunk at index time —
Hi-SCCG-style hierarchical context — lift hard-category recall@3 by **≥ +10 pp** over the flat-chunk hybrid
baseline, by restoring the definitional context that isolated hard-category clauses reference?

## Why it matters here

- Hard-category recall is scoring-invariant (013) and depth-invariant (009); the remaining non-scoring
  levers are **chunk boundaries** (014) and **query formulation** (015/016/030/046). This attacks the
  boundary/context lever: hard clauses ("Change of Control", "Exclusivity") are often 1–2 sentences that
  reference **defined terms set up paragraphs earlier**, so a clause embedded in isolation loses the
  context a retriever needs to match the question.
- **Cautionary prior:** PoC-016's cross-reference resolution (appending *referenced clause* text) was
  **rejected** — it diluted the embedding (−0.7 overall). This PoC prepends *section-hierarchy* context
  (headings/path), which is shorter and more targeted than full referenced clauses; whether that avoids the
  dilution failure is the open question.

## Hypothesis

Prepending the section path/heading (bounded, e.g. ≤ 40 tokens) to each chunk before embedding adds
disambiguating context without the dilution that full-clause xref caused. Untested on our stack.

- **H1:** hard-mean recall@3 ≥ **+10 pp** over the flat-chunk baseline (33.0).
- **H2:** overall recall@3 does not regress > 1 pp (guard against the PoC-016 xref dilution).
- **H3:** the gain is **larger than PoC-016 xref** (which was −1.0 hard) — i.e. hierarchy context ≠ xref.

## Method

Reuse the committed PoC-014 page chunks + gold spans + PoC-007 queries. **Derive a section heading/path per
chunk** (deterministic: nearest preceding ALL-CAPS/"Section N"/"Article X" heading in the contract), prepend
it (capped) to the chunk text, **re-embed the modified chunks** via EmbeddingGemma (`--embd-gemma-default`,
`title: none | text:` prefix), and score recall@3 (top-3 covers ≥50% of gold span) overall + per hard
category. Arms: (a) flat baseline (committed `emb-page`, reproduces 61.8/33.0), (b) hierarchical-context
chunks (headline). Pure semantic + hybrid 0.9/0.1 both reported.

- **Varies:** prepended section-hierarchy context vs none. **Held fixed:** chunk boundaries + spans (so
  recall scoring is comparable), EmbeddingGemma, eval items, K=3. **Measurements:** overall + per-hard-cat
  recall@3; heading-resolution coverage (% chunks that got a heading). **Repetitions:** deterministic.

## Decision rule

Adopt if **H1 (+≥10 hard) ∧ H2 (overall regression ≤1)**. Reject if hard-mean moves **< +3** or overall
regresses **> 1** (xref-style dilution). Inconclusive between.

## Expected outcome (engine estimate)

inconclusive · confidence ~0.4 · est. effort 1 week

## Harness (to be written at run time)

`hier-context.py`: derive per-chunk section heading (deterministic), prepend (capped), re-embed changed
chunks via EmbeddingGemma :8090 (reuse `emb-page` as base, overlay re-embedded), score recall@3 overall +
per hard cat vs the flat baseline. Reads committed vectors via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/048-hierarchical-chunk-context && python3 hier-context.py
```

---

### Engine provenance
- `synth-idea-1` · method×method · OP-1 · screen **null (false-null: substrate at ceiling)** → routed to
  reality. Attacks the chunk-boundary/context lever; cautionary prior is PoC-016 xref (rejected, dilution).
  Verdict feeds back to the ledger.
