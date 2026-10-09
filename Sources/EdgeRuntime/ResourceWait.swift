import Foundation
import Instrumentation

/// Waits, with a timeout, for memory headroom and thermal state to recover between
/// heavy stages (e.g. after unloading an LLM and before loading a translation model).
/// Nudges the allocator to return free pages on every poll.
///
/// Presets are the Unawain app's (commit b0124e6).
public enum ResourceWait {
    public struct Target: Sendable, Equatable {
        public var availableBytes: UInt64?
        public var thermalAtMost: ThermalState?
        public var timeout: Duration
        public var pollInterval: Duration

        public init(availableBytes: UInt64? = nil, thermalAtMost: ThermalState? = nil,
                    timeout: Duration, pollInterval: Duration = .milliseconds(250)) {
            self.availableBytes = availableBytes
            self.thermalAtMost = thermalAtMost
            self.timeout = timeout
            self.pollInterval = pollInterval
        }

        /// After an LLM unload: 800 MB headroom, up to 3 s, polling every 200 ms.
        public static let memoryReclaim = Target(availableBytes: 800_000_000, timeout: .seconds(3),
                                                 pollInterval: .milliseconds(200))

        /// Between generation and translation: `fair` or cooler and 600 MB headroom.
        /// 5 s on the low tier (where it always runs), 3 s on higher tiers (only when throttled).
        public static func thermalCooldown(tier: DeviceTier) -> Target {
            Target(availableBytes: 600_000_000, thermalAtMost: .fair,
                   timeout: tier == .low ? .seconds(5) : .seconds(3), pollInterval: .milliseconds(250))
        }
    }

    public struct Outcome: Sendable, Equatable {
        public var met: Bool
        public var polls: Int
        public var waited: Duration
        public var availableBytes: UInt64?
        public var thermal: ThermalState
    }

    public typealias Probe = @Sendable () -> (availableBytes: UInt64?, thermal: ThermalState)

    public static let liveProbe: Probe = {
        Memory.relievePressure()
        return (Memory.availableBytes(), .current)
    }

    /// Where headroom can't be read (`nil`, e.g. on macOS) the memory condition is
    /// treated as met, so the wait falls back to thermal state alone.
    public static func until(_ target: Target, probe: Probe = liveProbe) async -> Outcome {
        let clock = ContinuousClock()
        let start = clock.now
        var polls = 0
        while true {
            let (available, thermal) = probe()
            polls += 1
            let memoryOK = target.availableBytes.map { want in available.map { $0 >= want } ?? true } ?? true
            let thermalOK = target.thermalAtMost.map { thermal.severity <= $0.severity } ?? true
            let waited = clock.now - start
            if memoryOK && thermalOK {
                return Outcome(met: true, polls: polls, waited: waited, availableBytes: available, thermal: thermal)
            }
            if waited >= target.timeout {
                return Outcome(met: false, polls: polls, waited: waited, availableBytes: available, thermal: thermal)
            }
            try? await Task.sleep(for: target.pollInterval)
        }
    }
}
