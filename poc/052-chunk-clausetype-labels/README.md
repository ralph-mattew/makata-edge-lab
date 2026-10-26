# PoC 052: Rule-based clause-type labels prepended to chunks (OP-1/OP-2)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox `2026-10-27-a-krishoktechstyle-rulebased-extraction-gate` (engine `synth-idea-5`, analogical transfer, OP-2). The generator-free ("extract-don't-generate") analogue of PoC-011 contextual retrieval. |
| Registered | 2026-10-27 (before the first run). |

## Question

Does prepending a **deterministic clause-type label** (+ section heading) to each chunk at index time —
`[Clause Type: {label}] [Section: {heading}] {chunk}` — and re-embedding lift hard-category recall@3 over
the flat baseline, succeeding where PoC-011 (Qwen-generated context) failed and PoC-048 (section heading
only) was inert?

## Why it matters here

- PoC-011's contextual-retrieval failure was generator-quality; a zero-generator deterministic context
  injector tests whether the *concept* works once the weak generator is removed.
- **Cautionary priors:** PoC-048 prepended the section heading alone → **inert (+0.0 hard-mean)**; PoC-016
  cross-reference resolution → **dilution (−0.7)**. The one untested element here is the **clause-type
  label** (e.g. `[Clause Type: Exclusivity]`), a short discriminative tag that heading-context lacked.

## Hypothesis

A short clause-type tag injects the category signal the embedding under-represents, without the dilution of
appending long clause text. Untested; the 048 null result makes a large lift unlikely.

- **H1:** hard-mean recall@3 ≥ **+5 pp** over the flat baseline (34.7).
- **H2:** overall recall@3 does not regress > 1 pp (dilution guard, cf. PoC-016).
- **H3 (ablation):** clause-type label contributes more than the section heading alone (which was +0.0 in
  PoC-048).

## Method

Build a **rule-based CUAD clause-type classifier** (keyword/regex patterns for the 3 hard categories;
fallback `General Provisions`). For each PoC-014 chunk, detect the clause type and (reusing PoC-048's
heading resolver) the parent section heading; prepend `[Clause Type: {label}] [Section: {heading}] ` and
**re-embed** via EmbeddingGemma (`--embd-gemma-default`), overlaying on the committed `emb-page`. Hybrid
0.9/0.1, recall@3 overall + per hard category. **Ablate:** clause-type-only vs heading-only (= PoC-048) vs
both. Chunk spans unchanged (recall scoring comparable).

- **Varies:** prepended context (none / clause-type / heading / both). **Held fixed:** chunk boundaries +
  spans, EmbeddingGemma, eval items, K=3. **Measurements:** overall + per-hard-cat recall@3; classifier
  firing rate per category. **Repetitions:** deterministic.

## Decision rule

Adopt if **H1 (+≥5 hard) ∧ H2 (overall reg ≤1)**. Reject if hard-mean moves **< +3** or overall regresses
**> 1**. Inconclusive between. Report the ablation (does the clause-type label beat heading-only?).

## Expected outcome (engine estimate)

inconclusive · confidence ~0.38 · est. effort 3-4 days

## Harness (to be written at run time)

`clausetype-labels.py` forks `048/hier-context.py`: adds a rule-based clause-type classifier, prepends the
label (+heading), re-embeds changed chunks (EmbeddingGemma :8090), scores recall@3 for the 4 ablation arms.
Reads committed vectors via `LAB_POC_ROOT`; re-embedding cache gitignored.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/052-chunk-clausetype-labels && python3 clausetype-labels.py
```

---

### Engine provenance
- `synth-idea-5` · analogical transfer · OP-2 · UNSCREENED. Promoted per the user's directive to run; the
  untested element vs PoC-048 is the clause-type label. Verdict feeds back to the ledger.
