# PoC 001: KV cache quantization for Gemma E2B on 6 GB iPhones

| | |
|---|---|
| Status | Written up (host stage) |
| Verdict | Reject: stop, not the constraint. The unquantized cache already fits 4,096 context |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | None (published before the lab had reviewers) |
| Source idea | llama.cpp's quantized KV cache (`--cache-type-k` / `--cache-type-v`, `q8_0` and `q4_0`); the quantized V cache needs flash attention |
| Registered | 2026-09-23, in the commit that adds this file, before the first run |

## Question

Can a quantized KV cache let Gemma E2B run at 4,096 context in no more memory than the
Unawain app's shipped 2,048-context settings use, without a measurable loss in output quality?

## Why it matters here

On 6 GB iPhones, Unawain runs Gemma E2B Q4_K_M at 2,048 context in every thermal state
(commit b0124e6; see [architecture](../../docs/architecture/README.md#llm-context-policy)).
After the prompt and a 512-token reserve for the answer, that leaves room for roughly 2,000
characters of Filipino text, so longer documents get compressed or summarized
extractively first. The app notes say the cap is for thermal stability as well as memory.
This PoC tests the memory side; the thermal side needs a device run.

The shipped settings have flash attention off. A quantized V cache needs it on, so the arms
below separate the effect of flash attention from the effect of cache type.

## Hypotheses

All HYPOTHESIS until measured.

1. Per cell, q8_0 takes about 53% of f16's bytes (34 bytes per 32 values against 64) and q4_0
   about 28% (18 against 64).
2. Most Gemma layers use sliding-window attention, so their cache stays at the window size.
   Going from 2,048 to 4,096 context should therefore less than double the total KV cache.
3. q8_0 K and V at 4,096 context: mean KL divergence from the shipped settings under 0.01 and
   the same top token at least 97% of the time. q4_0 measurably worse than q8_0.
4. If going from 2,048 to 4,096 context at the shipped f16 settings adds less than 100 MB of
   KV and compute buffers, the KV cache is not what holds 6 GB phones at 2,048, and
   quantizing it is not needed for this goal.

## Method

**Model.** `google_gemma-4-E2B-it-Q4_K_M.gguf` from
[bartowski/google_gemma-4-E2B-it-GGUF](https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF),
3,462,680,032 bytes, SHA-256 `923c4c86177d2ee173a7f5b4fa3d0ac65f5962ab15e6d6a5bc250aec4fd7bf7e`.
The same file Xylo downloads. Gemma license: see the model page. Not committed.

**Tooling.** llama.cpp 0.4.1 (build 10964, commit b29c606e2) from Homebrew: `llama-bench`
and `llama-perplexity`, Metal backend.

**Host.** MacBook Pro, Apple M4 Pro, 24 GB, macOS 26.5.1, on AC power. The host shows memory
allocation and quality, which depend on the model and settings, not on the device. Its speed
numbers do not transfer to an iPhone GPU.

**Fixed settings**, mirroring the shipped low-tier settings: all layers on the GPU, 2 threads,
`n_batch` 2048, `n_ubatch` 128.

**Arms.**

| Arm | K cache | V cache | Flash attention |
|---|---|---|---|
| `f16-nofa` (shipped) | f16 | f16 | off |
| `f16-fa` | f16 | f16 | on |
| `q8k-nofa` | q8_0 | f16 | off |
| `q8-fa` | q8_0 | q8_0 | on |
| `q4-fa` | q4_0 | q4_0 | on |

**Memory and speed.** `llama-bench`, one process per arm and context size, with the prompt at
512 tokens, generation at 128, and depth set so the context is exactly 2,048, 4,096 or 8,192
(depth 1,408, 3,456, 7,552). Three repetitions. Recorded per run: KV and compute buffer sizes
from the llama.cpp log, the process's peak memory footprint from `/usr/bin/time -l`, and
prefill and decode tokens per second at that depth.

**Quality.** `llama-perplexity` on the Tagalog text of José Rizal's *Noli Me Tangere*
([Project Gutenberg #20228](https://www.gutenberg.org/ebooks/20228), public domain,
header and footer stripped). Reference log-probabilities come from the shipped arm at the same
context size (`--kl-divergence-base`); every other arm is compared against them
(`--kl-divergence`). Context 2,048 with 8 chunks and 4,096 with 4 chunks, so both score about
8,000 tokens. Recorded: mean KL divergence, the share of tokens where the top prediction
matches, and perplexity. Tagalog because it is the language Unawain summarizes; it also
tokenizes densely, which is the case that fills a context fastest.

## Decision rule

For the host stage the outcome is *proceed to a device run* or *stop*. A PoC-level *adopt*
needs a 6 GB iPhone run.

- **Proceed** with an arm if, at 4,096 context:
  1. its KV plus compute buffers are no larger than the shipped arm's at 2,048, plus 10%;
  2. mean KL divergence from the shipped arm is at most 0.01 and the top token matches at
     least 97% of the time;
  3. decode speed is at least 80% of the shipped arm's at 2,048.
- **Stop, not the constraint** if hypothesis 4 holds: the shipped arm grows by less than
  100 MB from 2,048 to 4,096. The next question is then thermal, not memory.
- **Stop, rejected** if no quantized arm meets 1 and 2.
- Otherwise **inconclusive**, with the failing criterion named.

## Results

Run 2026-09-23 on the host above. Every number here is MEASURED on the host unless it is tagged
otherwise. Raw logs are in [`results/raw`](results/raw). The tables below are
[`results/summary.md`](results/summary.md), generated by `summarize.py`, which also writes
[`results/summary.json`](results/summary.json).

**Memory and speed.** KV and compute buffers are for the prefill context (`n_ctx` equal to the
context size). Peak footprint is the whole process, from `/usr/bin/time -l`. It leaves out the
memory-mapped weights, which take 3,287 MiB on the GPU in every arm. Speeds are mean ± SD over three
repetitions, measured at depth (context minus 640).

| Arm | Context | KV MiB | Compute MiB | KV + compute MiB | Peak footprint MiB | Prefill tok/s | Decode tok/s |
|---|---|---|---|---|---|---|---|
| f16-nofa (shipped) | 2048 | 25.50 | 142.13 | 167.63 | 295.1 | 1042.13 ± 1.96 | 80.14 ± 0.15 |
| f16-nofa (shipped) | 4096 | 37.50 | 143.13 | 180.63 | 306.9 | 983.26 ± 9.12 | 76.07 ± 0.59 |
| f16-nofa (shipped) | 8192 | 61.50 | 148.63 | 210.13 | 338.8 | 898.2 ± 2.66 | 67.8 ± 0.23 |
| f16-fa | 2048 | 21.00 | 136.07 | 157.07 | 266.9 | 1019.73 ± 3.82 | 86.26 ± 1.93 |
| f16-fa | 4096 | 33.00 | 136.57 | 169.57 | 274.3 | 935.41 ± 5.08 | 84.05 ± 2.84 |
| f16-fa | 8192 | 57.00 | 144.14 | 201.14 | 324.0 | 796.77 ± 3.49 | 79.66 ± 2.54 |
| q8k-nofa | 2048 | 20.58 | 139.00 | 159.58 | 274.7 | 1030.93 ± 1.69 | 75.8 ± 1.87 |
| q8k-nofa | 4096 | 29.77 | 140.00 | 169.77 | 289.8 | 962.11 ± 2.56 | 73.91 ± 0.43 |
| q8k-nofa | 8192 | 48.14 | 142.00 | 190.14 | 317.8 | 860.31 ± 1.17 | 66.57 ± 0.77 |
| q8-fa | 2048 | 11.16 | 137.35 | 148.51 | 258.0 | 984.54 ± 2.05 | 73.13 ± 7.82 |
| q8-fa | 4096 | 17.53 | 137.85 | 155.38 | 281.3 | 912.64 ± 1.51 | 70.36 ± 8.0 |
| q8-fa | 8192 | 30.28 | 138.85 | 169.13 | 310.0 | 639.92 ± 14.55 | 52.59 ± 1.36 |
| q4-fa | 2048 | 5.91 | 137.35 | 143.26 | 256.1 | 679.36 ± 19.02 | 46.8 ± 8.3 |
| q4-fa | 4096 | 9.28 | 137.85 | 147.13 | 257.3 | 502.16 ± 6.16 | 33.55 ± 0.77 |
| q4-fa | 8192 | 16.03 | 138.85 | 154.88 | 281.5 | 394.44 ± 1.81 | 34.52 ± 4.06 |

**Quality.** Each arm is compared against reference logits from the shipped arm at the same
context size. That is 8,192 scored tokens per row: 8 × 1,024 at 2,048 context and 4 × 2,048 at
4,096. Values are mean ± standard error. The shipped arm compared against its own reference shows
the run-to-run noise floor.

| Arm | Context | Mean KLD | Same top token % | PPL |
|---|---|---|---|---|
| f16-nofa (shipped) | 2048 | 0.000000 ± 0.000000 | 99.99 ± 0.01 | 348.30 ± 19.98 |
| f16-nofa (shipped) | 4096 | 0.000000 ± 0.000000 | 100.00 ± 0.00 | 339.56 ± 20.11 |
| f16-fa | 2048 | 0.000011 ± 0.000001 | 99.76 ± 0.06 | 348.29 ± 19.98 |
| f16-fa | 4096 | 0.000008 ± 0.000000 | 99.93 ± 0.03 | 339.47 ± 20.10 |
| q8k-nofa | 2048 | 0.000337 ± 0.000034 | 99.25 ± 0.10 | 348.12 ± 19.97 |
| q8k-nofa | 4096 | 0.000565 ± 0.000071 | 99.06 ± 0.11 | 340.05 ± 20.14 |
| q8-fa | 2048 | 0.000625 ± 0.000079 | 98.88 ± 0.12 | 348.30 ± 19.98 |
| q8-fa | 4096 | 0.000597 ± 0.000043 | 98.95 ± 0.11 | 339.86 ± 20.12 |
| q4-fa | 2048 | 0.078903 ± 0.002427 | 87.24 ± 0.37 | 337.09 ± 19.23 |
| q4-fa | 4096 | 0.088810 ± 0.002857 | 86.92 ± 0.37 | 326.00 ± 19.18 |

**Hypotheses.**

1. **Held.** Compared with f16, q8_0 takes 53.1% of the KV bytes and q4_0 takes 28.1%, at all
   three context sizes (flash-attention arms).
2. **Held, and the effect is stronger than expected.** Of Gemma E2B's 35 layers, 20 reuse
   another layer's KV cache. Of the 15 that keep their own, 12 use a 512-token sliding window,
   which llama.cpp stores as a fixed 768-cell cache. Only 3 layers grow with context. For the
   shipped arm, doubling the context from 2,048 to 4,096 multiplies the KV cache by 1.47.
   Quadrupling it to 8,192 multiplies it by 2.41.
3. **Held.** At 4,096 context, q8_0 K and V has a mean KLD of 0.0006 and matches the top token
   98.95% of the time. q4_0 is much worse: mean KLD 0.089 and 86.9% top-token agreement. Its lower
   perplexity on this text comes with large divergence, so it is drift, not an improvement
   (INFERRED).
4. **Held.** At the shipped settings, going from 2,048 to 4,096 context adds 13.0 MiB of KV and
   compute buffers (180.63 − 167.63). The threshold was 100 MB. Going to 8,192 adds 42.5 MiB.

**Decision.** Criteria 1 to 3 of *proceed* at 4,096 context, against the shipped arm at 2,048
(167.63 MiB, 80.14 tok/s decode):

| Arm at 4,096 | KV + compute ≤ 184.39 MiB | KLD ≤ 0.01 and top ≥ 97% | Decode ≥ 64.11 tok/s |
|---|---|---|---|
| f16-nofa (shipped, unchanged) | 180.63, yes | reference | 76.07, yes |
| f16-fa | 169.57, yes | 0.000008 / 99.93%, yes | 84.05, yes |
| q8k-nofa | 169.77, yes | 0.000565 / 99.06%, yes | 73.91, yes |
| q8-fa | 155.38, yes | 0.000597 / 98.95%, yes | 70.36, yes |
| q4-fa | 147.13, yes | 0.089 / 86.92%, no | 33.55, no |

Hypothesis 4 holds, and the shipped settings pass every criterion at 4,096 context without any
change. The outcome is therefore **stop, not the constraint** (Deviations explains how the
rule's order was resolved). Quantizing the KV cache is not what stands between these phones and 4,096 context.
At 4,096, q8_0 saves 25 MiB compared with the shipped settings at the same context. The weights on
the GPU take 3,287 MiB, so that saving is under 1% of it (MEASURED sizes; the share is
arithmetic).

Two more OBSERVED points that are worth a device check, but not under this PoC:

- Turning flash attention on by itself shrinks the buffers by 11 MiB at 4,096 and decodes 10%
  faster on the host. Without it, llama.cpp pads the V cache to 512 dimensions, because Gemma's V
  head sizes differ between layer types.
- On this Metal build, q4_0 and deep-context q8_0 are slower than f16. Host speed does not
  transfer to A-series GPUs, but q4_0 at 42% of shipped decode speed is a large gap.

**What this points to next** (HYPOTHESIS). The app notes give thermal stability as the other
reason for the 2,048 cap. The next question is whether a 4,096-context summary on a 6 GB iPhone
stays within thermal limits over repeated runs. That needs a device harness around llama.cpp and
belongs in its own PoC.

## Deviations

- 2026-09-23, after the run. Both *proceed* (for every arm except q4-fa) and *stop, not the
  constraint* came out true, and the rule did not say which one wins. *Stop, not the
  constraint* was applied. The reason: the shipped arm meets the *proceed* criteria on its own, so proceeding
  with a quantized arm would test a change the goal does not need. The pre-registered text of
  hypothesis 4 says the same thing.
- `results/raw/conditions.txt` recorded a backend load message in place of the llama.cpp version,
  because `llama-bench --version` prints logs first. The version is in every bench JSON
  (`build_number` 10964, `build_commit` b29c606e2). `run.sh` now reads it from `llama-cli`.
- In the KLD runs, llama-perplexity's `Mean PPL(base)` line (323.54 at 2,048) does not match the
  reference run's own final estimate (348.30). The shipped arm's recomputed perplexity does match
  it, at 348.30. The tables report each arm's own perplexity and leave the `PPL(base)` line out.

## Limits

- The host is not an iPhone. Buffer sizes and quality carry over; speed, footprint limits,
  thermal behavior and flash attention stability on A-series GPUs do not.
- One model, one quantization of it, one language, one text.
- KL divergence and top-token agreement measure next-token drift, not summary quality.
- The text is Pascual H. Poblete's Tagalog translation in old orthography (for example `n~g`),
  scored as raw text without the chat template. Absolute perplexity (about 340) is high and only
  meaningful as a comparison between arms.
- The footprint column is the host process without its mapped weights. It is not a prediction of
  an iOS memory limit.

## Reproduce

```sh
cd poc/001-kv-cache-quantization
./run.sh            # downloads the text, checks the model hash, runs every arm
python3 summarize.py
```

The model must be at `models/google_gemma-4-E2B-it-Q4_K_M.gguf`; `run.sh` prints the
download command if it is missing.

## Replications

Replications of the host stage are open. The steps and the evidence standard are in
[CONTRIBUTING.md](../../CONTRIBUTING.md); open a Replication issue before running.

- **Needs:** an Apple silicon Mac with Homebrew `llama.cpp`, and about 9 GB of free disk (the
  3.46 GB model plus a roughly 4.3 GB KL-divergence base file). The original run peaked at
  3.74 GB resident memory (MEASURED).
- **Run** into a folder named `YYYY-MM-DD-<github-handle>-<device>`:

  ```sh
  cd poc/001-kv-cache-quantization
  R=replications/2026-10-01-yourhandle-m2-air
  OUT=$R/results/raw ./run.sh
  python3 summarize.py $R/results
  cp ../_template/REPLICATION.md $R/README.md   # then fill it in
  ```

- **Record** the `llama.cpp` version from `conditions.txt`. A different build is allowed, but
  it is a deviation, and the comparison has to say so.
- Absolute numbers will differ between chips. The comparison is about whether each hypothesis
  and decision criterion comes out the same way.

| Date | Device | Authors | Outcome |
|---|---|---|---|
| None yet | | | |
