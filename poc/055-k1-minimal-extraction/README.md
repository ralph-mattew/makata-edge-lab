# PoC 055: Minimal single-chunk (k=1) extraction prompt (OP-2)

| | |
|---|---|
| Status | Concluded — host stage (300 hard items; span-F1). |
| Verdict | **Reject k=1 — single-chunk extraction underperforms k=3; the "less context" premise fails.** Across the 2×2 (arm × depth), the best **k=1** arm (cosine 21.7) is **−1.8 below** the best **k=3** arm (Qwen-copy 23.5). Cutting to the top chunk does not help the 1.5B — it drops the rank-2/3 gold the extractor sometimes needs, and that loss outweighs any distractor-removal benefit. Per-cat it's a wash-to-worse (k=1 helps Change-of-Control a touch, hurts Non-Compete). H1 (k=1 ≥ +3 over k=3) FAIL → **REJECT k=1; keep k=3.** Consistent with PoC-036/047 (depth helps the extractor) and PoC-059 (more context helps generation) — the "minimum viable context" idea does not transfer to this stack. Control: copy_k3 23.5 reproduces PoC-047. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Source idea | Inbox `2026-10-27-a-minimal-singlechunk-extraction-prompt-fixing-k1` (engine `evo-g2-6`, structured-blend, OP-2; false-null screen). |
| Registered | 2026-10-27 (before the first run). |

## Question

Does fixing **k=1** (top chunk only) + a bare span-extraction prompt beat the k=3 answer step on
hard-category **span-F1**, avoiding both the instruction-overload (PoC-042) and context-dilution the
Raspberry-Pi study reported for small Qwen (k=3→k=5: 75%→52%)?

## Why it matters here

- PoC-047 found minimal Qwen verbatim-copy ≈ generator-free cosine (inconclusive, +2.1) at k=3. This isolates
  the **retrieval depth** for the answer step: does k=1 (one clause, no distractors) help the 1.5B?
- Hard-cat key-fact is undefined (no typed key_facts, PoC-042) → scored by **span-F1** (018/036 definition).

## Hypothesis

One highly-relevant chunk + one imperative removes both distraction and instruction load; but k=1 also loses
the rank-2/3 gold the extractor sometimes needs.

- **H1:** k=1 extraction hard-mean span-F1 ≥ +3 over the k=3 generator-free extractor (PoC-036 ≈ 20.7 at N=3).
- **H2:** k=1 ≥ k=3 for the Qwen-copy arm too (depth, not prompt, is the lever).

## Method

Fork PoC-047: arms = {generator-free cosine extractor, Qwen bare-extract} × depth {k=1, k=3}, on the 300
hard items, span-F1 (SQuAD overlap vs gold). Retrieval = PoC-016 decomposition (held fixed). Deterministic.

## Decision rule

Adopt k=1 if hard-mean span-F1 ≥ +3 over the k=3 best arm. Reject if k=1 < k=3. Inconclusive between.

## Harness

`k1-extract.py` forks PoC-047: 2×2 of {generator-free cosine extractor, Qwen verbatim-copy} × depth {k=1,
k=3} on the 300 hard items, PoC-016 decomposed retrieval held fixed, span-F1 (SQuAD overlap vs gold).
Reads committed vectors via `LAB_POC_ROOT`; EmbeddingGemma :8090 (cosine sentences) + Qwen :8091 (copy).

## Results

MEASURED on the host (EmbeddingGemma + Qwen2.5-1.5B Q4_K_M, temp 0), **300 hard items**, span-F1.

| Arm | hard-mean | Exclusivity | Non-Compete | Change-of-Control |
|---|---|---|---|---|
| cosine, k=1 | 21.7 | 13.4 | 15.1 | 36.7 |
| cosine, k=3 | 21.4 | 11.8 | 20.6 | 31.7 |
| copy, k=1 | 21.1 | 12.0 | 12.9 | 38.4 |
| **copy, k=3** (best) | **23.5** | 9.3 | 18.0 | 43.2 |

- **Control:** copy_k3 23.5 / cosine_k3 21.4 reproduce PoC-047. MEASURED.
- **H1 (best k=1 ≥ +3 over best k=3):** FAIL — best k=1 (cosine, 21.7) is **−1.8** vs best k=3 (copy, 23.5).
  MEASURED.
- k=1 slightly helps Change-of-Control (clean single sentence) but hurts Non-Compete (loses rank-2/3 gold);
  net negative. MEASURED.

Summary in `results/k1-extract.json`.

## Verdict

**Reject k=1 — keep k=3.** The proposal's premise (a 1.5B does better with the *minimum viable context*:
one chunk, one imperative) does not hold for the answer step on this stack. Cutting retrieval depth to the
single top chunk removes two "distractor" chunks but also removes the rank-2/3 chunks that often carry the
gold span for the hard categories (PoC-025 showed Non-Compete gold sits at rank 4–10), and the net is −1.8
span-F1. This agrees with PoC-036 (deeper extractor pools help, N=10 > N=3) and PoC-059 (k=5 > k=3 for
generation): **more context helps this stack, not less** — the Raspberry-Pi "less is more" finding does not
transfer to CUAD. The adopted answer step remains the generator-free extractor at k=3+ (PoC-036); k=1 is a
regression.

## Limits

- **span-F1 proxy**, hard categories only; CoC's small k=1 gain may be a clean-single-sentence artifact.
- Did not sweep k=2 (the −1.8 at k=1 and PoC-036's N=10 monotonic gains make a k=2 win unlikely).
- Retrieval held to PoC-016 decomposition (not the stronger PoC-053 clause-term binding).

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/055-k1-minimal-extraction
LAB_POC_ROOT=/path/to/lab-clone/poc python3 k1-extract.py
```

---
### Engine provenance
`evo-g2-6` · OP-2 · false-null screen. Overlaps PoC-047 (keep generator-free); isolates retrieval depth for the answer step. Verdict **REJECT k=1** (best k=1 −1.8 vs k=3; depth helps). Feeds back to the ledger.
