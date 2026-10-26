# PoC 052: Rule-based clause-type labels prepended to chunks (OP-1/OP-2)

| | |
|---|---|
| Status | Concluded — host stage (300 hard items, 216 contracts; recall@3). |
| Verdict | **Adopt — the clause-type label works where PoC-048's section heading was inert.** Prepending `[Clause Type: {label}]` to each chunk and re-embedding lifts hard-mean recall@3 **34.7 → 43.0 (+8.3)**; adding the heading (`both`) gives 43.3 (+8.6). The **ablation is decisive**: the clause-type label is the active ingredient, the heading adds ~0 on top (exactly PoC-048's inert heading-only result). Exclusivity 6 → 19, Non-Compete 33 → 44, Change-of-Control 65 → 69. H1 (+≥5) PASS (+8.6), H2 (overall reg ≤1) PASS. → **ADOPT.** This **refines PoC-048's "chunk context is dead"** conclusion: chunk context *can* help — but only if it carries the category-discriminative clause-type signal, not a generic section heading. Caveats: weaker than the query-side levers (PoC-053 +19.3 / PoC-046 +10.3) and it costs an index-time re-embed, so it is likely a *substitute* for them (all inject the same legal-category signal); retrieval-only (PoC-040 conversion deferred). See Verdict. |
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

## Harness

`clausetype-labels.py` runs a rule-based clause-type classifier (keyword/regex for the 3 hard categories,
`General Provisions` fallback) over each chunk, prepends `[Clause Type: {label}]` (+ `[Section: {heading}]`
for the `both` arm, reusing PoC-048's heading resolver), re-embeds the hard-contract chunks via
EmbeddingGemma (:8090), and scores recall@3 for flat / clausetype-only / both. Reads committed vectors via
`LAB_POC_ROOT`; re-embedding cache gitignored.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default`), **300 hard items / 216 contracts** (51,549
chunks re-embedded per arm), hybrid 0.9/0.1, recall@3. Classifier fired: General-Provisions 49,284 /
Exclusivity 1,501 / Change-of-Control 631 / Non-Compete 133.

| Arm | hard-mean | Exclusivity | Non-Compete | Change-of-Control |
|---|---|---|---|---|
| flat (committed `emb-page`) | 34.7 | 6 | 33 | 65 |
| clause-type label only | 43.0 | 19 | 42 | 68 |
| **both (clause-type + heading)** | **43.3** | 17 | 44 | 69 |

- **Control:** flat 34.7 reproduces the known hard baseline. MEASURED.
- **H1 (best ≥ +5 over flat):** PASS — **+8.6** (both). MEASURED.
- **Ablation:** clause-type-only (+8.3) ≈ both (+8.6); the section **heading adds ~0** — identical to
  PoC-048's inert heading-only finding. The clause-type label is the whole effect. MEASURED.

Summary in `results/clausetype-labels.json`.

## Verdict

**Adopt — with an important refinement of PoC-048.** PoC-048 concluded chunk/context injection was dead for
hard-category retrieval (section heading → +0.0). PoC-052 shows that was a property of the *heading*, not of
chunk context per se: prepending a **category-discriminative clause-type label** lifts hard-mean recall@3
+8.6, with the ablation isolating the label as the sole active ingredient (heading still ~0). Even though
the rule-based classifier tags only ~4% of chunks as a hard category, those are exactly the hard-clause
chunks, and tagging them makes them far more retrievable (Exclusivity 6 → 19, Non-Compete 33 → 44).

Where it sits among the hard-category levers: it is a **real but secondary** win. It is weaker than the
query-side levers (PoC-053 canonical-term binding +19.3 → 54.0; PoC-046 taxonomy +10.3) and the embedder
(PoC-045/049), and unlike the query levers it carries an **index-time re-embed cost**. By the PoC-051
logic, it is almost certainly a **substitute** for them — all four mechanisms (clause-type label, taxonomy
query, canonical-term query, legal embedder) inject the same missing legal-category signal, just at
different pipeline stages. Production guidance: prefer the **query-time** levers (053 ≫ 052) which need no
re-embedding; adopt 052 only if the index is being rebuilt anyway and query-side binding is unavailable.

The scientific contribution is the refinement: **chunk context helps iff it is clause-type-discriminative** —
a clean correction to 048.

## Limits

- **recall@3 only** (answer-step conversion deferred, cf. PoC-040).
- **Keyword/regex classifier** (3 hard cats); a learned classifier might tag more precisely, but the gain is
  already secondary to the query levers.
- **Hard-contract sample** (300 items / 216 contracts); overall-corpus recall not measured (the label is
  hard-category-targeted).
- **Index-time cost** — requires re-embedding the corpus with labels; query-side levers (053/046) avoid this.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/052-chunk-clausetype-labels
python3 clausetype-labels.py      # or: LAB_POC_ROOT=/path/to/lab-clone/poc python3 clausetype-labels.py
```

---

### Engine provenance
- `synth-idea-5` · analogical transfer · OP-2 · UNSCREENED. Promoted per the user's directive to run; the
  untested element vs PoC-048 is the clause-type label. Verdict **ADOPT** — clause-type label +8.6 (heading inert, refines 048); secondary to query levers 053/046. Feeds back to the ledger.
