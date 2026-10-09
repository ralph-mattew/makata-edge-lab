import Foundation
import XCTest
@testable import Instrumentation

final class InstrumentationTests: XCTestCase {
    func testPercentilesMatchNumpyLinearInterpolation() {
        // numpy.percentile([5, 1, 4, 2, 3, 10], [50, 95]) == [3.5, 8.75]
        let s = Stats([5, 1, 4, 2, 3, 10])
        XCTAssertEqual(s.percentile(50), 3.5, accuracy: 1e-12)
        XCTAssertEqual(s.percentile(95), 8.75, accuracy: 1e-12)
        XCTAssertEqual(s.min, 1)
        XCTAssertEqual(s.max, 10)
        XCTAssertEqual(s.mean, 25.0 / 6, accuracy: 1e-12)
        XCTAssertTrue(Stats([]).percentile(50).isNaN)
        XCTAssertEqual(Stats([7]).stdev, 0)
    }

    func testSplitMix64MatchesReferenceSequence() {
        var a = SplitMix64(seed: 0)
        XCTAssertEqual([a.next(), a.next(), a.next()], [16294208416658607535, 7960286522194355700, 487617019471545679])
        var b = SplitMix64(seed: 42)
        XCTAssertEqual([b.next(), b.next(), b.next()], [13679457532755275413, 2949826092126892291, 5139283748462763858])
        var c = SplitMix64(seed: 7)
        for _ in 0..<1000 {
            let u = c.unit()
            XCTAssert(u >= 0 && u < 1)
        }
    }

    /// Expected digests come from `scripts/build_manifest.py` (sha256_path) run on the same tree.
    func testPackageHashMatchesPythonManifestScript() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("hashfix-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: root) }
        let pkg = root.appendingPathComponent("pkg.mlpackage")
        try FileManager.default.createDirectory(at: pkg.appendingPathComponent("a"), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: pkg.appendingPathComponent("a-b"), withIntermediateDirectories: true)
        try Data("one".utf8).write(to: pkg.appendingPathComponent("a/x.bin"))
        try Data("two".utf8).write(to: pkg.appendingPathComponent("a-b/y.bin"))
        try Data("three".utf8).write(to: pkg.appendingPathComponent("Manifest.json"))
        let file = root.appendingPathComponent("model.gguf")
        try Data("single".utf8).write(to: file)

        // "a/x.bin" sorts before "a-b/y.bin" component-wise, after it as a whole string.
        XCTAssertEqual(try PackageHash.sha256(of: pkg), "b5d04d3f92d97c2f5765d78ad4b30c8416ee178dc68f3f552d53e533b6d1ae61")
        XCTAssertEqual(try PackageHash.sha256(of: file), "947f187506f7629c81c81879a2cb2256455038e4ac770091d897fa0a8b945e3b")
        XCTAssertEqual(try PackageHash.sizeBytes(of: pkg), 11)
        XCTAssertEqual(try PackageHash.sizeBytes(of: file), 6)
    }

    func testResultJSONIsSnakeCaseSortedWithTrailingNewline() throws {
        struct Row: Codable, Equatable { var loadS: Double; var computeUnits: String }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("rj-\(UUID().uuidString)/r.json")
        defer { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }
        try ResultJSON.write(Row(loadS: 1.5, computeUnits: "ALL"), to: url)
        let text = try String(contentsOf: url, encoding: .utf8)
        XCTAssertEqual(text, "{\n  \"compute_units\" : \"ALL\",\n  \"load_s\" : 1.5\n}\n")
        XCTAssertEqual(try ResultJSON.decoder().decode(Row.self, from: Data(text.utf8)), Row(loadS: 1.5, computeUnits: "ALL"))
    }

    func testStageTimerRecordsStagesInOrder() async throws {
        let t = StageTimer()
        let x = t.measure("sync") { 21 * 2 }
        let y = try await t.measure("async", memory: true) { () async throws -> Int in
            try await Task.sleep(for: .milliseconds(20))
            return 7
        }
        XCTAssertEqual(x, 42)
        XCTAssertEqual(y, 7)
        XCTAssertEqual(t.stages.map(\.name), ["sync", "async"])
        XCTAssertGreaterThanOrEqual(t.stages[1].ms, 15)
        XCTAssertNotNil(t.stages[1].footprintAfterMb)
        XCTAssertNil(t.stages[0].footprintBeforeMb)
    }

    func testMemorySnapshotReadsProcessFootprint() {
        let m = MemorySnapshot.capture()
        XCTAssertEqual(m.physicalBytes, ProcessInfo.processInfo.physicalMemory)
        XCTAssertGreaterThan(m.footprintBytes ?? 0, 0)
        XCTAssertGreaterThan(m.residentBytes ?? 0, 0)
        #if os(macOS)
        XCTAssertNil(m.availableBytes)
        #endif
    }

    func testThermalSeverityOrdering() {
        XCTAssertEqual(ThermalState.allCases.map(\.severity), [0, 1, 2, 3, 1])
        XCTAssertFalse(ThermalState.fair.isThrottled)
        XCTAssertTrue(ThermalState.serious.isThrottled)
        XCTAssertTrue(ThermalState.critical.isThrottled)
    }
}
