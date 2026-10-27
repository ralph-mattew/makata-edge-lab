# PoC 056: 2-bit Qwen quantization for RAM headroom (OP-8)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration. |
| Verdict | _pending._ |
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

## Harness (run-time)

`qwen-2bit.py` reuses the PoC-042 key-fact path + PoC-041 CAR path, parameterised by `--qwen-url` (Q2_K
server). Downloads the gguf on first run. Reads committed vectors via `LAB_POC_ROOT`.

---
### Engine provenance
`arxiv-2610.34886v1-idea-2` · OP-8 · UNSCREENED. New front (RAM), no overlap with closed hard-cat avenues.
Verdict feeds back to the ledger.
