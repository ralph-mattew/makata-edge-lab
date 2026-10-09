import Foundation

public enum DiskSpace {
    /// Space the app can use for downloads the user asked for, which counts purgeable
    /// storage iOS will free on demand. Falls back to the file-system free size.
    public static func availableForImportantUsage(at url: URL = URL(fileURLWithPath: NSHomeDirectory())) -> UInt64? {
        if let c = try? url.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey])
            .volumeAvailableCapacityForImportantUsage {
            return UInt64(max(c, 0))
        }
        return (try? FileManager.default.attributesOfFileSystem(forPath: url.path))?[.systemFreeSize] as? UInt64
    }

    /// Free space to keep after a model download (500 MB in Unawain, b0124e6).
    public static let defaultReserveBytes: UInt64 = 500_000_000

    /// Whether `bytes` can be written while leaving `reserve` free. Unknown free space counts as enough.
    public static func canFit(_ bytes: UInt64, reserve: UInt64 = defaultReserveBytes, at url: URL = URL(fileURLWithPath: NSHomeDirectory())) -> Bool {
        guard let free = availableForImportantUsage(at: url) else { return true }
        return free >= bytes &+ reserve
    }
}
