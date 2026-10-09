// PoC 007 chunker: contracts (as pages) in, chunks out.
//
// Follows the chunking Xylo runs on page text (DocumentChunker, private app, v1.2.0), as a first
// ingest runs it on the 6 and 8 GB tiers: each page is split on blank lines; a paragraph of at most
// 175 words is one chunk; a longer one is cut at sentence boundaries (Apple's sentence tokenizer),
// adding sentences until the next would pass 175 words; then every chunk after the first gets the
// last 30 words of the previous chunk's own text in front of it. Words are runs between spaces,
// as in the app.
//
// Output, one line per contract: its chunks as {page, overlap, own}. A chunk's text is
// `overlap + " " + own`, or `own` for the first chunk.
import Foundation
import NaturalLanguage

struct ContractIn: Decodable {
    let contract: String
    let pages: [String]
}

struct ChunkOut: Encodable {
    let page: Int
    let overlap: String
    let own: String
}

struct ContractOut: Encodable {
    let contract: String
    let chunks: [ChunkOut]
}

let targetWords = 175
let overlapWords = 30

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func spaceWords(_ text: String) -> [Substring] {
    text.split(separator: " ", omittingEmptySubsequences: true)
}

func sentences(of text: String) -> [String] {
    let tokenizer = NLTokenizer(unit: .sentence)
    tokenizer.string = text
    var result: [String] = []
    tokenizer.enumerateTokens(in: text.startIndex..<text.endIndex) { range, _ in
        let sentence = String(text[range]).trimmingCharacters(in: .whitespacesAndNewlines)
        if !sentence.isEmpty { result.append(sentence) }
        return true
    }
    return result.isEmpty ? [text] : result
}

func chunkPage(_ text: String, page: Int) -> [(page: Int, text: String)] {
    var chunks: [(page: Int, text: String)] = []
    let paragraphs = text.components(separatedBy: "\n\n")
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
    for paragraph in paragraphs {
        let words = spaceWords(paragraph)
        guard !words.isEmpty else { continue }
        if words.count <= targetWords {
            chunks.append((page, paragraph))
            continue
        }
        var current: [String] = []
        var currentWords = 0
        for sentence in sentences(of: paragraph) {
            let n = spaceWords(sentence).count
            if currentWords + n > targetWords && !current.isEmpty {
                chunks.append((page, current.joined(separator: " ")))
                current = []
                currentWords = 0
            }
            current.append(sentence)
            currentWords += n
        }
        if !current.isEmpty { chunks.append((page, current.joined(separator: " "))) }
    }
    return chunks
}

var options: [String: String] = [:]
var argv = CommandLine.arguments.dropFirst().makeIterator()
while let key = argv.next() {
    guard key.hasPrefix("--"), let value = argv.next() else { break }
    options[String(key.dropFirst(2))] = value
}
guard let inPath = options["contracts"], let outPath = options["out"] else {
    fail("usage: Chunker --contracts contracts.jsonl --out chunks.jsonl")
}
guard let text = try? String(contentsOfFile: inPath, encoding: .utf8) else { fail("cannot read \(inPath)") }

FileManager.default.createFile(atPath: outPath, contents: nil)
guard let out = FileHandle(forWritingAtPath: outPath) else { fail("cannot write \(outPath)") }
defer { try? out.close() }
let decoder = JSONDecoder()
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]

var total = 0
for line in text.split(separator: "\n") {
    guard let contract = try? decoder.decode(ContractIn.self, from: Data(line.utf8)) else { fail("bad line") }
    var originals: [(page: Int, text: String)] = []
    for (i, page) in contract.pages.enumerated() {
        originals += chunkPage(page, page: i + 1)
    }
    var chunks: [ChunkOut] = []
    for (i, chunk) in originals.enumerated() {
        let overlap = i == 0 ? "" : spaceWords(originals[i - 1].text).suffix(overlapWords).joined(separator: " ")
        chunks.append(ChunkOut(page: chunk.page, overlap: overlap, own: chunk.text))
    }
    guard let encoded = try? encoder.encode(ContractOut(contract: contract.contract, chunks: chunks)) else {
        fail("encode failed")
    }
    out.write(encoded)
    out.write(Data("\n".utf8))
    total += chunks.count
}
FileHandle.standardError.write(Data("\(total) chunks\n".utf8))
