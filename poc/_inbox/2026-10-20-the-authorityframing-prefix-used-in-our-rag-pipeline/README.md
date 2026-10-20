# PoC (proposed): Does the authority-framing prefix used in our RAG pipeline (e.g., 'You…

> **Staged proposal — not yet a registered PoC.** Auto-exported from the lab's ideation engine.
> A human must review this, fill Method/devices, then PROMOTE it to a numbered `poc/NNN-<slug>/`
> and register it (commit before the first run). See `../POC-GENERATION-WORKFLOW.md`.

| | |
|---|---|
| Status | planned |
| Verdict | — |
| Authors | (unclaimed — assign on promotion) |
| Reviewers | none yet |
| Source idea | LLMs Prompted for Legal Context Refuse More: Overrefusal from Small On-Premises LLMs in Criminal Legal Context (http://arxiv.org/abs/2610.26211v1) |
| Registered | not yet — proposed 2026-10-20 |

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
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

ADOPT plain/task-only prompt if H1 holds (key-fact accuracy ≥70.9%) AND H3 holds (recall@3 unchanged ±1 pt). REJECT if key-fact accuracy delta < +1 point across all variant pairs. INCONCLUSIVE if accuracy improves 1–2.9 points or if H3 is violated (retrieval also shifts), warranting deeper investigation.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.45  ·  est. effort 2-3 days (prompt variants require no retraining; only inference re-runs on existing harness)

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

- Engine idea id: `arxiv-2610.26211v1-idea-2` · technique: extraction · attacks: -
- Gates (0–10): G1 6.5 · G2 8.5 · G3 8.0 · null-control Δ8.0 (real 8.5 vs null 0.5)
- Tournament: rank 4, elo 954.9 · priority 📊 MEDIUM (6.6)
- Provenance: idea-evolution-engine (private) scan 2026-10-20. Gate-approved + null-control-screened, NOT yet empirically validated.
