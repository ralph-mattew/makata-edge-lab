# PoC 026: Cosine-gated abstention vs the Qwen stack on absent hard clauses (OP-4)

| | |
|---|---|
| Status | Concluded — host stage (101 absent + 300 answerable hard-cat items) |
| Verdict | **Reject — premise inverted.** The cosine abstention gate is *far worse* than the current Qwen stack at declining absent clauses: **Qwen baseline CAR = 86.3%** vs **gate CAR = 13.7%** at τ=0.50 (0% at τ≤0.45) → **Δ = −72.5pp** (decision rule rejects at Δ<+5). The hypothesis "the generator is the false-confidence source" is refuted: Qwen, reading the retrieved text, correctly says "not stated" 86% of the time, while the cosine score can't separate absent from present (absent items still retrieve high-cosine chunks — the PoC-021 effect). This also reconciles PoC-021: the 75% retrieval-level false-surfacing is largely **caught downstream by Qwen's abstention**. Keep Qwen for absent-clause handling. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | OnQ (on-policy QAT distillation for Qwen3) + DeclineCraft (retrieval vs. abstention on unanswerable queries); promoted from the 2026-10-22 ideation-engine scan. |
| Registered | 2026-10-22 (this draft, before the first run) |

## Question

Does routing category-absent items through the generator-free extractive pipeline (PoC-018 adopted mechanism) instead of Qwen2.5-1.5B generation — combined with a cosine-score abstention threshold — yield a Correct Abstention Rate (CAR) ≥10 percentage points higher than the current hybrid-retrieval + Qwen generation stack on CUAD absent-clause items?

## Why it matters here

- PoC-018 showed the tiny Qwen2.5-1.5B generator actively hurts answer quality — the same mechanism (over-confident generation on weak evidence) is the most plausible driver of false positives on absent-clause items; replacing generation with an extractive step plus a confidence gate could suppress false positives without adding RAM
- OP-4 is entirely unmeasured in the extractive-answer regime: we know generator-free extraction wins for answerable hard categories, but whether it also reduces over-retrieval false claims on category-absent items is unknown and directly actionable

## Hypothesis

The unverified leap: for CUAD items where the target clause category is absent from the contract, the PoC-018 extractive pipeline (no Qwen generation) will produce lower-confidence cosine scores for top-retrieved chunks than for answerable items, and a simple cosine-score threshold gate (e.g., max chunk cosine < τ → abstain) applied atop the extractive pipeline will yield CAR ≥10pp higher than the current Qwen-generation stack — because the generator is the false-confidence source, not the retrieval itself. No source establishes this threshold mechanism or its transfer to legal absent-clause detection.

- H1: Extractive pipeline (PoC-018) + cosine-threshold abstention gate achieves CAR ≥10pp higher than Qwen-generation baseline on CUAD absent-clause items (current CAR: unmeasured, estimated ~40–55% based on OP-4 gap)
- H2: The optimal threshold τ (determined by sweep on a held-out calibration split) generalises across hard categories (Exclusivity, Non-Compete, Change-of-Control absent items) without per-category tuning
- H3: The abstention gate does NOT regress recall@3 on answerable items by more than 2pp (false-abstention constraint)

## Method

Reuse existing experiment harness and CUAD dataset. (1) Identify all category-absent items for Exclusivity, Non-Compete, Change-of-Control (~150–200 items from full CUAD). (2) Run PoC-018 extractive pipeline on these items; record max cosine score of top-3 retrieved chunks per query. (3) Sweep threshold τ ∈ {0.30, 0.35, 0.40, 0.45, 0.50} on a 50% calibration split; select τ maximising CAR while keeping false-abstention on answerable items ≤2pp regression. (4) Evaluate on held-out 50% split: measure CAR (primary) and false-abstention rate on answerable hard-category items (constraint). (5) Compare to current Qwen-generation baseline CAR on same absent-clause items as the control arm. No new model training required — pure inference + threshold search on adopted stack.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- **Varies:** the abstention mechanism on absent items — cosine-threshold gate (sweep τ ∈ {0.30…0.50}) vs the current Qwen generation stack. **Held fixed:** EmbeddingGemma hybrid 0.9/0.1 retrieval, top-3, the PoC-008 absent set + PoC-007 answerable set, Qwen prompt/sampling. **Measurements:** CAR on absent hard-cat items (primary), recall@3 regression on answerable hard-cat items (constraint). **Repetitions:** deterministic (greedy Qwen, fixed cosines) → single pass; seeded 50/50 calibration split.

## Decision rule

Adopt if H1 (CAR +≥10pp vs. Qwen baseline) AND H3 (answerable recall regression ≤2pp). Reject if H1 <+5pp. Inconclusive if +5pp ≤ H1 < +10pp or H3 violated.

## Expected outcome (engine estimate, not a result)

inconclusive  ·  confidence 0.42  ·  est. effort 1 week

## Harness

`absent-routing.py` compares two abstention mechanisms on the HARD categories. **Absent arm** =
PoC-008 `answerable=False` hard-cat items (101); their questions are embedded fresh (EmbeddingGemma)
for the top-1 cosine, and Qwen is run on the hybrid top-3 context for the baseline CAR (refusal
detected by the frozen PoC-020 regex). **Answerable arm** = PoC-007 hard-cat items (300, committed
vectors) for the over-abstention regression. τ swept {0.30…0.50}; calibration = seeded 50% of absent
items; τ\* maximises calib CAR subject to answerable regression ≤ 2pp; evaluated on the held-out 50%.

## Results

MEASURED on the host (EmbeddingGemma + Qwen2.5-1.5B Q4). 101 absent hard-cat items (calib 50 /
held 51); 300 answerable hard-cat items (baseline recall@3 33.0%).

| τ | gate CAR (held, absent) | answerable regression |
|---|---|---|
| 0.30–0.45 | 0.0% | 0.0 pp |
| 0.50 | 13.7% | 0.7 pp |

| Arm | CAR on held-out absent |
|---|---|
| **Qwen generation (current stack)** | **86.3%** |
| Cosine gate @ τ\*=0.50 | 13.7% |
| **Δ (gate − Qwen)** | **−72.5 pp** |

- **H1 (gate CAR ≥ Qwen + 10pp):** FAIL, catastrophically — Δ = −72.5pp. MEASURED.
- **H2 (one τ generalises across hard cats):** moot — no τ is competitive; absent-item cosines are too
  high (the gate barely fires) because retrieval surfaces topically-similar chunks even when the
  clause is absent (the PoC-021 effect). MEASURED.
- **H3 (answerable regression ≤2pp):** technically satisfied (≤0.7pp) only because τ\* is so low the
  gate almost never fires — which is also why its CAR is ~0. MEASURED.

Summary in `results/absent-routing.json`; human-readable `results/comparison.txt`.

## Verdict

**Reject — the premise is inverted.** The PoC assumed Qwen's generation is the false-confidence
source for absent clauses and that a cosine gate would abstain better. The opposite is true: **Qwen
is an excellent absent-clause abstainer (86.3% CAR)** — reading the retrieved text, it correctly
answers "not stated" — while the **cosine score is the poor signal** (absent items retrieve
high-cosine chunks, so a gate at any usable τ either never fires or would also gate out answerable
items). Net:

- **Keep Qwen for absent-clause handling.** Replacing its abstention with a cosine gate would be a
  ~72pp CAR regression.
- **This reconciles PoC-021:** the alarming 75% retrieval-level false-surfacing is largely *caught
  downstream* by Qwen's generation step saying "not stated" — so OP-4 is far less severe end-to-end
  than the retrieval-only view suggested.
- **Design tension to carry forward:** PoC-018 showed removing Qwen *helps* answerable answer
  quality, but PoC-026 shows removing Qwen *hurts* absent-clause abstention (86%→~14%). A
  generator-free pipeline would need its own strong abstainer — and the cosine gate is not it. The
  natural design is a hybrid: extractive answering (018) for above-threshold answerable items, but
  retain a generation/NLI-style abstention check for the absent decision.

## Limits

- **Hard categories only** (101 absent / 300 answerable). Fact categories are not covered; their
  absent-item behaviour may differ (they retrieve more distinctive date/jurisdiction text).
- **Abstention is lexical** for the Qwen arm (frozen PoC-020 regex) — a paraphrased decline could be
  missed, which would *understate* Qwen's CAR, making the gate look relatively better than it is; the
  gap is so large (−72.5pp) this cannot change the verdict.
- **Gate signal = top-1 raw semantic cosine** (same as PoC-021). A learned confidence signal
  (top1−top2 margin, NLI entailment of the answer against the chunk) is untested and is the sensible
  follow-up if an abstainer cheaper than full generation is ever needed.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 \
  -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Q4.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &

cd poc/026-absent-extractive-routing
python3 absent-routing.py
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `evo-g2-3` · technique: facet-recombination · attacks: OP-4
- Gates (0–10): G1 6.5 · G2 6.0 · G3 6.25 · null-control Δ5.75 (real 6.0 vs null 0.25)
- Tournament: rank 6, elo 981.1 · priority 📊 MEDIUM (7.57)
- Provenance: idea-evolution-engine (private) scan 2026-10-22. Gate-approved + null-control-screened, NOT yet empirically validated.
