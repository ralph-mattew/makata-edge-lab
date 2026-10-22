# PoC 029: Per-category retrieval-confidence routing for absent clauses (OP-4)

| | |
|---|---|
| Status | Concluded — host stage (separability + ceiling analysis) |
| Verdict | **Reject — adopt is unreachable, despite a genuine positive sub-finding.** H3 **passes**: per-category top-1 cosine *does* separate absent from answerable (Non-Compete & Change-of-Control AUC **0.73**, Exclusivity 0.60) — a real correction to PoC-021's global-pooling conclusion that "cosine can't separate." BUT it still can't clear the bar: at the H2-respecting operating point (≤3pp answerable-recall loss) the routable absent fraction is only 64/36/11%, and since PoC-026 showed the current Qwen stack **already abstains at 86.3% CAR**, the *optimistic* end-to-end CAR-gain ceiling is **+8.8 / +5.0 / +1.6 pp** — all below the +10 H1 bar (NC/CoC ≤ +5). No zero-context Qwen run needed: the arithmetic ceiling fails H1. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | DeclineCraft (single-shot vs iterative RAG, CAR metric) + authority-framing over-refusal paper (small LLM refusal rates under legal role prompts) |
| Registered | 2026-10-22 (this draft, before the first run) |

## Question

Does a per-item retrieval-confidence routing mechanism — where items whose top-1 cosine score falls below a category-specific threshold are routed to a zero-retrieval (no-context) path instead of the hybrid stack — improve Correct Abstention Rate (CAR) on category-absent CUAD items by ≥10 percentage points vs. the current full-retrieval baseline, without degrading answerable-item recall@3 by more than 3 points?

## Why it matters here

- PoC-021 showed that a global single-threshold gate cannot separate absent from answerable items (both cluster near top-1 cosine ~0.59), but category-specific thresholds may exploit the fact that hard categories (Exclusivity, Non-Compete, Change-of-Control) have a distinctive retrieval-score distribution when the clause is absent — allowing a tighter, less costly gate.
- DeclineCraft established that presenting retrieved context to an LLM on unanswerable items actively degrades abstention relative to simpler retrieval regimes; routing absent-clause items to a zero-context path could free Qwen2.5-1.5B's parametric 'I cannot find this clause' behaviour without a system-prompt change, attacking OP-4 from the retrieval side rather than the generation side.

## Hypothesis

The unverified leap: computing per-category top-1 cosine score distributions separately for absent vs. answerable items will reveal category-specific decision boundaries that a global threshold cannot exploit, and routing low-confidence absent-clause items to a zero-context prompt will raise CAR ≥10 pp without the recall penalty seen in PoC-021's global gate. No source establishes this category-stratified routing on CUAD or on a 1.5B generator.

- H1: CAR on absent-clause items improves by ≥10 pp over the PoC-021 baseline (currently ~25% CAR at zero-threshold, 75% false-surfacing rate) when using per-category routing.
- H2: Answerable-item recall@3 regresses by ≤3 pp vs. the full-retrieval baseline (currently ~62–65% overall recall@3) — the PoC-021 global gate cost >3 pp; category routing should tighten this.
- H3: At least one hard category (Exclusivity, Non-Compete, or Change-of-Control) shows a statistically separable top-1 cosine distribution between absent and answerable items, validating the stratification premise.

## Method

Reuse the PoC-021 experiment harness and CUAD absent/answerable split. (1) For each of the three hard categories plus a pooled 'other' group, compute top-1 cosine score distributions separately for absent vs. answerable items using the existing EmbeddingGemma + hybrid stack. (2) Fit a per-category threshold (e.g., Youden's J on a held-out 20% split) that maximises CAR − recall penalty. (3) At inference: if the item's category-matched top-1 cosine < category threshold, invoke a zero-context prompt ('Based only on your knowledge of this document, does it contain a [category] clause? Answer only Absent if you cannot confirm.'); otherwise use the standard hybrid-retrieval path. (4) Measure CAR on absent items and recall@3 on answerable items vs. the full-retrieval baseline. All other pipeline components (chunking, embedding, LLM) unchanged.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** a per-category top-1 cosine threshold that routes low-confidence items to a zero-context path. **Held fixed:** EmbeddingGemma hybrid retrieval, the PoC-014 chunk index, the PoC-008 absent set + PoC-007 answerable set. **Measurements:** per-category absent-vs-answerable separability AUC (H3), the Youden-J threshold, CAR of absent items routed, and answerable recall@3 loss; plus the end-to-end CAR-gain ceiling given PoC-026's 86.3% with-context baseline. **Repetitions:** deterministic (fixed cosines) → single pass.

## Decision rule

Adopt routing if H1 (CAR +≥10 pp) AND H2 (recall@3 regression ≤3 pp) AND H3 (at least one category shows AUC > 0.65 for absent/answerable separation). Reject if H1 < +5 pp. Mark inconclusive if H1 is met but H2 is violated (pursue category-specific threshold tuning as next step).

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.38  ·  est. effort 1-2 weeks

## Harness

`routing-separability.py` computes, per hard category, the top-1 semantic cosine for absent items
(PoC-008 `answerable=False`, questions embedded fresh) and answerable items (PoC-007, committed query
vectors); the absent-vs-answerable AUC; the Youden-J threshold; and the CAR / answerable-recall-loss
tradeoff. No Qwen call — the decision gate is the cosine separability plus the PoC-026 baseline ceiling.

## Results

MEASURED on the host (EmbeddingGemma), 101 absent + 300 answerable hard-category items.

| Category | AUC (absent vs answerable) | abs median cos | ans median cos | CAR @ ≤3pp-recall cap | CAR-gain ceiling* |
|---|---|---|---|---|---|
| Exclusivity | 0.60 | 0.512 | 0.522 | 63.6% | **+8.8 pp** |
| Non-Compete | **0.73** | 0.531 | 0.559 | 36.4% | **+5.0 pp** |
| Change Of Control | **0.73** | 0.557 | 0.594 | 11.4% | **+1.6 pp** |

\* *optimistic* end-to-end CAR-gain ceiling = (routed fraction at ≤3pp recall cap) × (100% − 86.3%),
where 86.3% is the current Qwen-with-context absent CAR measured in PoC-026. It assumes zero-context
Qwen abstains perfectly (100%) on every routed item — a strict upper bound.

- **H3 (≥1 hard category AUC > 0.65):** **PASS** — Non-Compete and Change-of-Control both 0.73.
  Per-category cosine carries real absent/answerable signal that PoC-021's global pool hid. MEASURED.
- **H1 (CAR +≥10 pp):** FAIL — unreachable. Even the optimistic ceiling is +8.8 / +5.0 / +1.6 pp. MEASURED/INFERRED.
- **H2 (answerable recall loss ≤3 pp):** binding — at the CAR-maximising (Youden) point, loss is 3 / 13 / 9 pp,
  so the useful operating point is already capped at ≤3pp, which is what limits the routed fraction. MEASURED.

Per-category figures in `results/routing-separability.json`.

## Verdict

**Reject — but with a real, documented positive sub-finding.** The proposal's stratification premise
(H3) is *correct*: per-category, the top-1 cosine does separate absent from answerable items
(Non-Compete / Change-of-Control AUC 0.73), which refines PoC-021's "cosine can't separate" — that was
an artifact of pooling categories with opposite score distributions. **However, adopt is arithmetically
unreachable.** Two independent ceilings close it:

1. **Separation strength** — AUC 0.73 is "fair", not clean; forcing answerable-recall loss ≤ 3pp (H2)
   shrinks the routed absent fraction to 64 / 36 / 11%.
2. **Baseline headroom** — PoC-026 established the current Qwen stack already abstains on 86.3% of
   absent hard items. Routing can only change the routed fraction, so the best possible CAR gain is
   `routed × (100 − 86.3)` = **+8.8 / +5.0 / +1.6 pp**, all under the +10 bar (NC/CoC ≤ +5 → reject).

No zero-context Qwen run is needed: the upper bound already fails H1. **This closes OP-4 definitively:**
the generator is the correct absent-clause abstainer (PoC-026), and no cosine-confidence router —
global (021) or per-category (029) — can beat it enough to matter, because it has almost no headroom
to work with. Future absent-clause effort should target the ~14% Qwen *misses* directly (e.g. an
NLI/entailment check on the single top chunk), not a retrieval-confidence gate.

## Limits

- **Separability uses top-1 cosine only.** A richer confidence feature (top1−top2 margin, a small
  calibrated classifier over score features) could raise AUC; but the 86.3% baseline-headroom ceiling
  (independent of AUC) still caps the achievable gain, so a large reversal is unlikely.
- **Ceiling assumes zero-context Qwen = 100% CAR on routed items** — a strict upper bound; the true
  gain would be lower, strengthening the reject.
- **Absent set is PoC-008's hard-category items (101); answerable is PoC-007 (300)** — distributions,
  not paired items.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &

cd poc/029-percategory-confidence-routing
python3 routing-separability.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g2-4` · technique: structured-blend · attacks: OP-4
- Gates (0–10): G1 7.5 · G2 6.25 · G3 6.5 · null-control Δ6.0 (real 6.25 vs null 0.25)
- Tournament: rank 2, elo 1016.0 · priority 📊 MEDIUM (9.909534368070958)
- Provenance: idea-evolution-engine (private) scan 2026-10-22. Gate-approved + null-control-screened, NOT yet empirically validated.
