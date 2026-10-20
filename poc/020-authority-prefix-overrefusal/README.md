# PoC 020: Does the authority-framing prompt prefix cause over-refusal?

| | |
|---|---|
| Status | Building (host harness scaffolded; logic validated on committed data, full run pending Qwen server) |
| Verdict | — |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | *LLMs Prompted for Legal Context Refuse More: Overrefusal from Small On-Premises LLMs in Criminal Legal Context* (http://arxiv.org/abs/2610.26211v1), surfaced by the lab's ideation engine (2026-10-20 edge-ai scan, Stage-3 extraction) as a self-critique of our own system prompt. |
| Registered | 2026-10-20 (this draft, before the first run) |

## Question

Does the authority-framing prefix used in our RAG pipeline (e.g., 'You are a legal expert…' in the system prompt) cause Qwen2.5-1.5B Q4 to refuse or hedge on CUAD contract questions, measurably degrading key-fact accuracy compared to a plain no-prefix baseline?

## Why it matters here

- If Qwen2.5-1.5B exhibits the same 2–20x over-refusal pattern on legal framing, our current system prompt could be silently suppressing answers on hard categories (Exclusivity, Non-Compete, Change-of-Control) that PoC-013 showed are already bottlenecked — masking real retrieval improvements.
- Identifying and eliminating over-refusal is a zero-cost fix: changing the system prompt requires no new models, no RAM budget increase, and no indexing changes, making it the cheapest possible accuracy lever.
- Key-fact accuracy (currently 67.9%) is sensitive to outright refusals and hedged non-answers; even a 3–5 point gain from prompt reformulation would match the gains we are seeking from chunking experiments.

## Hypothesis

The source demonstrated over-refusal under legal authority framing on criminal-law prompts with unspecified small LLMs; we test whether the same framing effect degrades Qwen2.5-1.5B Q4's key-fact accuracy on CUAD contract Q&A, which is a different legal subdomain, a different model, and a different output metric — all unverified transfer.

- H1: Removing or neutralizing the legal-authority framing from the system prompt increases key-fact accuracy by ≥3 points over the current 67.9% baseline on the full CUAD 1,325 Q&A set.
- H2: The hard categories identified in PoC-013 (Exclusivity, Non-Compete, Change-of-Control) show a disproportionately large accuracy gain (≥5 points) under plain vs. authority-framed prompts, consistent with refusal being a contributing factor to their invariance.
- H3: recall@3 is unaffected (±1 point) by prompt framing changes, confirming that any accuracy delta is due to generation behavior, not retrieval.

## Method

Reuse the PoC-006/007 harness and the full CUAD 1,325 Q&A benchmark. Design three system-prompt variants: (A) current authority-framed prompt (baseline), (B) plain no-role prompt ('Answer the following question about the contract.'), (C) task-only prompt with no legal framing. Run all three through Qwen2.5-1.5B Q4 with EmbeddingGemma hybrid retrieval (0.9/0.1). Log refusal/hedge rate alongside key-fact accuracy and recall@3. Stratify results by PoC-013 hard categories. Estimated sample: full 1,325 items × 3 conditions.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- Varies: the system-prompt framing only — (A) current authority-framed baseline / (B) plain / (C) task-only. Held fixed: EmbeddingGemma retrieval, Qwen2.5-1.5B Q4, decoding settings, the full CUAD eval set.
- Measurements: key_fact accuracy, recall@3, refusal/hedge rate, all stratified by the PoC-013 hard categories. Repetitions: greedy decoding (temp 0) → single pass over 1,325 items × 3 conditions. Host run first, then on-device replication.

## Decision rule

ADOPT plain/task-only prompt if H1 holds (key-fact accuracy ≥70.9%) AND H3 holds (recall@3 unchanged ±1 pt). REJECT if key-fact accuracy delta < +1 point across all variant pairs. INCONCLUSIVE if accuracy improves 1–2.9 points or if H3 is violated (retrieval also shifts), warranting deeper investigation.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 2-3 days (prompt variants require no retraining; only inference re-runs on existing harness)

## Harness

`authority-prompt.py` runs three system-prompt variants with a **byte-identical user turn** and
**identical retrieval**, so only the authority framing varies:

- **A (authority)** — `system = "You are a legal expert specializing in contract analysis…"`
- **B (plain)** — no system message at all
- **C (task-only)** — `system = "Answer the question using the provided text."`

Per item: EmbeddingGemma hybrid 0.9/0.1 retrieval (raw query, top-3, committed `014/emb-page` +
`014/emb-queries` — no re-embedding) → Qwen2.5-1.5B with each variant. Metrics:

- **Key-fact accuracy** (primary) via PoC-006 `facts.py`, on the 6 date/duration/jurisdiction
  categories (464 scorable items).
- **Refusal/hedge rate** on every answerable item — a refusal or "not stated" is a miss here —
  via a frozen marker regex, stratified by category.
- **recall@3** — identical across variants (retrieval is unchanged), computed once. The dry pass
  reproduces the 61.8% PoC-007/014 baseline, confirming the retrieval layer.

Greedy decoding (temperature 0). Full run = 1,325 items × the chosen variants.

## Results

Not run yet. Non-embedding logic validated on committed data: full 1,325-item set, 464 key-fact
scorable, recall@3 = 61.8% (matches baseline), refusal regex + facts scorer checked. The run needs
the Qwen server. Per-variant raw answers (with `refused` / `key_fact_hit` flags) land in
`results/raw/variant-*-answers.jsonl`; the summary in `results/authority-overrefusal.json`. Tag
every number MEASURED / OBSERVED / INFERRED.

## Verdict

To be determined against the decision rule after the run.

## Limits

- **H2 (hard-category accuracy gain) is not key-fact-scorable.** The PoC-013 hard categories
  (Exclusivity, Non-Compete, Change Of Control) have `key_fact = None`, so H2's "disproportionate
  accuracy gain" is measured here via **refusal-rate** on those categories (reported as
  `hard_cat_refusal_rate`), not key-fact accuracy. Note this when evaluating H2.
- **Variant A's wording is representative, not verbatim-from-app.** It should be reconciled with
  Xylo's exact production system prompt on promotion to a verdict; the experiment measures the
  *framing effect*, which the three variants isolate.
- **Refusal detection is lexical.** A frozen marker regex; it will miss paraphrased refusals and
  may count a legitimately-absent "not stated" — but on the answerable CUAD set a "not stated" is
  a miss, which is exactly the over-refusal signal under test.
- **recall@3 unaffected by construction** — prompt framing does not touch retrieval, so H3 is a
  sanity check, confirmed by the 61.8% reproduction.

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &

cd poc/020-authority-prefix-overrefusal
python3 authority-prompt.py                 # all three variants, full 1,325-item set
python3 authority-prompt.py --limit 200     # quick smoke run
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `arxiv-2610.26211v1-idea-2` · technique: extraction · attacks: -
- Gates (0–10): G1 6.5 · G2 8.5 · G3 8.0 · null-control Δ8.0 (real 8.5 vs null 0.5)
- Tournament: rank 4, elo 954.9 · priority 📊 MEDIUM (6.6)
- Provenance: idea-evolution-engine (private) scan 2026-10-20. Gate-approved + null-control-screened, NOT yet empirically validated.
