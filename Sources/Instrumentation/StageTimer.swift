import Foundation
import os

/// Records how long named pipeline stages take, and emits a signpost interval for each so
/// the same stages show up in Instruments on a device.
///
/// ```swift
/// let timer = StageTimer()
/// let chunks = timer.measure("chunk") { chunker.chunk(text) }
/// let vectors = try await timer.measure("embed", memory: true) { try await embedder.embed(chunks) }
/// print(timer.stages)
/// ```
public final class StageTimer: @unchecked Sendable {
    public struct Stage: Codable, Sendable, Equatable {
        public var name: String
        public var ms: Double
        public var footprintBeforeMb: Double?
        public var footprintAfterMb: Double?
    }

    private let signposter: OSSignposter
    private let lock = NSLock()
    private var recorded: [Stage] = []

    public init(subsystem: String = "ai.makata.edge-lab", category: String = "stages") {
        signposter = OSSignposter(subsystem: subsystem, category: category)
    }

    public var stages: [Stage] {
        lock.lock()
        defer { lock.unlock() }
        return recorded
    }

    public func reset() {
        lock.lock()
        recorded.removeAll()
        lock.unlock()
    }

    /// - Parameter memory: also record the process footprint before and after the stage.
    public func measure<T>(_ name: StaticString, memory: Bool = false, _ body: () throws -> T) rethrows -> T {
        let before = memory ? Memory.footprintMB() : nil
        let state = signposter.beginInterval(name)
        let t0 = ContinuousClock.now
        defer {
            let elapsed = ContinuousClock.now - t0
            signposter.endInterval(name, state)
            append(name, elapsed, before, memory ? Memory.footprintMB() : nil)
        }
        return try body()
    }

    public func measure<T>(_ name: StaticString, memory: Bool = false, _ body: () async throws -> T) async rethrows -> T {
        let before = memory ? Memory.footprintMB() : nil
        let state = signposter.beginInterval(name)
        let t0 = ContinuousClock.now
        defer {
            let elapsed = ContinuousClock.now - t0
            signposter.endInterval(name, state)
            append(name, elapsed, before, memory ? Memory.footprintMB() : nil)
        }
        return try await body()
    }

    private func append(_ name: StaticString, _ elapsed: Duration, _ before: Double?, _ after: Double?) {
        let c = elapsed.components
        let ms = Double(c.seconds) * 1e3 + Double(c.attoseconds) / 1e15
        lock.lock()
        recorded.append(Stage(name: "\(name)", ms: ms, footprintBeforeMb: before, footprintAfterMb: after))
        lock.unlock()
    }
}
