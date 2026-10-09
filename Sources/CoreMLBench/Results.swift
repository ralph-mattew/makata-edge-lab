import Foundation
import Instrumentation

// Result schema. Moved unchanged from unawain-public-models/benchmarks/swift (BenchCore).
// Encoded with snake_case keys so the JSON lines up with bench_coreml_latency.py;
// fields that only the Swift harness records are additions, not renames.

public struct BenchConfig: Codable, Sendable {
    public var artifacts: [String]
    public var computeUnits: [String]
    public var warmup: Int
    public var iters: Int
    public var activeLen: Int
    public var seed: UInt64
    public var release: String

    public init(artifacts: [String], computeUnits: [String] = ComputeUnits.all,
                warmup: Int = 10, iters: Int = 100, activeLen: Int = 64, seed: UInt64 = 0,
                release: String = "v0.1.0") {
        self.artifacts = artifacts
        self.computeUnits = computeUnits
        self.warmup = warmup
        self.iters = iters
        self.activeLen = activeLen
        self.seed = seed
        self.release = release
    }
}

public struct Method: Codable, Sendable {
    public var harness = "swift (MLModel.prediction)"
    public var warmup: Int
    public var iters: Int
    public var activeLen: Int
    public var seed: UInt64
    public var inputs = "synthetic, from declared input spec"
    public var load = "load_s/first_call_ms on a fresh instance; reload_s + warmup + timed iters on a second instance; compile_s is .mlpackage -> .mlmodelc, measured once per model"
    public var memory = "phys_footprint of the benchmark process; after_load is taken after warmup with one instance resident"
}

public struct IOFeature: Codable, Sendable {
    public var name: String
    public var shape: [Int]
    public var dtype: String
}

public struct IODescription: Codable, Sendable {
    public var inputs: [IOFeature]
    public var outputs: [IOFeature]
}

/// Op placement from `MLComputePlan` with `computeUnits = .all`.
public struct ComputePlanSummary: Codable, Sendable {
    public var computeUnits = "ALL"
    /// Operations with a device-usage entry (constants and other non-dispatched ops have none).
    public var operations = 0
    public var operationsWithoutUsage = 0
    public var preferredCpu = 0
    public var preferredGpu = 0
    public var preferredNeuralEngine = 0
    public var supportedNeuralEngine = 0
    public var supportedGpu = 0
    public var note: String?
}

public struct RunResult: Codable, Sendable {
    public var computeUnits: String
    public var failed: Bool?
    public var error: String?
    public var loadS: Double?
    public var firstCallMs: Double?
    public var reloadS: Double?
    public var p50Ms: Double?
    public var p95Ms: Double?
    public var meanMs: Double?
    public var stdevMs: Double?
    public var minMs: Double?
    public var maxMs: Double?
    public var iters: Int?
    public var warmup: Int?
    public var footprintBeforeLoadMb: Double?
    public var footprintAfterLoadMb: Double?
    public var footprintAfterRunMb: Double?
    public var thermalBefore: String?
    public var thermalAfter: String?

    static func failure(_ cu: String, _ message: String, thermalBefore: String? = nil) -> RunResult {
        var r = RunResult(computeUnits: cu)
        r.failed = true
        r.error = message
        r.thermalBefore = thermalBefore
        return r
    }
}

public struct ModelEntry: Codable, Sendable {
    public var artifact: String
    public var packageSizeMb: Double?
    public var packageSha256: String?
    public var compileS: Double?
    public var io: IODescription?
    public var computePlan: ComputePlanSummary?
    public var setupError: String?
    public var runs: [RunResult] = []
}

public struct BenchRun: Codable, Sendable {
    public var hostBefore: DeviceConditions
    public var release: String
    public var method: Method
    public var models: [ModelEntry]
    public var hostAfter: DeviceConditions?
}

/// Persisted between launches so a crash (e.g. an MPSGraph abort) is recorded as a
/// failed setting and the run continues on the next launch.
public struct BenchState: Codable, Sendable {
    public struct Job: Codable, Sendable, Equatable {
        public var model: Int
        public var computeUnits: String
    }

    public var config: BenchConfig
    public var result: BenchRun
    public var nextJob = 0
    public var inProgress: Job?
    /// Set by the macOS parent process when a child dies, so the crash line is kept.
    public var crashNote: String?
    public var resumeCount = 0

    public var jobs: [Job] {
        config.artifacts.indices.flatMap { m in config.computeUnits.map { Job(model: m, computeUnits: $0) } }
    }
    public var isDone: Bool { nextJob >= jobs.count && result.hostAfter != nil }
}
