import Foundation

/// SplitMix64: small, seedable, and identical on every platform, so synthetic inputs
/// can be regenerated exactly from a seed recorded in a result file.
public struct SplitMix64: Sendable {
    public var state: UInt64

    public init(seed: UInt64) { state = seed }

    public mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }

    /// Uniform in [0, 1).
    public mutating func unit() -> Double { Double(next() >> 11) / Double(1 << 53) }

    /// Standard normal (Box-Muller).
    public mutating func gaussian() -> Double {
        (-2 * log(Swift.max(unit(), .leastNonzeroMagnitude))).squareRoot() * cos(2 * .pi * unit())
    }
}
