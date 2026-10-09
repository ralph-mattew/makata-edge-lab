import Foundation
import Instrumentation

/// Decides how long to pause between on-device LLM runs so repeated use doesn't drive
/// the phone into thermal throttling. Pure: the caller owns the counter and any timer.
///
/// Values and logic are the Xylo app's (commit 9e103e8), kept as shipped:
/// - Each tier has a consecutive-run limit. Reaching it resets the counter and pauses
///   for the tier's longer cooldown, scaled by thermal state.
/// - Otherwise the shorter base cooldown applies once the device is warm: `fair` or
///   above on mid and high tiers, `serious` or above on the low tier.
/// - Scaling: nominal x0, fair x1, serious x1.5, critical x2.
/// - High-tier devices skip cooldowns of 5 seconds or less.
///
/// Because nominal scales to zero, reaching the consecutive limit on a cool device
/// resets the counter without a pause. That is the shipped behavior, pinned by a test;
/// whether it is the intended one is an open question for the app.
public struct CooldownPolicy: Sendable {
    public struct TierSettings: Sendable, Equatable {
        public var consecutiveLimit: Int
        public var baseSeconds: Int
        public var consecutiveSeconds: Int

        public init(consecutiveLimit: Int, baseSeconds: Int, consecutiveSeconds: Int) {
            self.consecutiveLimit = consecutiveLimit
            self.baseSeconds = baseSeconds
            self.consecutiveSeconds = consecutiveSeconds
        }
    }

    public struct Decision: Sendable, Equatable {
        public var cooldownSeconds: Int
        /// The counter value to keep for the next run.
        public var consecutiveRuns: Int
    }

    public var low = TierSettings(consecutiveLimit: 5, baseSeconds: 10, consecutiveSeconds: 15)
    public var mid = TierSettings(consecutiveLimit: 3, baseSeconds: 20, consecutiveSeconds: 35)
    public var high = TierSettings(consecutiveLimit: 4, baseSeconds: 10, consecutiveSeconds: 25)
    public var highTierSkipAtOrBelowSeconds = 5

    public init() {}

    public func settings(for tier: DeviceTier) -> TierSettings {
        switch tier {
        case .low: return low
        case .mid: return mid
        case .high: return high
        }
    }

    /// Call when a run finishes.
    /// - Parameter consecutiveRuns: the counter before this run was counted.
    public func afterRun(consecutiveRuns: Int, tier: DeviceTier, thermal: ThermalState) -> Decision {
        let s = settings(for: tier)
        var runs = consecutiveRuns + 1
        var seconds: Int
        if runs >= s.consecutiveLimit {
            seconds = Self.scaled(s.consecutiveSeconds, thermal)
            runs = 0
        } else if thermal.severity >= (tier == .low ? ThermalState.serious.severity : ThermalState.fair.severity) {
            seconds = Self.scaled(s.baseSeconds, thermal)
        } else {
            seconds = 0
        }
        if tier == .high, seconds <= highTierSkipAtOrBelowSeconds { seconds = 0 }
        return Decision(cooldownSeconds: seconds, consecutiveRuns: runs)
    }

    public static func scaled(_ base: Int, _ thermal: ThermalState) -> Int {
        switch thermal {
        case .nominal: return 0
        case .fair, .unknown: return base
        case .serious: return Int(Double(base) * 1.5)
        case .critical: return base * 2
        }
    }
}
