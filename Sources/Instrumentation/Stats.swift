import Foundation

/// Summary statistics. Percentiles use linear interpolation, matching numpy's default,
/// so Swift and Python harness results are comparable.
public struct Stats: Sendable {
    public let sorted: [Double]

    public init(_ values: [Double]) { sorted = values.sorted() }

    public var count: Int { sorted.count }
    public var min: Double { sorted.first ?? .nan }
    public var max: Double { sorted.last ?? .nan }
    public var mean: Double { sorted.isEmpty ? .nan : sorted.reduce(0, +) / Double(sorted.count) }

    /// Sample standard deviation (n - 1); 0 for fewer than two values.
    public var stdev: Double {
        guard sorted.count > 1 else { return 0 }
        let m = mean
        return (sorted.reduce(0) { $0 + ($1 - m) * ($1 - m) } / Double(sorted.count - 1)).squareRoot()
    }

    /// - Parameter q: 0...100.
    public func percentile(_ q: Double) -> Double {
        guard !sorted.isEmpty else { return .nan }
        let pos = q / 100 * Double(sorted.count - 1)
        let lo = Int(pos.rounded(.down)), hi = Int(pos.rounded(.up))
        return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - Double(lo))
    }

    public var summary: Summary {
        Summary(n: count, p50: percentile(50), p95: percentile(95), mean: mean, stdev: stdev, min: min, max: max)
    }

    public struct Summary: Codable, Sendable, Equatable {
        public var n: Int
        public var p50: Double
        public var p95: Double
        public var mean: Double
        public var stdev: Double
        public var min: Double
        public var max: Double
    }
}

public func round2(_ x: Double) -> Double { (x * 100).rounded() / 100 }

/// Monotonic seconds since boot.
public func uptimeSeconds() -> Double { Double(DispatchTime.now().uptimeNanoseconds) / 1e9 }
