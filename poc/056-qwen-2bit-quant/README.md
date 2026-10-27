# PoC 056: 2-bit Qwen quantization for RAM headroom (OP-8)

| | |
|---|---|
| Status | Concluded — host stage (464 typed-fact + 101 absent hard items; key-fact + CAR). |
| Verdict | **Reject — 2-bit Qwen destroys absent-clause abstention.** Q2_K (645 MB vs ~1.0 GB Q4) holds key-fact extraction nearly intact (**66.8 → 62.9, −3.9**) but **collapses absent-clause CAR from 84.2% → 3.0% (−81.2 pp)** — it stops saying "not stated" and instead echoes irrelevant context as a confident (hallucinated) answer. Verified by direct probe: asked for an exclusivity clause with only a term clause in context, Q2_K answers "The term of this Agreement is five years." H2 (≤0.7 GB) passes, but **H1 (−3.9, over the −3 bar) and H3 (CAR −81.2 ≫ −3) fail** → **REJECT.** 2-bit quantization preserves the easier *extraction* behaviour but wipes out the subtler *abstention/instruction-following* — the OP-7 faithfulness the stack depends on — so the ~0.35 GB saving is not worth it. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Source idea | Inbox `2026-10-27-applying-thinkbitstyle-2bit-scalar-quantization` (engine `arxiv-2610.34886v1-idea-2`, OP-8). |
| Registered | 2026-10-27 (before the first run). |

## Question

Does a **2-bit** Qwen2.5-1.5B (Q2_K) hold key-fact accuracy within **−3 pp** of the Q4_K_M baseline while
cutting the on-disk/RAM footprint from ~1.0 GB to ~0.5–0.7 GB — freeing headroom (OP-8) for a larger
generator / longer context / a resident embedder?

## Why it matters here

- Qwen Q4_K_M ≈ 1.0 GB is the largest single component after the OS budget; a near-lossless 2-bit checkpoint
  roughly doubles what PoC-035 freed from the index. Every future RAM-bound PoC benefits.
- The claim to test is **reasoning/answer-quality preservation** at 2-bit — unverified on our CUAD stack.

## Hypothesis

Q2_K degrades a 1.5B more than it does a large model (fewer redundant params), so some key-fact loss is
expected; the question is whether it stays within −3 pp for the RAM saving.

- **H1:** key-fact accuracy (464 typed-fact items, PoC-042 metric) within **−3 pp** of Q4_K_M.
- **H2:** model file ≤ 0.7 GB (vs ~1.0 GB Q4_K_M), freeing ≥ 300 MB.
- **H3:** absent-clause CAR (hard) not worse by > 3 pp (abstention preserved).

## Method

Download `Qwen2.5-1.5B-Instruct-Q2_K.gguf` (bartowski). Serve via llama-server (same config as the Q4
baseline). Re-run the PoC-042 key-fact harness (464 typed-fact items, hybrid 0.9/0.1 top-3) + the PoC-041
absent/answerable hard CAR arm, comparing Q2_K vs Q4_K_M. Record model bytes + host RSS. Deterministic
(temp 0). Also report IQ2_M as a secondary point if time permits.

## Decision rule

Adopt Q2_K if **H1 (key-fact ≥ −3 pp) ∧ H2 (≤0.7 GB) ∧ H3 (CAR ≥ −3 pp)**. Reject if key-fact drops > 6 pp.
Inconclusive between (document the RAM/quality tradeoff curve).

## Harness

`qwen-2bit.py` runs the PoC-042 key-fact path (464 typed-fact items) + absent-clause CAR (101 PoC-008 hard
items) against two Qwen servers — Q4_K_M (:8091) and Q2_K (:8092) — on identical hybrid 0.9/0.1 top-3
retrieval, and reports the deltas. Deterministic (temp 0). Reads committed vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (Qwen2.5-1.5B-Instruct, temp 0; Q2_K from bartowski-GGUF = 645 MB vs Q4_K_M ~1.0 GB).

| Model | file | key-fact (464) | absent CAR (101 hard) |
|---|---|---|---|
| Q4_K_M (baseline) | ~1.0 GB | 66.8 | 84.2% |
| **Q2_K (2-bit)** | **645 MB** | 62.9 | **3.0%** |
| Δ | −~0.35 GB | **−3.9** | **−81.2 pp** |

- **Control:** Q4 key-fact 66.8 / CAR 84.2 reproduce PoC-042 / PoC-041. MEASURED.
- **H2 (≤0.7 GB):** PASS — 645 MB. MEASURED.
- **H1 (key-fact ≥ −3 pp):** FAIL (just) — −3.9. MEASURED.
- **H3 (absent CAR ≥ −3 pp):** **FAIL catastrophically — −81.2 pp.** MEASURED.
- **Direct probe** (exclusivity question, term-only context): Q2_K replies *"The term of this Agreement is
  five years."* instead of "not stated" — it echoes context rather than abstaining. OBSERVED.

Summary in `results/qwen-2bit.json`.

## Verdict

**Reject.** 2-bit quantization looks almost free on the headline extraction metric (key-fact −3.9) but is
**catastrophic for abstention**: absent-clause CAR collapses 84.2% → 3.0%. The 2-bit model retains the
easier, high-frequency behaviour (pull a fact out of a relevant passage) but loses the subtler,
instruction-dependent behaviour (recognise that the clause is *absent* and decline) — precisely the OP-7
faithfulness the stack was built to protect (PoC-026/008). A generator that hallucinates a confident answer
on ~97% of absent clauses is unusable regardless of the ~0.35 GB it frees. Q2_K is **not** a viable RAM path
for this stack.

Two broader takeaways: (1) **evaluate quantization on abstention, not just extraction** — a single
accuracy number hides the failure; (2) the OP-8 RAM front is not opened by crushing the generator — freed
RAM must come from elsewhere (e.g. PoC-035's binary index) without touching the generator's instruction
fidelity. A gentler step (Q3_K_M / IQ3) might preserve abstention; untested here (left as a follow-up), but
2-bit is too aggressive.

## Limits

- **Q2_K only** (one 2-bit scheme); IQ2_M / Q3_K_M not swept — a 3-bit tier may land within budget without
  the abstention collapse (follow-up).
- **Not the paper's exact ThinkBit layerwise scheme** — a pragmatic llama.cpp Q2_K stand-in; a
  reasoning-preserving layerwise 2-bit *might* differ, but the shipped-stack-feasible option (Q2_K) fails.
- key-fact on typed-fact items; CAR on hard absent items (the faithfulness-critical slice).

## Reproduce

```bash
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q2_K.gguf>   -c 4096 -ngl 99 --port 8092 --log-disable &
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
cd poc/056-qwen-2bit-quant
LAB_POC_ROOT=/path/to/lab-clone/poc python3 qwen-2bit.py
```

---
### Engine provenance
`arxiv-2610.34886v1-idea-2` · OP-8 · UNSCREENED. New front (RAM), no overlap with closed hard-cat avenues.
Verdict feeds back to the ledger.
