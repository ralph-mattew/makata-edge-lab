# PoCs

Each PoC tests one idea, usually from a recent paper or open-source repo, against the limits the
lab's apps run into on real devices. The question, method and decision rule are written down
before the first run and not edited afterwards; changes go in a dated deviations section.

Start a new one by copying [`_template`](_template) to `NNN-short-slug`. Replications of a
PoC go in its `replications/` folder, using [`_template/REPLICATION.md`](_template/REPLICATION.md);
see [CONTRIBUTING.md](../CONTRIBUTING.md).

| # | PoC | Question | Status | Verdict | Replications |
|---|---|---|---|---|---|
| 001 | [KV cache quantization](001-kv-cache-quantization) | Can a q8_0 or q4_0 KV cache give 6 GB iPhones twice the context for Gemma E2B in the same memory? | Written up (host stage) | Reject: not the constraint. Shipped f16 settings grow 13 MiB from 2,048 to 4,096 context | [Open](001-kv-cache-quantization#replications), none yet |
| 003 | [Qwen2.5 sampler and clean stopping](003-qwen-sampler-stop-behavior) | Does Qwen's recommended sampler make Qwen2.5-1.5B finish Xylo's four-section summary on its own, and does presence penalty carry the effect? | Written up (host stage) | Reject: does not reproduce. Old settings already stop on their own 95% of the time; the recipe lifts four-section output from 3% to 39%, and presence penalty does not carry it | [Open](003-qwen-sampler-stop-behavior#replications), none yet |
| 004 | [What holds Qwen2.5 to two summary sections](004-qwen-summary-format) | Does the repeat penalty explain why Qwen2.5-1.5B writes two of four sections, and does removing the prompt's example-closing line raise complete summaries? | Written up (host stage) | Reject: no gain from removing the END line. Repeat penalty carries the format effect: 1.3 gives 3–4% four-section summaries, 1.05 about 40%, under either sampler | [Open](004-qwen-summary-format#replications), none yet |
| 005 | [Continuing a summary past an early end](005-summary-heading-continuation) | At Xylo's shipped settings, does inserting the next section heading when Qwen2.5-1.5B tries to end early raise complete four-section summaries, without unsupported numbers or empty sections? | Written up (host stage) | Adopt (host stage): inserting the missing heading lifts complete summaries from 39% to 93%; unsupported numbers 3% to 5% | [Open](005-summary-heading-continuation#replications), none yet |
| 006 | [Contract questions on FoundationModels, Gemma 4 E2B and Qwen2.5-1.5B](006-doc-qa-fm-gemma-qwen) | Given the same three contract sections and Xylo's chat prompt, how often does each chat backend answer when the answer is there, and say so when it is not? | Written up (host stage) | Adopt (host stage): Gemma 4 E2B beats FoundationModels on balanced accuracy by 14.5 points (95% CI +11.3 to +17.6), by saying absent on 65% of unanswerable items against 39% | [Open](006-doc-qa-fm-gemma-qwen#replications), none yet |
| 007 | [Retrieval recall of EmbeddingGemma and NLEmbedding](007-embedding-retrieval-recall) | On contracts too long to read whole, does Xylo's retrieval find the answer-bearing text more often with EmbeddingGemma than with NLEmbedding, at Xylo's chunking, weights and re-ranking? | Written up (host stage) | Adopt (host stage): EmbeddingGemma raises recall@3 from 35% to 61% over NLEmbedding (+26 points, 95% CI +24 to +29), at 8.9 ms per chunk | [Open](007-embedding-retrieval-recall#replications), none yet |
| 008 | [A plain "not in the sections" instruction](008-absence-instruction-doc-qa) | At Xylo's shipped settings, does adding an instruction to reply with a fixed sentence when the sections do not contain the answer raise how often FoundationModels, Gemma 4 E2B and Qwen2.5-1.5B flag an unanswerable contract question as absent, without cutting their answers on answerable ones? | Written up (host stage) | Headline, FoundationModels: reject, no gain (the rule alone does not move its absent rate; the reminder after the question adds 18.3 points but costs 7.2 points of key facts). Gemma 4 E2B: adopt (host stage), the rule lifts its absent rate from 64.9% to 80.1%. Qwen2.5-1.5B: reject, trade-off | [Open](008-absence-instruction-doc-qa#replications), none yet |

Status moves through *planned*, *host run*, *device run*, *written up*. Verdicts are *adopt*,
*reject* or *inconclusive*; adopted results then move into `Sources/` as a default, with the PoC
cited in the change.

PoC numbers are separate from the benchmark numbers in
[unawain-public-models](https://github.com/ralph-mattew/unawain-public-models).
