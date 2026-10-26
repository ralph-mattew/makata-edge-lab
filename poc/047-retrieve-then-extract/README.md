# PoC 047: Retrieve-then-extract — minimal Qwen verbatim-copy extraction (OP-1)

| | |
|---|---|
| Status | **Registered — host stage pending (not yet run).** Pre-registration: hypotheses + decision rule fixed before the first run. |
| Verdict | _pending._ |
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

## Harness (to be written at run time)

`retrieve-extract.py` forks `036/extract-depth.py`: same retrieval/sentences; adds a Qwen verbatim-copy
arm (:8091) + substring-compliance check; scores span-F1 vs 036's cosine arm and a free-generate arm.
Reads committed vectors via `LAB_POC_ROOT`.

## Reproduce (planned)

```bash
llama-server --embd-gemma-default --embedding --pooling mean --embd-normalize 2 -c 16384 --parallel 8 -b 16384 -ub 2048 --port 8090 --log-disable &
llama-server -m <Qwen2.5-1.5B-Instruct-Q4_K_M.gguf> -c 4096 -ngl 99 --port 8091 --log-disable &
cd poc/047-retrieve-then-extract && python3 retrieve-extract.py
```

---

### Engine provenance
- `evo-g2-6` · structured-blend · OP-1 · micro-lab screen **mixed** (2× cuad_hard:CONFIRMED). The minimal-load
  generation case 018/036 (no Qwen) and 042/044 (heavy load) never isolated. Verdict feeds back to the ledger.
