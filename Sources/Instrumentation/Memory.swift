import Foundation
#if canImport(Darwin)
import Darwin
#endif

/// Process and device memory at one instant. Byte counts, decimal units when converted to MB.
public struct MemorySnapshot: Codable, Sendable, Equatable {
    /// `ProcessInfo.physicalMemory`. Reported below the marketed size (a 6 GB iPhone reports about 5,960 MB).
    public var physicalBytes: UInt64
    /// `phys_footprint`: the figure iOS compares against the jetsam limit.
    public var footprintBytes: UInt64?
    public var residentBytes: UInt64?
    /// `os_proc_available_memory()`: headroom before this process hits its limit. iOS only; `nil` elsewhere.
    public var availableBytes: UInt64?

    public init(physicalBytes: UInt64, footprintBytes: UInt64? = nil, residentBytes: UInt64? = nil, availableBytes: UInt64? = nil) {
        self.physicalBytes = physicalBytes
        self.footprintBytes = footprintBytes
        self.residentBytes = residentBytes
        self.availableBytes = availableBytes
    }

    public static func capture() -> MemorySnapshot {
        let task = Memory.taskInfo()
        return MemorySnapshot(physicalBytes: ProcessInfo.processInfo.physicalMemory,
                              footprintBytes: task?.footprint, residentBytes: task?.resident,
                              availableBytes: Memory.availableBytes())
    }
}

public enum Memory {
    public static func footprintBytes() -> UInt64? { taskInfo()?.footprint }

    /// Footprint in MB (10^6 bytes), one decimal place, as recorded by the Core ML harness.
    public static func footprintMB() -> Double? {
        footprintBytes().map { (Double($0) / 1e5).rounded() / 10 }
    }

    public static func availableBytes() -> UInt64? {
        #if os(iOS) || os(tvOS) || os(watchOS) || os(visionOS)
        return UInt64(os_proc_available_memory())
        #else
        return nil
        #endif
    }

    /// Asks the allocator to return free pages to the system (used before waiting for headroom).
    public static func relievePressure() {
        malloc_zone_pressure_relief(nil, 0)
    }

    static func taskInfo() -> (footprint: UInt64, resident: UInt64)? {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let kr = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        guard kr == KERN_SUCCESS else { return nil }
        return (UInt64(info.phys_footprint), UInt64(info.resident_size))
    }
}
