import CryptoKit
import Foundation

/// SHA-256 and size of a model artifact, computed the same way as
/// `unawain-public-models/scripts/build_manifest.py`, so a downloaded package can be
/// checked against a release `model-manifest.json`.
///
/// For a directory (e.g. `.mlpackage`): files sorted component-wise by relative path, and
/// for each file the relative path (`/`-separated, UTF-8) followed by its bytes.
/// For a single file: its bytes.
public enum PackageHash {
    public static func sha256(of url: URL) throws -> String {
        var h = SHA256()
        if try isDirectory(url) {
            for f in try files(url) {
                h.update(data: Data(f.rel.joined(separator: "/").utf8))
                try stream(f.url) { h.update(data: $0) }
            }
        } else {
            try stream(url) { h.update(data: $0) }
        }
        return h.finalize().map { String(format: "%02x", $0) }.joined()
    }

    public static func sizeBytes(of url: URL) throws -> Int {
        guard try isDirectory(url) else { return try fileSize(url) }
        return try files(url).reduce(0) { $0 + (try fileSize($1.url)) }
    }

    static func isDirectory(_ url: URL) throws -> Bool {
        try url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory == true
    }

    static func fileSize(_ url: URL) throws -> Int {
        try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
    }

    static func files(_ root: URL) throws -> [(rel: [String], url: URL)] {
        let base = root.standardizedFileURL.pathComponents
        guard let e = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.isRegularFileKey]) else { return [] }
        var out: [(rel: [String], url: URL)] = []
        for case let url as URL in e where try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true {
            out.append((Array(url.standardizedFileURL.pathComponents.dropFirst(base.count)), url))
        }
        // Python sorts Path objects component-wise; match that, not whole-string order.
        return out.sorted { $0.rel.lexicographicallyPrecedes($1.rel) }
    }

    static func stream(_ url: URL, _ body: (Data) -> Void) throws {
        let fh = try FileHandle(forReadingFrom: url)
        defer { try? fh.close() }
        while try autoreleasepool(invoking: { () throws -> Bool in
            guard let chunk = try fh.read(upToCount: 1 << 20), !chunk.isEmpty else { return false }
            body(chunk)
            return true
        }) {}
    }
}
