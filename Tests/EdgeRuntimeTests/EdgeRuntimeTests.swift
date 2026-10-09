import XCTest
@testable import EdgeRuntime

final class DeviceTierTests: XCTestCase {
    func testThresholds() {
        XCTAssertEqual(DeviceTier(physicalMemory: 5_960_000_000), .low)   // 6 GB iPhone as reported
        XCTAssertEqual(DeviceTier(physicalMemory: 7_499_999_999), .low)
        XCTAssertEqual(DeviceTier(physicalMemory: 7_500_000_000), .mid)
        XCTAssertEqual(DeviceTier(physicalMemory: 11_499_999_999), .mid)
        XCTAssertEqual(DeviceTier(physicalMemory: 11_500_000_000), .high)
        XCTAssert(DeviceTier.low < .mid && DeviceTier.mid < .high)
    }
}

final class LLMContextPolicyTests: XCTestCase {
    let policy = LLMContextPolicy()
    let gb: UInt64 = 1_000_000_000

    private func plan(_ tier: DeviceTier, _ available: UInt64?, _ thermal: ThermalState) -> LLMContextPlan {
        policy.plan(for: LLMRunConditions(tier: tier, availableBytes: available, thermal: thermal))
    }

    func testShippedTable() {
        // (tier, available, thermal) -> (context, gpu layers, budget for a 448-token request)
        let cases: [(DeviceTier, UInt64?, ThermalState, Int, Int, Int)] = [
            (.high, 4 * gb, .serious, 4096, 48, 448),
            (.mid, 4 * gb, .critical, 2048, 48, 352),
            (.low, 4 * gb, .serious, 2048, 48, 350),
            (.high, 3 * gb, .nominal, 4096, 99, 512),
            (.high, 2 * gb, .fair, 2500, 48, 448),
            (.high, nil, .nominal, 2500, 48, 448),
            (.mid, 4 * gb, .fair, 2500, 48, 448),
            (.low, 4 * gb, .nominal, 2048, 48, 350),
        ]
        for (tier, avail, thermal, ctx, gpu, budget) in cases {
            let p = plan(tier, avail, thermal)
            let label = "\(tier) \(String(describing: avail)) \(thermal)"
            XCTAssertEqual(p.contextSize, ctx, label)
            XCTAssertEqual(p.gpuLayers, gpu, label)
            XCTAssertEqual(p.generationBudget.resolve(requested: 448), budget, label)
            XCTAssertEqual(p.threads, 2, label)
            XCTAssertFalse(p.flashAttention, label)
        }
    }

    func testEngineSettings() {
        let low = plan(.low, 4 * gb, .nominal)
        XCTAssertEqual(low.batchSize, 2048)
        XCTAssertEqual(low.microBatchSize, 128)
        XCTAssertEqual(low.generationReserve, 512)
        XCTAssertFalse(low.compactPrompt)

        let lowHot = plan(.low, 4 * gb, .serious)
        XCTAssertTrue(lowHot.compactPrompt)

        let highHot = plan(.high, 4 * gb, .serious)
        XCTAssertFalse(highHot.compactPrompt)  // 4,096 context keeps the full prompt
        XCTAssertEqual(highHot.microBatchSize, 256)
        XCTAssertEqual(highHot.generationReserve, 1024)

        let fb = highHot.fallback
        XCTAssertEqual(fb.contextSize, 2048)
        XCTAssertEqual(fb.batchSize, 512)
        XCTAssertEqual(fb.generationReserve, 512)
        XCTAssertEqual(fb.microBatchSize, 256)
    }

    func testMemoryGates() {
        XCTAssertFalse(policy.canLoad(availableBytes: 2_500_000_000))
        XCTAssertTrue(policy.canLoad(availableBytes: 2_500_000_001))
        XCTAssertTrue(policy.canLoad(availableBytes: nil))
        XCTAssertTrue(policy.mustStop(availableBytes: 399_999_999))
        XCTAssertFalse(policy.mustStop(availableBytes: 400_000_000))
        XCTAssertFalse(policy.mustStop(availableBytes: nil))
    }

    func testInputCharacterBudget() {
        // 2,048 ctx, 512 reserve, 900 overhead chars = 600 tokens -> 936 tokens * 1.5 = 1,404 chars.
        XCTAssertEqual(LLMContextPolicy.inputCharacterBudget(contextSize: 2048, overheadChars: 900), 1404)
        // Overhead larger than the context falls back to the floor.
        XCTAssertEqual(LLMContextPolicy.inputCharacterBudget(contextSize: 2048, overheadChars: 5000), 800)
        XCTAssertEqual(LLMContextPolicy.minimumInputCharacters(forContext: 2500), 1100)
        XCTAssertEqual(LLMContextPolicy.minimumInputCharacters(forContext: 2800), 1400)
        XCTAssertEqual(LLMContextPolicy.minimumInputCharacters(forContext: 4096), 2000)
        XCTAssertEqual(LLMContextPolicy.minimumInputCharacters(forContext: 8192), 6000)
    }
}

final class CooldownPolicyTests: XCTestCase {
    let policy = CooldownPolicy()

    func testBaseCooldownOnlyWhenWarm() {
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 0, tier: .mid, thermal: .nominal).cooldownSeconds, 0)
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 0, tier: .mid, thermal: .fair).cooldownSeconds, 20)
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 0, tier: .mid, thermal: .serious).cooldownSeconds, 30)
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 0, tier: .mid, thermal: .critical).cooldownSeconds, 40)
        // The low tier waits for `serious` before pausing.
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 0, tier: .low, thermal: .fair).cooldownSeconds, 0)
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 0, tier: .low, thermal: .serious).cooldownSeconds, 15)
    }

    func testConsecutiveLimitResetsCounter() {
        let d = policy.afterRun(consecutiveRuns: 2, tier: .mid, thermal: .fair)
        XCTAssertEqual(d, .init(cooldownSeconds: 35, consecutiveRuns: 0))
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 1, tier: .mid, thermal: .fair).consecutiveRuns, 2)
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 4, tier: .low, thermal: .critical),
                       .init(cooldownSeconds: 30, consecutiveRuns: 0))
    }

    /// Shipped behavior: on a cool device the consecutive limit resets the counter but
    /// scales the pause to zero.
    func testConsecutiveLimitAtNominalHasNoPause() {
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 2, tier: .mid, thermal: .nominal),
                       .init(cooldownSeconds: 0, consecutiveRuns: 0))
    }

    func testHighTierSkipsShortPauses() {
        XCTAssertEqual(policy.afterRun(consecutiveRuns: 0, tier: .high, thermal: .fair).cooldownSeconds, 10)
        var p = policy
        p.high.baseSeconds = 5
        XCTAssertEqual(p.afterRun(consecutiveRuns: 0, tier: .high, thermal: .fair).cooldownSeconds, 0)
        p.low.baseSeconds = 5
        XCTAssertEqual(p.afterRun(consecutiveRuns: 0, tier: .low, thermal: .serious).cooldownSeconds, 7)
    }
}

final class ResourceWaitTests: XCTestCase {
    final class Sequence: @unchecked Sendable {
        var values: [(UInt64?, ThermalState)]
        init(_ v: [(UInt64?, ThermalState)]) { values = v }
        func next() -> (availableBytes: UInt64?, thermal: ThermalState) {
            values.count > 1 ? values.removeFirst() : values[0]
        }
    }

    func testReturnsOnceBothConditionsHold() async {
        let s = Sequence([(500_000_000, .serious), (700_000_000, .serious), (700_000_000, .fair)])
        let target = ResourceWait.Target(availableBytes: 600_000_000, thermalAtMost: .fair,
                                         timeout: .seconds(2), pollInterval: .milliseconds(5))
        let r = await ResourceWait.until(target, probe: { s.next() })
        XCTAssertTrue(r.met)
        XCTAssertEqual(r.polls, 3)
        XCTAssertEqual(r.thermal, .fair)
    }

    func testTimesOut() async {
        let target = ResourceWait.Target(availableBytes: 600_000_000, timeout: .milliseconds(40), pollInterval: .milliseconds(10))
        let r = await ResourceWait.until(target, probe: { (100, .nominal) })
        XCTAssertFalse(r.met)
        XCTAssertGreaterThan(r.polls, 1)
        XCTAssertGreaterThanOrEqual(r.waited, .milliseconds(40))
    }

    func testUnknownHeadroomCountsAsMet() async {
        let r = await ResourceWait.until(.memoryReclaim, probe: { (nil, .nominal) })
        XCTAssertTrue(r.met)
        XCTAssertEqual(r.polls, 1)
    }

    func testPresets() {
        XCTAssertEqual(ResourceWait.Target.thermalCooldown(tier: .low).timeout, .seconds(5))
        XCTAssertEqual(ResourceWait.Target.thermalCooldown(tier: .mid).timeout, .seconds(3))
        XCTAssertEqual(ResourceWait.Target.memoryReclaim.availableBytes, 800_000_000)
    }
}
