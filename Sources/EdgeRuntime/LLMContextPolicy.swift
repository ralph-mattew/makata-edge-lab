import Foundation
import Instrumentation

/// What the context policy needs to know about the device at the moment a run starts.
public struct LLMRunConditions: Sendable, Equatable {
    public var tier: DeviceTier
    /// Headroom from `os_proc_available_memory()`. `nil` where it can't be read (macOS);
    /// the policy then treats the headroom-gated options as unavailable.
    public var availableBytes: UInt64?
    public var thermal: ThermalState

    public init(tier: DeviceTier, availableBytes: UInt64?, thermal: ThermalState) {
        self.tier = tier
        self.availableBytes = availableBytes
        self.thermal = thermal
    }

    public static func current() -> LLMRunConditions {
        LLMRunConditions(tier: .current, availableBytes: Memory.availableBytes(), thermal: .current)
    }
}

/// How many tokens a run may generate, relative to what the caller asked for.
public enum GenerationBudget: Sendable, Equatable {
    /// Use the caller's limit.
    case requested
    /// Use the caller's limit, but no more than this.
    case cappedAt(Int)
    /// Use this limit regardless of the request.
    case fixed(Int)

    public func resolve(requested: Int) -> Int {
        switch self {
        case .requested: return requested
        case .cappedAt(let cap): return min(requested, cap)
        case .fixed(let n): return n
        }
    }
}

/// llama.cpp settings for one generation run.
public struct LLMContextPlan: Sendable, Equatable {
    public var contextSize: Int
    public var gpuLayers: Int
    public var threads: Int
    public var generationBudget: GenerationBudget
    /// `n_batch`.
    public var batchSize: Int
    /// `n_ubatch`.
    public var microBatchSize: Int
    public var flashAttention: Bool
    /// The caller should use its shorter prompt (throttled and at most 2,048 context).
    public var compactPrompt: Bool
    /// Tokens held back from the prompt for the answer.
    public var generationReserve: Int

    /// Settings to retry with if context creation fails: half the context, batch 512.
    public var fallback: LLMContextPlan {
        var p = self
        p.contextSize = contextSize / 2
        p.batchSize = 512
        p.generationReserve = LLMContextPolicy.generationReserve(forContext: p.contextSize)
        return p
    }
}

/// Picks context size, GPU offload, threads and generation budget from device tier,
/// memory headroom and thermal state.
///
/// Defaults are the values the Unawain app ships (commit b0124e6) for Gemma on-device
/// summarization, with engine settings from the Xylo app (commit 9e103e8). Both are
/// tuned for Gemma E2B/E4B Q4_K_M under llama.cpp on 6, 8 and 12 GB iPhones.
///
/// | Thermal    | Tier                     | Context | GPU layers | Budget       |
/// |------------|--------------------------|---------|------------|--------------|
/// | throttled  | high                     | 4,096   | 48         | requested    |
/// | throttled  | mid                      | 2,048   | 48         | cap 352      |
/// | throttled  | low                      | 2,048   | 48         | cap 350      |
/// | normal     | high, >= 3 GB available  | 4,096   | 99         | fixed 512    |
/// | normal     | high (less headroom), mid| 2,500   | 48         | requested    |
/// | normal     | low                      | 2,048   | 48         | cap 350      |
///
/// Threads are 2 everywhere: with the model on the GPU, more CPU threads add heat
/// without measurable throughput (Unawain's observation, not re-measured here).
public struct LLMContextPolicy: Sendable {
    /// Headroom a high-tier device needs for the full-offload 4,096 plan.
    public var highTierFullOffloadMinAvailable: UInt64 = 3_000_000_000
    /// Minimum headroom before loading a model at all.
    public var minAvailableToLoad: UInt64 = 2_500_000_000
    /// Headroom at which a running generation should stop.
    public var criticalAvailable: UInt64 = 400_000_000
    public var threads = 2

    public init() {}

    public func plan(for c: LLMRunConditions) -> LLMContextPlan {
        let throttled = c.thermal.isThrottled
        let headroom = c.availableBytes ?? 0
        let context: Int, gpu: Int, budget: GenerationBudget

        switch (throttled, c.tier) {
        case (true, .high):
            (context, gpu, budget) = (4096, 48, .requested)
        case (true, .mid):
            (context, gpu, budget) = (2048, 48, .cappedAt(352))
        case (true, .low), (false, .low):
            (context, gpu, budget) = (2048, 48, .cappedAt(350))
        case (false, .high) where headroom >= highTierFullOffloadMinAvailable:
            (context, gpu, budget) = (4096, 99, .fixed(512))
        case (false, .high), (false, .mid):
            (context, gpu, budget) = (2500, 48, .requested)
        }

        return LLMContextPlan(
            contextSize: context, gpuLayers: gpu, threads: threads, generationBudget: budget,
            batchSize: min(2048, context), microBatchSize: c.tier >= .mid ? 256 : 128,
            flashAttention: false, compactPrompt: throttled && context <= 2048,
            generationReserve: Self.generationReserve(forContext: context))
    }

    public func canLoad(availableBytes: UInt64?) -> Bool {
        guard let a = availableBytes else { return true }
        return a > minAvailableToLoad
    }

    public func mustStop(availableBytes: UInt64?) -> Bool {
        guard let a = availableBytes else { return false }
        return a < criticalAvailable
    }

    /// 1,024 tokens at 4,096 context and above, otherwise 512.
    public static func generationReserve(forContext n: Int) -> Int { n >= 4096 ? 1024 : 512 }

    /// Floor on input characters, so a large prompt overhead never squeezes the document to nothing.
    public static func minimumInputCharacters(forContext n: Int) -> Int {
        switch n {
        case 8192...: return 6000
        case 4096...: return 2000
        case 2800...: return 1400
        case 2300...: return 1100
        default: return 800
        }
    }

    /// Characters of document text that fit next to a prompt with `overheadChars` of
    /// instructions. `charsPerToken` 1.5 is Unawain's estimate for Filipino and mixed
    /// Filipino/English under Gemma's tokenizer; English is closer to 4.
    public static func inputCharacterBudget(contextSize: Int, overheadChars: Int, charsPerToken: Double = 1.5) -> Int {
        let overheadTokens = Int(Double(overheadChars) / charsPerToken)
        let textTokens = contextSize - generationReserve(forContext: contextSize) - overheadTokens
        return max(Int(Double(textTokens) * charsPerToken), minimumInputCharacters(forContext: contextSize))
    }
}
