# Makata AI Edge Lab

Reusable parts and proof-of-concept experiments for running AI models on phones and laptops,
from the Makata AI Edge Lab. They come out of work on two on-device iOS apps, Xylo (document chat)
and Unawain (Filipino document summarization and translation). This repo holds the parts that aren't
specific to either app, plus experiments that test ideas from recent edge-AI papers and repos
against real device limits.

The question behind all of it: what does it take for a model that fits on a device to also
run well there, under memory limits, thermal throttling and uneven hardware?

## What's here

| Path | What it is |
|---|---|
| [`Sources/Instrumentation`](Sources/Instrumentation) | Measurement: device conditions, memory snapshots, stage timing with signposts, percentile stats, a seeded RNG, artifact hashing, result JSON conventions. No dependencies. |
| [`Sources/EdgeRuntime`](Sources/EdgeRuntime) | Runtime policy: device tiers, llama.cpp context planning, cooldowns between runs, waiting for memory and thermal recovery, disk checks. Pure functions where possible, so the policies can be tested and compared. |
| [`Sources/CoreMLBench`](Sources/CoreMLBench) | The resumable Core ML latency runner behind the [unawain-public-models](https://github.com/ralph-mattew/unawain-public-models) benchmarks. Its result JSON is unchanged. |
| [`poc/`](poc) | Experiments, numbered. Each has a pre-registered question, its own setup, raw results and a verdict. [Index](poc/README.md). |
| [`docs/architecture/`](docs/architecture) | How the components fit together and where their defaults come from. |

No model weights or datasets are committed. PoCs download what they need and say where from.

## Using the package

Swift 5.10 or later, iOS 17 / macOS 14.

```swift
.package(url: "https://github.com/ralph-mattew/makata-edge-lab", branch: "main")
```

```swift
import EdgeRuntime

let plan = LLMContextPolicy().plan(for: .current())
// plan.contextSize, plan.gpuLayers, plan.threads, plan.generationBudget.resolve(requested: 448)

let pause = CooldownPolicy().afterRun(consecutiveRuns: runs, tier: .current, thermal: .current)
runs = pause.consecutiveRuns
```

`swift test` runs the tests on a Mac. The iOS-only paths (`os_proc_available_memory`, `UIDevice`)
are checked by cross-compiling for iOS.

## How results are reported

Every claim in a PoC write-up carries one of four tags:

- **MEASURED**: a number from a run recorded in this repo, with the device and conditions.
- **OBSERVED**: seen during a run, not measured systematically.
- **INFERRED**: follows from measurements, not measured directly.
- **HYPOTHESIS**: not yet tested.

Results hold for the device, OS, model build and settings they were measured under. A PoC can
end as *adopt*, *reject* or *inconclusive*; rejected and inconclusive results are published too.

## Status

Early. `Instrumentation`, `EdgeRuntime` and `CoreMLBench` are in; the apps don't use this package
yet. Next are a llama.cpp engine wrapper, the document retrieval pipeline from Xylo, and model
download and verification. The app code these come from is private; the parts here are
extracted from it, with the source commit noted where defaults were taken from it.

## History

This repository starts from a snapshot of the lab's earlier repository, taken on 2026-10-09 after
PoC 008 was written up. The earlier history is not published, because it held text from a private
app. Commit hashes cited in PoC write-ups and in the changelog (for example, the commits where a PoC
was registered) refer to that earlier repository, not to this one. From the snapshot on, each PoC
is registered and written up through pull requests here.

## Contributing

The lab currently accepts **replications**: running an existing PoC on your own hardware and
submitting the raw results. Results from devices the lab doesn't own are the most useful
contribution right now. See [CONTRIBUTING.md](CONTRIBUTING.md), and use
[Discussions](https://github.com/ralph-mattew/makata-edge-lab/discussions) for questions and PoC
ideas. How results are accepted and corrected is in [GOVERNANCE.md](GOVERNANCE.md). Everyone taking
part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Citing

See [CITATION.cff](CITATION.cff), or use GitHub's "Cite this repository" button. Tagged releases
are archived on Zenodo with a DOI.

## License

- **Code** (`Sources/`, `Tests/`, `Package.swift`, and the scripts in `poc/`): Apache License 2.0.
  See [LICENSE](LICENSE) and [NOTICE](NOTICE).
- **Write-ups and result data** (Markdown documents and everything under `poc/*/results/` and
  `poc/*/replications/`): Creative Commons Attribution 4.0 International. See
  [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).

Models and datasets used by the PoCs are not included and have their own licenses, linked from
each PoC.
