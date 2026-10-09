import Foundation
import XCTest
@testable import CoreMLBench
@testable import Instrumentation

final class CoreMLBenchTests: XCTestCase {
    /// A result written by the BenchCore harness in unawain-public-models (benchmark 002,
    /// Mac harness check) must decode and re-encode byte for byte.
    func testSchemaRoundTripsPublishedResult() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "002-harness-check-mac", withExtension: "json", subdirectory: "Fixtures"))
        let original = try Data(contentsOf: url)
        let run = try ResultJSON.decoder().decode(BenchRun.self, from: original)
        var encoded = try ResultJSON.encoder().encode(run)
        encoded.append(0x0A)
        XCTAssertEqual(String(decoding: encoded, as: UTF8.self), String(decoding: original, as: UTF8.self))
        XCTAssertFalse(run.models.isEmpty)
    }

    func testJobsAreModelMajor() {
        let config = BenchConfig(artifacts: ["a.mlpackage", "b.mlpackage"], computeUnits: ["ALL", "CPU_ONLY"])
        let run = BenchRun(hostBefore: DeviceConditions(timestampUtc: "", platform: "", os: "", osBuild: "", deviceModel: "",
                                                        chip: nil, memoryGb: 0, thermalState: "", lowPowerMode: false,
                                                        powerSource: "", batteryLevel: nil),
                           release: "v0.1.0", method: Method(warmup: 1, iters: 1, activeLen: 1, seed: 0),
                           models: [], hostAfter: nil)
        let state = BenchState(config: config, result: run)
        XCTAssertEqual(state.jobs.map { "\($0.model)/\($0.computeUnits)" }, ["0/ALL", "0/CPU_ONLY", "1/ALL", "1/CPU_ONLY"])
        XCTAssertFalse(state.isDone)
    }

    func testComputeUnitNames() {
        XCTAssertEqual(ComputeUnits.all.compactMap(ComputeUnits.parse).count, 4)
        XCTAssertNil(ComputeUnits.parse("NPU"))
    }
}
