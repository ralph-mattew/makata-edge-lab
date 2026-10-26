# PoC 047: Retrieve-then-extract — minimal Qwen verbatim-copy extraction (OP-1)

| | |
|---|---|
| Status | Concluded — host stage (300 hard-category items; span-F1). |
| Verdict | **Inconclusive — Qwen verbatim-copy doesn't beat the generator-free extractor overall; keep PoC-036.** Minimal Qwen copy reaches hard-mean span-F1 **23.5 vs 21.4** for the PoC-036 cosine extractor (**+2.1**, below the +5 bar → H1 FAIL), and the gain is **entirely Change-of-Control** (31.7 → **43.2**, +11.5) while **Exclusivity (−2.5) and Non-Compete (−2.6) regress**. Verbatim-substring compliance is only **56.3%** (the 1.5B paraphrases despite "copy verbatim", echoing 043). Free-generation is far worse (14.5, 1.3% compliance — confirms 042/044). Practically: **keep the generator-free extractor (036)**; copy only helps CoC, so at most a per-category router would use it. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | Inbox `2026-10-26-a-retrievethenextract-prompting-strategy` (engine `evo-g2-6`, structured-blend, OP-1). The **only micro-lab-screened** new item (mixed, 2× cuad_hard:CONFIRMED). |
| Registered | 2026-10-26 (before the first run). |

## Question

Does a **minimal** retrieve-then-extract prompt — give Qwen2.5-1.5B the top-3 chunks and instruct it ONLY
to copy the single most relevant clause **verbatim** (no paraphrase, no citation, no abstention) — beat the
**generator-free** PoC-036 cosine extractor on hard-category span-F1, without the instruction-following
collapse that sank PoC-042?

## Why it matters here

- The generation-side failures (042 −7.3, 044 −37.7) all imposed **compound** load (cite + abstain +
  self-critique). The adopted answer step (018/036) is **generator-free** cosine sentence selection. The
  untested middle ground is **pure verbatim copy by the generator** — the simplest possible generation task.
  Does using the 1.5B to *pick and copy* a clause beat picking it by cosine?
- Retrieval runs first on raw queries (no HyDE-style routing-through-the-generator, which 038 showed is
  lossy) — the generator only acts on retrieved text, the regime where it's least likely to hallucinate.

## Hypothesis

Verbatim copy is low-load and low-hallucination; it may select the gold clause better than cosine when
multiple sentences are plausible. Untested on our stack.

- **H1:** hard-mean span-F1 ≥ **+5 pp** over the PoC-036 generator-free extractor (22.1 at N=10 / 20.7 at N=3).
- **H2:** does **not** regress vs the same-retrieval Qwen baseline the way 042 did (answerable answers not lost).
- **H3 (grounding):** the copied text is a real substring of the retrieved chunks on ≥90% of items
  (verbatim-copy compliance; contrast PoC-043's 56.5% citation / grounding failures).

## Method

Reuse the PoC-036 retrieval + eval (committed PoC-014 chunks, PoC-016 decomposed retrieval, top-3, 300
hard-cat items, gold spans). **Answer step:** prompt Qwen *"Copy the single sentence from the sections
below that best answers the question, verbatim and nothing else."* Score **span-F1** (SQuAD token overlap
vs gold, identical to 018/036) — **not** key-fact (the hard categories carry no typed key_facts, cf.
PoC-042). Arms: (a) PoC-036 generator-free cosine extractor (reference), (b) Qwen verbatim-copy (headline),
(c) same-retrieval Qwen free-generation (PoC-042-style control). Measure verbatim-substring compliance.

- **Varies:** the answer step (Qwen copy vs cosine extract vs Qwen generate). **Held fixed:** retrieval,
  chunks, eval, span-F1 scorer, Qwen temp 0. **Measurements:** per-cat + hard-mean span-F1, substring
  compliance; contract-level bootstrap CI. **Repetitions:** deterministic → single pass.

## Decision rule

Adopt if **H1 (span-F1 +≥5 over 036)**. Reject if span-F1 **< 036** (cosine extraction wins — keep
generator-free). Inconclusive if within ±5. Report compliance + the generate-arm contrast.

## Expected outcome (engine estimate)

mixed · confidence ~0.45 · est. effort 2-3 days

## Harness

`retrieve-extract.py` forks `036/extract-depth.py`: identical PoC-016 decomposed retrieval (top-3). Three
answer arms on the same retrieval — `cosine` (036 generator-free ≤3-sentence window), `copy` (Qwen verbatim
sentence copy, :8091), `generate` (Qwen free generation) — scored by span-F1 (018/036 definition), plus a
verbatim-substring compliance check. Reads committed vectors via `LAB_POC_ROOT`.

## Results

MEASURED on the host (EmbeddingGemma `--embd-gemma-default` + Qwen2.5-1.5B Q4_K_M, temp 0), **300
hard-category items**, span-F1, deterministic single pass.

| Arm | hard-mean span-F1 | Exclusivity | Non-Compete | Change-of-Control | substring compliance |
|---|---|---|---|---|---|
| `cosine` (PoC-036, generator-free) | 21.4 | 11.8 | 20.6 | 31.7 | — |
| **`copy` (Qwen verbatim)** | **23.5** | 9.3 | 18.0 | **43.2** | 56.3% |
| `generate` (Qwen free) | 14.5 | 2.5 | 12.8 | 28.1 | 1.3% |

- **Control:** `cosine` 21.4 reproduces PoC-036 (20.7–22.1). MEASURED.
- **H1 (copy ≥ +5 over cosine):** FAIL — **+2.1**. MEASURED.
- **Category split:** copy's entire gain is **Change-of-Control +11.5** (31.7→43.2); it **regresses**
  Exclusivity (−2.5) and Non-Compete (−2.6). MEASURED.
- **H3 (verbatim compliance ≥ 90%):** FAIL — **56.3%**; the 1.5B reformats/paraphrases nearly half the time
  despite "copy verbatim" (same unreliability as PoC-043's 56.5% citation). MEASURED.
- **Free-generation** collapses to 14.5 (1.3% compliance) — re-confirms PoC-042/044. MEASURED.

Per-item in `results/raw/answers.jsonl`.

## Verdict

**Inconclusive — and the practical answer is "keep the generator-free extractor."** Stripping the generation
task to pure verbatim copy (no cite/abstain) did avoid the catastrophic collapse of PoC-042/044 — copy
(23.5) is far better than free-generation (14.5) — but it does **not** beat the generator-free cosine
extractor (21.4) by a meaningful margin (+2.1, below +5), and it is *worse* on two of the three hard
categories. The only real win is Change-of-Control (+11.5), where the answer is typically a single clean
sentence the model can lift intact; on Exclusivity/Non-Compete, cosine selection picks better than Qwen.

Two findings make this a non-adopt: (1) **the "verbatim" premise doesn't hold** — only 56.3% of copies are
actual substrings of the retrieved text, so the mechanism's safety guarantee (no hallucination because it's
copied) is violated nearly half the time; (2) adding a Qwen pass to the answer path costs ~1 GB + latency
for a net +2.1 that a per-category rule (apply copy to CoC only) could capture more cheaply. So the adopted
answer step remains **PoC-036 generator-free cosine extraction**, optionally with a CoC-specific copy arm as
a future micro-optimisation. This also sharpens the series' picture: even the *minimal* generation task
doesn't beat no-generation — the 1.5B adds no value at the answer step that cosine selection doesn't already
provide.

## Limits

- **span-F1 proxy**, hard categories only; CoC's copy win may be a clean-single-sentence artifact.
- **One copy-prompt wording**; a stricter decoding constraint (e.g. constrained generation to chunk
  substrings) might raise compliance, but that is a different mechanism.
- **Retrieval held to PoC-016 decomposition** (not the PoC-046 taxonomy / PoC-045 GreenLeaf); the answer-step
  comparison is on identical retrieval by design.

## Reproduce

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/047-retrieve-then-extract
python3 retrieve-extract.py        # or: LAB_POC_ROOT=/path/to/lab-clone/poc python3 retrieve-extract.py
```

---

### Engine provenance
- `evo-g2-6` · structured-blend · OP-1 · micro-lab screen **mixed** (2× cuad_hard:CONFIRMED). The minimal-load
  generation case 018/036 (no Qwen) and 042/044 (heavy load) never isolated. Verdict **INCONCLUSIVE** (copy +2.1 over cosine, below +5; keep generator-free 036) feeds back to the ledger.
