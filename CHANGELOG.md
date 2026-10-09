# Changelog

## Unreleased

- Public repository started from a snapshot of the earlier repository (after PoC 008 was written up);
  its history is not published, and commit hashes in earlier entries and PoC write-ups refer to it. The
  generic stand-ins in `generic/` are reworded so they share no five-word run with the private text, and
  PoC 006's README no longer quotes FoundationModels' lead-in line. Registered results, inputs hashes and
  verdicts are unchanged.
- PoC 008 host run, headline for FoundationModels *reject* (no gain): adding the rule "check whether the sections
  contain the answer, otherwise reply exactly ..." leaves its absent rate on unanswerable items at 39% (38.6%),
  while a reminder line after the question raises it to 57.5% (+18.3 points) at a cost of 7.2 points of key
  facts (reject, trade-off; that arm ran on battery). Gemma 4 E2B *adopt* (host stage): the rule raises its
  absent rate from 64.9% to 80.1% and balanced accuracy by 5.8 points (95% CI +3.7 to +8.0), with 3.6 fewer answers
  and 2.2 fewer key facts. Qwen2.5-1.5B *reject* (trade-off): +5.5 points balanced, key facts 5.5 points lower; with
  the reminder it answers 31% of answerable items. H1 and H2 did not hold, H3 held. Detector v2 agrees with an AI
  reader on 97.5% of 120 audited outputs. One Qwen output that recited the private prompt is redacted.
- PoC 008 registered (a plain "not in the sections" instruction for contract questions): does a fixed-reply
  instruction raise how often FoundationModels, Gemma 4 E2B and Qwen2.5-1.5B flag unanswerable contract
  questions as absent, without cutting answers on answerable ones? Reuses PoC 006's items, harness and
  scoring over three prompt variants, with a corrected answer-or-absent detector registered before the run.
  Not run yet.
- Private overlay for confidential source-app text: Xylo's prompts (PoC 003 to 006) and keyword tables
  (PoC 007) moved out of the tracked tree into a gitignored `private/` directory, read through
  `scripts/overlay.py` with generic stand-ins in `generic/`. Inputs that embed the prompt are no longer
  committed. Rebuilt inputs and keyword scores match the registered runs; dated Errata in PoCs 003 to 007.
- `Instrumentation`: `DeviceConditions`, `MemorySnapshot`, `ThermalState`, `StageTimer`,
  `Stats`, `SplitMix64`, `PackageHash`, `ResultJSON`. Moved from the BenchCore target in
  unawain-public-models; hashing now also accepts single files (e.g. `.gguf`).
- `EdgeRuntime`: `DeviceTier`, `LLMContextPolicy`, `CooldownPolicy`, `ResourceWait`, `DiskSpace`,
  with defaults from the Xylo (9e103e8) and Unawain (b0124e6) apps.
- `CoreMLBench`: the resumable Core ML runner from BenchCore. Result JSON unchanged; a test
  round-trips the published benchmark 002 Mac result byte for byte.
- `poc/`: index, template, and PoC 001 (KV cache quantization).
- PoC 001 host run, verdict *reject: not the constraint*. At the shipped settings, Gemma E2B's KV
  plus compute buffers grow 13 MiB from 2,048 to 4,096 context, and q8_0 saves 25 MiB at 4,096.
  Raw logs, `summarize.py`, and summary tables are committed.
- Opened to replications: `CONTRIBUTING.md`, `GOVERNANCE.md` (review, corrections, conflicts of
  interest), Contributor Covenant 2.1, `SECURITY.md`, `CITATION.cff`, issue and PR templates,
  and a replication template. PoC 001's `run.sh` and `summarize.py` accept a replication folder.
- Write-ups and results are now CC BY 4.0; code stays Apache-2.0. Contributions need a DCO
  sign-off.
- CI: `swift test`, the iOS build, repo checks (personal data, large files, weights, JSON, raw
  results present), and a DCO check on pull requests.
- Lab write-ups use the lab or the experiment as the subject, with a named byline on each PoC
  and replication.
- PoC 003 registered (Qwen2.5 sampler settings and clean stopping): protocol, arms, CUAD input
  preparation, and a Swift harness pinned to llama.swift 2.8901.0 (llama.cpp b8901). Not run yet.
- PoC 003 host run, verdict *reject: does not reproduce*. Xylo's old near-greedy settings
  already stop on their own 95% of the time (recipe 98%). The recipe's real effect is on format:
  four sections rise from 3% to 39%. Presence penalty does not carry it. Raw generations,
  `summarize.py` with a labeled exploratory section, and summary tables are committed.
- PoC 004 registered (what holds Qwen2.5 to two summary sections): repeat penalty 1.05 / 1.15 /
  1.3 under both of PoC 003's settings, and Xylo's prompt without the line that closes its worked example.
  Reuses PoC 003's harness, inputs and scoring unchanged. Not run yet.
- PoC 004 host run, verdict *reject: no gain*: removing the example's closing line does not add
  sections (36% against 39%). The repeat penalty carries PoC 003's format effect: four sections
  fall from 39% to 4% as it rises from 1.05 to 1.3, and Xylo's old settings with only it lowered
  reach 42%. The repeated arms are token-identical to PoC 003. The run was on battery, a recorded
  deviation that affects timings only.
- PoC 004 errata: the answer budget is ruled out as a cause of missing sections by PoC 004's own
  results (98% of outputs end before the cap). Verdict unchanged.
- PoC 005 registered (continuing a summary past an early end): at Xylo's shipped settings,
  insert the next section heading when the model tries to end early, or suppress the end token,
  against no intervention. Harness is PoC 003's plus a per-arm `intervention`; its `none` path
  matched PoC 003's tokens in a smoke test. Not run yet.
- PoC 005 host run, verdict *adopt* (host stage): inserting the missing section heading raises
  complete four-section summaries from 39% to 93% (+54 points, CI [+44, +64]); unsupported
  numbers 3% to 5%. Suppressing the end token reaches 76% but runs to the cap 22% of the time.
  `b-shipped` is token-identical to PoC 003. Raw generations, `summarize.py` with a labeled
  exploratory section, and summary tables are committed.
- PoC 006 registered (contract questions on FoundationModels, Gemma 4 E2B and Qwen2.5-1.5B):
  986 CUAD items, half with the answer in three fixed sections and half with no answer in the
  contract, through Xylo's chat prompt and each backend's shipped settings. Two harness programs,
  `GGUFQA` (llama.swift 2.8901.0) and `FMQA` (FoundationModels), a frozen absent detector with a
  blinded audit, and key-fact parsers calibrated on CUAD's spans. Not run yet.
- PoC 007 registered (retrieval recall of EmbeddingGemma and NLEmbedding): does Xylo's shipped
  EmbeddingGemma retrieval find the answer-bearing text more often than its NLEmbedding fallback, at
  Xylo's chunking, weights and re-ranking? 1,325 CUAD items from 397 contracts; harness is a chunker and
  a scorer (keyword, NLEmbedding, EmbeddingGemma) pinned to llama.swift 2.8901.0. Smoke-tested on five
  contracts. Not run yet.
- PoC 007 host run, verdict *adopt* (host stage): EmbeddingGemma retrieval raises recall@3 from 35% to
  61% over NLEmbedding at Xylo's weights (+26 points, 95% CI +24 to +29), in all 14 categories, at
  8.9 ms per chunk against NLEmbedding's 14.5. NLEmbedding's hybrid scores below the keyword score
  alone (35% against 47%). `index.py` failed inside `run.sh` and was run by hand (Deviations); `run.sh`
  now detaches stdin. Raw scores, `summarize.py` and summary tables are committed.
- PoC 006 host run, verdict *adopt* (host stage): Gemma 4 E2B has a balanced accuracy of 76.5% against
  62.1% for FoundationModels (+14.5 points, 95% CI +11.3 to +17.6), mainly by saying the answer is absent on
  65% of unanswerable items against 39%, with a higher key-fact rate and fewer unsupported numbers. The
  three hypotheses did not hold: FoundationModels fills the gap on 61% of unanswerable items, close to
  Qwen2.5-1.5B's 67%. The detector agrees with an AI reader on 96% of 120 audited outputs; it misses a
  leading-punctuation "No" (Limits). Run 2 timings are not reported because the Mac was on battery for
  part of it. `run.sh` detaches stdin. Raw generations, the audit sheet and labels, `summarize.py` and
  summary tables are committed.
