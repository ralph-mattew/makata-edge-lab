# PoC 048: Hierarchical parent-section context for clause chunks (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (full CUAD, 1,325 items; recall@3). |
| Verdict | **Reject — hierarchical parent-section context is inert for hard-category retrieval.** Prepending the nearest section heading/path to each chunk (51% coverage) and re-embedding moves hard-mean recall@3 **+0.0** (34.7 → 34.7) and overall **+0.4** (62.6 → 63.0). It is *better* than PoC-016's cross-reference resolution (which diluted, −0.7 overall / −1.0 hard) — section headings don't hurt — but they add no disambiguating signal: Exclusivity 6 → 7 (noise), Non-Compete flat, CoC 65 → 64. H1 (+≥10) FAIL, H2 (reg ≤1) pass; hard-mean < +3 → **REJECT.** Confirms the hard-category bottleneck is the **query side** (PoC-046 taxonomy +10.3) and the **embedder** (PoC-045 GreenLeaf +14.3), not chunk boundaries/context (cf. 014). See Verdict. |
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

## Harness

`hier-context.py`: for each chunk, finds the nearest preceding section heading (`ARTICLE/SECTION/CLAUSE N`
or an UPPERCASE title run) in the 80-word window before the chunk, prepends it (≤40 words), re-embeds the
heading-prepended chunks via EmbeddingGemma (:8090), overlays them on the committed `emb-page` flat index,
and scores recall@3 overall + per hard category vs the flat baseline. Reads committed vectors via
`LAB_POC_ROOT`; the re-embedding cache (`results/raw/hier-emb.jsonl`) is gitignored.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default`), full CUAD 1,325 items, hybrid 0.9/0.1,
recall@3. Heading context resolved for **50.5%** of chunks (39,918 / 79,037).

| Arm | overall | hard-mean | Exclusivity | Non-Compete | Change-of-Control |
|---|---|---|---|---|---|
| flat baseline (`emb-page`) | 62.6 | 34.7 | 6 | 33 | 65 |
| hierarchical (heading prepended) | 63.0 | 34.7 | 7 | 33 | 64 |
| Δ | +0.4 | **+0.0** | +1 | 0 | −1 |

- **H1 (hard-mean ≥ +10):** FAIL — **+0.0**. MEASURED.
- **H2 (overall regression ≤ 1):** PASS — overall +0.4 (no dilution). MEASURED.
- **H3 (beats PoC-016 xref, −0.7/−1.0):** technically yes (no dilution) but the effect is **null**, not a win.
  MEASURED.
- Decision rule: hard-mean moved < +3 → **REJECT**. MEASURED.

Summary in `results/hier-context.json`.

## Verdict

**Reject.** Hierarchical parent-section context is inert for hard-category retrieval. The hypothesis — that
isolated hard clauses lose the definitional context a retriever needs, and prepending the section heading
restores it — does not hold on CUAD/EmbeddingGemma: the heading text (section numbers, short titles) adds
no discriminative signal that moves recall@3, and at 51% coverage the effect is a flat +0.0 hard-mean. The
one genuinely positive note is that it does **not dilute** the way PoC-016's cross-reference resolution did
(−0.7/−1.0) — section-path context is short and benign — but benign is not useful.

This triangulates the hard-category bottleneck cleanly. Across the series, the chunk/context levers are all
null-to-negative (PoC-014 boundaries +4/+2/0; 016 xref −1.0; 037 chunk-size recall gain didn't convert;
048 hierarchy +0.0), while the two levers that *do* move the hard categories are the **query side**
(PoC-016/030 decomposition; PoC-046 legal taxonomy +10.3) and the **embedder** (PoC-045 GreenLeaf +14.3).
The right chunk is already retrievable (PoC-014's 95.8% span-containment); what matters is *matching* it —
a query/embedding problem, not a chunk-context one. Effort should stay on 045/046 (and their composition),
not chunk engineering.

## Limits

- **Heuristic heading resolution** (regex, 80-word window, 51% coverage) — a parser with full section-tree
  structure might attach better headings, but the null result + PoC-014's span-containment make a large
  reversal unlikely.
- **recall@3 only**; EmbeddingGemma embedder (not GreenLeaf).
- **Spans unchanged** (only embedded text changed), so recall scoring is directly comparable to the baseline.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/048-hierarchical-chunk-context
python3 hier-context.py            # or: LAB_POC_ROOT=/path/to/lab-clone/poc python3 hier-context.py
```

---

### Engine provenance
- `synth-idea-1` · method×method · OP-1 · screen **null (false-null: substrate at ceiling)** → routed to
  reality. Attacks the chunk-boundary/context lever; cautionary prior is PoC-016 xref (rejected, dilution).
  Verdict **REJECT** (hierarchical context inert, +0.0 hard-mean) feeds back to the ledger.
