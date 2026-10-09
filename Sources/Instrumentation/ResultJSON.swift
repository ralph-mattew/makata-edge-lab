import Foundation

/// JSON conventions shared by every result file in the lab: snake_case keys, sorted,
/// pretty-printed, trailing newline. Python harnesses write the same shape.
public enum ResultJSON {
    public static func encoder() -> JSONEncoder {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        e.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return e
    }

    public static func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }

    public static func write<T: Encodable>(_ value: T, to url: URL) throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        var data = try encoder().encode(value)
        data.append(0x0A)
        try data.write(to: url, options: .atomic)
    }
}
