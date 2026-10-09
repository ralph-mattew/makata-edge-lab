import CoreML
import Foundation
import Instrumentation

public enum ComputeUnits {
    public static let all = ["ALL", "CPU_ONLY", "CPU_AND_GPU", "CPU_AND_NE"]

    public static func parse(_ name: String) -> MLComputeUnits? {
        switch name {
        case "ALL": return .all
        case "CPU_ONLY": return .cpuOnly
        case "CPU_AND_GPU": return .cpuAndGPU
        case "CPU_AND_NE": return .cpuAndNeuralEngine
        default: return nil
        }
    }
}

public enum BenchError: Error, CustomStringConvertible {
    case missingArtifact(String)
    case unsupportedInput(String)

    public var description: String {
        switch self {
        case .missingArtifact(let name): return "artifact not found: \(name)"
        case .unsupportedInput(let name): return "input \(name) is not a multi-array"
        }
    }
}

/// Runs a benchmark as a list of (model, compute-units) jobs, saving state before and
/// after each one. If the process dies mid-job, the next `resume()` records that job as
/// failed and continues, which is how a Core ML crash is captured on iOS (no child processes).
public final class BenchRunner: @unchecked Sendable {
    public let stateURL: URL
    let compiledDir: URL
    let models: [String: URL]
    let log: @Sendable (String) -> Void

    /// - Parameters:
    ///   - modelURLs: `.mlpackage` locations, matched to `config.artifacts` by file name.
    ///   - compiledDir: cache for compiled `.mlmodelc` bundles (cleared on a fresh start).
    public init(stateURL: URL, compiledDir: URL, modelURLs: [URL], log: @escaping @Sendable (String) -> Void) {
        self.stateURL = stateURL
        self.compiledDir = compiledDir
        self.models = Dictionary(modelURLs.map { ($0.lastPathComponent, $0) }, uniquingKeysWith: { a, _ in a })
        self.log = log
    }

    // MARK: State

    public func loadState() -> BenchState? {
        guard let data = try? Data(contentsOf: stateURL) else { return nil }
        return try? ResultJSON.decoder().decode(BenchState.self, from: data)
    }

    public func save(_ state: BenchState) throws {
        try FileManager.default.createDirectory(at: stateURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try ResultJSON.encoder().encode(state).write(to: stateURL, options: .atomic)
    }

    /// Discards any previous state and compiled cache, and records starting conditions.
    @discardableResult
    public func start(_ config: BenchConfig) async throws -> BenchState {
        try? FileManager.default.removeItem(at: compiledDir)
        let host = await DeviceConditions.capture()
        let method = Method(warmup: config.warmup, iters: config.iters, activeLen: config.activeLen, seed: config.seed)
        let run = BenchRun(hostBefore: host, release: config.release, method: method,
                           models: config.artifacts.map { ModelEntry(artifact: $0) }, hostAfter: nil)
        let state = BenchState(config: config, result: run)
        try save(state)
        return state
    }

    /// Runs remaining jobs (at most `maxJobs`, if given). ``BenchState/isDone`` is true on completion.
    public func resume(maxJobs: Int = .max) async throws -> BenchState {
        guard var state = loadState() else { throw CocoaError(.fileNoSuchFile) }

        if let job = state.inProgress {
            let note = state.crashNote ?? "process ended while this setting was running (crash, jetsam, or forced quit); check the device crash log"
            log("\(state.config.artifacts[job.model]) [\(job.computeUnits)] did not finish: \(note)")
            state.result.models[job.model].runs.append(.failure(job.computeUnits, note))
            state.inProgress = nil
            state.crashNote = nil
            state.nextJob += 1
            state.resumeCount += 1
            try save(state)
        }

        let jobs = state.jobs
        var ran = 0
        while state.nextJob < jobs.count, ran < maxJobs {
            ran += 1
            let job = jobs[state.nextJob]
            let name = state.config.artifacts[job.model]
            state.inProgress = job
            try save(state)

            if state.result.models[job.model].packageSha256 == nil, state.result.models[job.model].setupError == nil {
                log("\(name): hashing and compiling ...")
                state.result.models[job.model] = await setUp(name, entry: state.result.models[job.model])
                try save(state)
            }

            log("\(name) [\(job.computeUnits)] ...")
            var result: RunResult
            if let err = state.result.models[job.model].setupError {
                result = .failure(job.computeUnits, "setup failed: \(err)")
            } else {
                let (r, io) = await bench(name, job.computeUnits, state.config)
                result = r
                if state.result.models[job.model].io == nil { state.result.models[job.model].io = io }
            }
            if result.failed == true {
                log("  FAILED: \(result.error ?? "")")
            } else {
                log(String(format: "  load %.2fs  p50 %.2fms  p95 %.2fms  thermal %@",
                           result.loadS ?? 0, result.p50Ms ?? 0, result.p95Ms ?? 0, result.thermalAfter ?? "?"))
            }
            state.result.models[job.model].runs.append(result)
            state.inProgress = nil
            state.nextJob += 1
            try save(state)
        }
        if state.nextJob < jobs.count { return state }

        // Op placement last, so the timed loads above were not warmed by it.
        for m in state.result.models.indices where state.result.models[m].setupError == nil {
            if state.result.models[m].computePlan?.note == Self.planStarted {
                state.result.models[m].computePlan?.note = "compute plan did not finish (process ended)"
                try save(state)
            }
            guard state.result.models[m].computePlan == nil else { continue }
            log("\(state.config.artifacts[m]): reading compute plan ...")
            var marker = ComputePlanSummary()
            marker.note = Self.planStarted
            state.result.models[m].computePlan = marker
            try save(state)
            state.result.models[m].computePlan = await computePlan(compiledURL(state.config.artifacts[m]))
            try save(state)
        }

        if state.result.hostAfter == nil {
            state.result.hostAfter = await DeviceConditions.capture()
            try save(state)
        }
        return state
    }

    public func writeResult(_ state: BenchState, to url: URL) throws {
        try ResultJSON.write(state.result, to: url)
    }

    // MARK: Per-model setup

    func compiledURL(_ name: String) -> URL {
        compiledDir.appendingPathComponent((name as NSString).deletingPathExtension + ".mlmodelc")
    }

    func setUp(_ name: String, entry: ModelEntry) async -> ModelEntry {
        var entry = entry
        guard let src = models[name] else {
            entry.setupError = BenchError.missingArtifact(name).description
            return entry
        }
        do {
            entry.packageSizeMb = (Double(try PackageHash.sizeBytes(of: src)) / 1e5).rounded() / 10
            entry.packageSha256 = try PackageHash.sha256(of: src)

            let t0 = uptimeSeconds()
            let tmp = try await MLModel.compileModel(at: src)
            entry.compileS = round2(uptimeSeconds() - t0)
            let dest = compiledURL(name)
            try FileManager.default.createDirectory(at: compiledDir, withIntermediateDirectories: true)
            try? FileManager.default.removeItem(at: dest)
            try FileManager.default.moveItem(at: tmp, to: dest)
        } catch {
            entry.setupError = "\(error)"
        }
        return entry
    }

    static let planStarted = "started"

    func computePlan(_ compiled: URL) async -> ComputePlanSummary {
        var s = ComputePlanSummary()
        guard #available(macOS 14.4, iOS 17.4, *) else {
            s.note = "MLComputePlan needs macOS 14.4 / iOS 17.4"
            return s
        }
        do {
            let cfg = MLModelConfiguration()
            cfg.computeUnits = .all
            let plan = try await MLComputePlan.load(contentsOf: compiled, configuration: cfg)
            guard case .program(let program) = plan.modelStructure else {
                s.note = "not an ML program; op placement unavailable"
                return s
            }
            func visit(_ block: MLModelStructure.Program.Block) {
                for op in block.operations {
                    if let usage = plan.deviceUsage(for: op) {
                        s.operations += 1
                        switch usage.preferred {
                        case .cpu: s.preferredCpu += 1
                        case .gpu: s.preferredGpu += 1
                        case .neuralEngine: s.preferredNeuralEngine += 1
                        @unknown default: break
                        }
                        for device in usage.supported {
                            switch device {
                            case .neuralEngine: s.supportedNeuralEngine += 1
                            case .gpu: s.supportedGpu += 1
                            default: break
                            }
                        }
                    } else {
                        s.operationsWithoutUsage += 1
                    }
                    op.blocks.forEach(visit)
                }
            }
            program.functions.values.forEach { visit($0.block) }
        } catch {
            s.note = "compute plan failed: \(error)"
        }
        return s
    }

    // MARK: Timing

    func bench(_ name: String, _ cuName: String, _ config: BenchConfig) async -> (RunResult, IODescription?) {
        let thermalBefore = ThermalState.current.rawValue
        guard let cu = ComputeUnits.parse(cuName) else {
            return (.failure(cuName, "unknown compute units", thermalBefore: thermalBefore), nil)
        }
        let compiled = compiledURL(name)
        let cfg = MLModelConfiguration()
        cfg.computeUnits = cu

        do {
            var r = RunResult(computeUnits: cuName)
            r.thermalBefore = thermalBefore
            r.footprintBeforeLoadMb = Memory.footprintMB()

            // Fresh instance: cold load for this compute-units setting, then the first call.
            let (inputs, io) = try autoreleasepool { () throws -> (MLDictionaryFeatureProvider, IODescription) in
                var t0 = uptimeSeconds()
                let model = try MLModel(contentsOf: compiled, configuration: cfg)
                r.loadS = round2(uptimeSeconds() - t0)
                let inputs = try SyntheticInputs.make(model.modelDescription, seed: config.seed, activeLen: config.activeLen)
                t0 = uptimeSeconds()
                _ = try model.prediction(from: inputs)
                r.firstCallMs = round2((uptimeSeconds() - t0) * 1e3)
                return (inputs, describe(model.modelDescription))
            }

            // Second instance: warm (cached) load, then warmup and timed calls.
            var t0 = uptimeSeconds()
            let warm = try MLModel(contentsOf: compiled, configuration: cfg)
            r.reloadS = round2(uptimeSeconds() - t0)

            for _ in 0..<config.warmup {
                _ = try autoreleasepool { try warm.prediction(from: inputs) }
            }
            r.footprintAfterLoadMb = Memory.footprintMB()
            var times: [Double] = []
            times.reserveCapacity(config.iters)
            for _ in 0..<config.iters {
                t0 = uptimeSeconds()
                _ = try autoreleasepool { try warm.prediction(from: inputs) }
                times.append((uptimeSeconds() - t0) * 1e3)
            }

            let st = Stats(times)
            r.p50Ms = round2(st.percentile(50))
            r.p95Ms = round2(st.percentile(95))
            r.meanMs = round2(st.mean)
            r.stdevMs = round2(st.stdev)
            r.minMs = round2(st.min)
            r.maxMs = round2(st.max)
            r.iters = config.iters
            r.warmup = config.warmup
            r.footprintAfterRunMb = Memory.footprintMB()
            r.thermalAfter = ThermalState.current.rawValue
            return (r, io)
        } catch {
            return (.failure(cuName, "\(error)", thermalBefore: thermalBefore), nil)
        }
    }

    func describe(_ d: MLModelDescription) -> IODescription {
        func features(_ dict: [String: MLFeatureDescription]) -> [IOFeature] {
            dict.values.sorted { $0.name < $1.name }.map { f in
                let c = f.multiArrayConstraint
                return IOFeature(name: f.name, shape: c?.shape.map(\.intValue) ?? [],
                                 dtype: c.map { SyntheticInputs.dtypeName($0.dataType) } ?? "NON_ARRAY")
            }
        }
        return IODescription(inputs: features(d.inputDescriptionsByName), outputs: features(d.outputDescriptionsByName))
    }
}

/// Synthetic inputs from a model's declared input spec, with the same conventions as
/// `bench_coreml_latency.py`: masks cover the first `activeLen` positions, id/token inputs
/// draw from 4..<1000, position inputs are `activeLen - 1`, float inputs are N(0, 0.1).
public enum SyntheticInputs {
    public static func make(_ desc: MLModelDescription, seed: UInt64, activeLen: Int) throws -> MLDictionaryFeatureProvider {
        var rng = SplitMix64(seed: seed)
        var feeds: [String: MLFeatureValue] = [:]
        for (name, f) in desc.inputDescriptionsByName.sorted(by: { $0.key < $1.key }) {
            guard let c = f.multiArrayConstraint else { throw BenchError.unsupportedInput(name) }
            let arr = try MLMultiArray(shape: c.shape, dataType: c.dataType)
            let last = max(c.shape.last?.intValue ?? 1, 1)
            let lname = name.lowercased()
            let isInt = c.dataType == .int32
            for i in 0..<arr.count {
                let v: Double
                if lname.contains("mask") {
                    v = i % last < activeLen ? 1 : 0
                } else if lname.contains("ids") || lname.contains("token") {
                    v = Double(4 + rng.next() % 996)  // low ids exist in full and pruned vocabularies
                } else if lname.contains("pos") {
                    v = Double(activeLen - 1)
                } else if isInt {
                    v = 0
                } else {
                    v = rng.gaussian() * 0.1
                }
                arr[i] = NSNumber(value: v)
            }
            feeds[name] = MLFeatureValue(multiArray: arr)
        }
        return try MLDictionaryFeatureProvider(dictionary: feeds)
    }

    public static func dtypeName(_ t: MLMultiArrayDataType) -> String {
        switch t {
        case .int32: return "INT32"
        case .float32: return "FLOAT32"
        case .float16: return "FLOAT16"
        case .double: return "DOUBLE"
        default: return "OTHER(\(t.rawValue))"
        }
    }
}
