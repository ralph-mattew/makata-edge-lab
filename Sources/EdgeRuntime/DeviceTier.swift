import Foundation

/// Memory class of the device, from `ProcessInfo.physicalMemory`.
///
/// The thresholds sit below the marketed sizes because iOS reports less than the nominal
/// amount (a 6 GB iPhone reports about 5.96 GB). Same thresholds as the Xylo and Unawain apps.
public enum DeviceTier: String, Codable, Sendable, CaseIterable, Comparable {
    /// 6 GB and below.
    case low
    /// 8 GB.
    case mid
    /// 12 GB and above.
    case high

    public static let midThresholdBytes: UInt64 = 7_500_000_000
    public static let highThresholdBytes: UInt64 = 11_500_000_000

    public init(physicalMemory: UInt64) {
        if physicalMemory >= Self.highThresholdBytes {
            self = .high
        } else if physicalMemory >= Self.midThresholdBytes {
            self = .mid
        } else {
            self = .low
        }
    }

    public static var current: DeviceTier { DeviceTier(physicalMemory: ProcessInfo.processInfo.physicalMemory) }

    public static func < (a: DeviceTier, b: DeviceTier) -> Bool { a.rank < b.rank }

    private var rank: Int {
        switch self {
        case .low: return 0
        case .mid: return 1
        case .high: return 2
        }
    }
}
