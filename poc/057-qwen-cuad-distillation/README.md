# PoC 057: KD fine-tune Qwen on GPT-4 CUAD rationale-answer pairs (OP-2) — PARKED (infra)

| | |
|---|---|
| Status | **Registered — PARKED (blocked on training infrastructure).** Not runnable in the current host/inference-only lab environment; registered for provenance + a clear unblock path (precedent: PoC-012 parked on device). |
| Verdict | _pending — requires a fine-tuning environment + teacher-data access._ |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Source idea | Inbox `2026-10-27-finetuning-qwen2515b-on-gpt4generated-cuadstyle-rationaleanswer-pairs` (engine `gh-Awesome-KD-of-LLMs-idea-3`, OP-2). |
| Registered | 2026-10-27 (before the first run). |

## Question

Does white-box KD — SFT Qwen2.5-1.5B on GPT-4-generated CUAD rationale-answer pairs — lift hard-category
answer quality (key-fact / span-F1) by ≥ 3 pp over the base model, at the same inference footprint?

## Why it matters here

- PoC-040/049 identified the 1.5B *generator* as the answer-step ceiling; a distilled, domain-specialised
  student could raise that ceiling without changing runtime size/RAM.

## Why this is PARKED (not run)

Unlike every prior PoC in this lab, 057 is **not an inference-only experiment**. Conducting it requires:
1. **Teacher data generation** — GPT-4 (or equivalent) API access to produce CUAD-style rationale-answer
   pairs at scale. Not available in this environment.
2. **A fine-tuning run** — LoRA/SFT of Qwen2.5-1.5B (GPU hours + training stack: PEFT/axolotl/llama-factory).
   The lab host runs inference (llama.cpp/MPS) only; no training pipeline is set up.
3. **Re-quantize + evaluate** the tuned student back into the gguf/6 GB slot.

Faking any of these would violate the lab's "run the real experiment" discipline. 057 is therefore
**registered and parked**, exactly as PoC-012 was parked on the physical-device requirement.

## Hypothesis / Method / Decision rule (for when unblocked)

- **H1:** tuned student hard-category key-fact / span-F1 ≥ +3 pp over base Qwen2.5-1.5B Q4_K_M on the CUAD
  eval (PoC-042 key-fact / PoC-036 span-F1), at equal inference footprint.
- **Method (when a training env is available):** (1) generate N≈2–5k teacher rationale-answer pairs over CUAD
  train contracts with a strong teacher; (2) LoRA-SFT Qwen2.5-1.5B; (3) merge + quantize to Q4_K_M;
  (4) evaluate on the held-out CUAD eval vs base, same retrieval. **Guard:** check absent-clause CAR does not
  regress (over-confident student risk).
- **Decision rule:** adopt if H1 ∧ CAR not worse > 3 pp; reject if < +1 pp; inconclusive between.

## Unblock path

Run on a training-capable host with teacher-model access; or substitute an existing open legal-SFT Qwen
checkpoint if one appears (evaluate-only, which *would* be lab-runnable).

---
### Engine provenance
`gh-Awesome-KD-of-LLMs-idea-3` · OP-2 · UNSCREENED. Parked on training infrastructure; verdict deferred.
Feeds back to the ledger as parked (not reject) so the engine does not re-propose it as runnable here.
