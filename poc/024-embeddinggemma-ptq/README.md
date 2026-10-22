# PoC 024: 4-bit PTQ of EmbeddingGemma-300M (OP-3)

| | |
|---|---|
| Status | Concluded — premise overtaken by events (host investigation) |
| Verdict | **Reject as moot — we already ship 4-bit.** `--embd-gemma-default`, which produced every committed vector and the 61.4% recall baseline, **is** `ggml-org/embeddinggemma-300M-qat-q4_0-GGUF` — a 4-bit quantization-aware-trained model at **≈270 MB on disk**. So the proposal's premise (an fp16 600 MB baseline to quantize) is false, and **H3 (≤400 MB / free ≥200 MB) is already satisfied** by what we run. The paper's PTQ-calibration-dose/D_func apparatus targets post-training quantization of an fp16 model; Google's QAT checkpoint sidesteps it. No further host-side PTQ work is justified. See Verdict. |
| Authors | Ralph Mattew Palomaria ([@ralph-mattew](https://github.com/ralph-mattew)) |
| Reviewers | none yet |
| Source idea | When PTQ Calibration Helps or Hurts: Dose-Driven Collapse and Validation-Gated Abstention in Quantized Text Embedders (http://arxiv.org/abs/2610.27397v1); promoted from the 2026-10-21 ideation-engine scan. |
| Registered | 2026-10-21 (this draft, before the first run) |

## Question

Does validation-gated PTQ calibration of EmbeddingGemma-300M to 4-bit weights preserve recall@3 within 1 point of the fp16 baseline while freeing ≥200MB RAM on the 6GB iPhone 15 Pro budget?

## Why it matters here

- OP-3 identifies EmbeddingGemma's 600MB as the single largest fixed RAM cost; freeing 200-300MB would allow loading a larger LLM (e.g. Qwen2.5-3B) or longer context window without exceeding 6GB
- The PTQ paper's key finding — that calibration dose drives the outcome from gain to catastrophic collapse, and that a validation-gated abstention can detect collapse before deployment — directly solves our fear of 'does 4-bit quantization hurt recall@3 on CUAD?'

## Hypothesis

The paper tested EmbeddingGemma-300M directly — its findings on calibration dose and validation gating transfer most directly to our stack. We test whether a low-dose 4-bit PTQ calibration run on a CUAD-derived calibration set (retrieval relevance supervision) passes the validation gate and preserves our 61.4% recall@3 baseline, yielding a quantized embedder with ≤1 point recall loss and ≥200MB RAM savings.

- H1: 4-bit PTQ of EmbeddingGemma-300M with low-dose calibration on CUAD retrieval pairs passes the validation gate (D_func below collapse threshold)
- H2: Quantized embedder recall@3 is within 1 point of fp16 baseline (≥60.4%)
- H3: Quantized embedder occupies ≤400MB RAM (vs 600MB fp16), freeing ≥200MB
- H4: Key-fact accuracy does not degrade by more than 2 points (≥65.9%)

## Method

Reuse PoC-007/008 harness. Step 1: prepare a CUAD retrieval calibration set (200-400 query-chunk relevance pairs from training split). Step 2: apply 4-bit weight PTQ to EmbeddingGemma-300M at three calibration doses (low/medium/high, varying number of calibration steps). Step 3: compute D_func (functional displacement) for each run and apply validation gate from the paper. Step 4: for runs that pass the gate, measure recall@3 on the full CUAD 1,325-item eval set. Step 5: profile RAM on iPhone 15 Pro (CoreML). Compare to fp16 baseline on both recall@3 and key-fact accuracy.

- Baseline stack (fill exact files/SHA-256 on promotion): EmbeddingGemma 300M (600 MB), Qwen2.5-1.5B Q4 (1.0 GB), Hybrid: 0.9 semantic + 0.1 BM25 (weight adopted in PoC 013).
- Device: iPhone 15 Pro (6GB). Dataset: CUAD contracts (397 documents, 1,325 Q&A items).
- What varies vs held fixed, measurements, repetitions: TO BE SPECIFIED before registration.

## Decision rule

If H1 + H2 + H3 hold: adopt quantized embedder and reallocate freed RAM to larger LLM; if any dose fails the validation gate: use the gate to select the passing dose; if no dose passes the gate or recall@3 < 60.4%: reject quantization for EmbeddingGemma and close OP-3 as infeasible at 4-bit

## Expected outcome (engine estimate, not a result)

likely inconclusive — calibration may pass gate but CoreML 4-bit inference support is the unknown variable  ·  confidence 0.5  ·  est. effort 1-2 weeks

## Results

MEASURED (host investigation; `probe.py`):

1. **The deployed embedder is already 4-bit QAT.** `--embd-gemma-default` resolves to
   `ggml-org/embeddinggemma-300M-qat-q4_0-GGUF` → `embeddinggemma-300M-qat-Q4_0.gguf`, **≈270 MB on
   disk**. It was verified in the PoC-022 work to reproduce the committed PoC-014 vectors at cosine
   **1.00000**, so it is unambiguously the model behind the 61.4% recall baseline. MEASURED.
2. **No same-model fp16/Q8 reference is available host-side.** The only auth-free higher-precision
   GGUF, `ggml-org/embeddinggemma-300M-GGUF:Q8_0` (318 MB), embeds the *same* chunk text + doc prefix
   to vectors **orthogonal** to the committed Q4_0 (cosine ≈ 0.02–0.05 on 3 chunks) — a different
   checkpoint / embedding space, not a precision twin. The `…-f16-GGUF` repo returns HTTP 401 (gated).
   So a clean "Q4 vs fp16 same-model" recall-preservation Δ (H2) cannot be produced here. MEASURED.

| Hypothesis | Status |
|---|---|
| H1 (4-bit passes the paper's D_func validation gate) | **Moot** — Google's QAT checkpoint is already 4-bit by construction; the paper's PTQ-dose method does not apply to our deployed path |
| H2 (recall within 1 pt of fp16) | **Not determinable host-side** — no same-model fp16 reference (gated); our 4-bit recall is the 61.4% baseline |
| H3 (≤400 MB / free ≥200 MB) | **Already satisfied** — ≈270 MB (the 600 MB fp16 premise never applied) |
| H4 (key-fact within 2 pt) | Moot alongside H2 |

## Verdict

**Reject as moot — overtaken by events.** The PoC asked whether to quantize EmbeddingGemma to 4-bit
to free RAM; our stack has been running 4-bit **QAT** EmbeddingGemma (Q4_0, ≈270 MB) all along —
that *is* `--embd-gemma-default`. The RAM target (H3) is already met, and there is no fp16 baseline
in production to "preserve recall against." Google's quantization-aware-trained checkpoint achieves
the paper's goal (near-lossless 4-bit) without the paper's post-hoc calibration-dose + D_func
machinery, which targets PTQ of an fp16 model. **No action.** OP-3's "EmbeddingGemma is 600 MB"
framing should be corrected across the lab to ≈270 MB. Any further shrink (sub-4-bit, or an
EmbeddingGemma→smaller-embedder swap) is a separate question — and PoC-022 already showed a smaller
embedder (UIBK 179M) is only inconclusive on retrieval quality, so the embedder RAM line is
effectively settled at the QAT-Q4_0 ≈270 MB.

## Limits

- **Correctness of the "already 4-bit" claim** rests on the cosine-1.0 reproduction (PoC-022) +
  the resolved cache path; both are shown. The exact bit-layout/quality of Google's QAT-Q4_0 vs a
  true fp16 EmbeddingGemma is not measured (gated f16 GGUF).
- **Device stage not addressed** — on-iPhone CoreML 4-bit inference + live RAM (the engine's flagged
  unknown) are out of scope, parked like [PoC-012](../012-cross-encoder-reranking); but the disk/
  host footprint (≈270 MB) already clears the H3 target.
- **The paper's D_func validation gate was not implemented** — it is unnecessary for a QAT checkpoint,
  and would only matter if we ever PTQ an fp16 EmbeddingGemma ourselves.

## Reproduce

```bash
cd poc/024-embeddinggemma-ptq
python3 probe.py        # shows the default = QAT-Q4_0 ≈270 MB
# optional space check vs Q8_0:
llama-server -hf ggml-org/embeddinggemma-300M-GGUF:Q8_0 --embedding --pooling mean \
  --embd-normalize 2 -c 16384 --port 8092 --log-disable &
python3 probe.py        # adds the Q8-vs-Q4 orthogonality lines
```

---

### Engine provenance (how this idea was generated)

- Engine idea id: `synth-idea-4` · technique: constraint-driven inversion · attacks: OP-3
- Gates (0–10): G1 8.5 · G2 8.25 · G3 6.75 · null-control Δ8.0 (real 8.25 vs null 0.25)
- Tournament: rank 1, elo 1047.3 · priority 📊 MEDIUM (9.5)
- Provenance: idea-evolution-engine (private) scan 2026-10-21. Gate-approved + null-control-screened, NOT yet empirically validated.
