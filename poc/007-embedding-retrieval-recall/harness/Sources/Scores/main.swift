// PoC 007 scores: per item, one score per chunk of its contract.
//
//   --mode kw   Xylo's keyword score (share of the question's keywords found in the chunk)
//   --mode nl   cosine similarity of Apple NLEmbedding sentence vectors
//   --mode eg   cosine similarity of EmbeddingGemma 300M vectors
//
// Adapted from Xylo v1.2.0 (private app): DocumentEmbedder (NLEmbedding path, keyword score,
// cosine similarity) and EmbeddingEngine (EmbeddingGemma through llama.cpp: context 2,048, mean
// pooling, 2 threads, all layers on the GPU, flash attention off, the model card's task prefixes,
// vectors L2-normalized). Language handling follows the app: chunks use the language detected from
// the start of the contract, each question its own detected language. Where NLEmbedding returns no
// vector the score is null; the app would substitute a hashed keyword vector, which only matters
// when both sides fail.
import Accelerate
import Foundation
import LlamaSwift
import NaturalLanguage

struct ItemIn: Decodable {
    let item: Int
    let contract: String
    let question: String
}

struct ContractIn: Decodable {
    let contract: String
    let language_sample: String
}

struct ChunkIn: Decodable {
    let overlap: String
    let own: String
    var text: String { overlap.isEmpty ? own : overlap + " " + own }
}

struct ChunksIn: Decodable {
    let contract: String
    let chunks: [ChunkIn]
}

struct ScoreRecord: Encodable {
    let item: Int
    let contract: String
    let mode: String
    let scores: [Double?]
    let language: String?
    let query_language: String?
}

struct TimingRecord: Encodable {
    let mode: String
    let contract: String
    let chunks: Int
    let tokens: Int
    let truncated: Int
    let nil_chunks: Int
    let chunk_ms: [Double]
    let query_ms: [Double]
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func log(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

func elapsedMs(since start: DispatchTime) -> Double {
    Double(DispatchTime.now().uptimeNanoseconds - start.uptimeNanoseconds) / 1_000_000
}

func round6(_ x: Double) -> Double { (x * 1_000_000).rounded() / 1_000_000 }

// MARK: - Keyword score

// The stopword and suffix tables are Xylo's and are not published. They are loaded from a JSON
// file ({"stopwords": [...], "suffixes": [...]}) given by --keywords, in kw mode only.
var stopWords: Set<String> = []
var suffixes: [String] = []

func loadKeywordTables(_ path: String) {
    guard let data = FileManager.default.contents(atPath: path),
          let json = try? JSONSerialization.jsonObject(with: data) as? [String: [String]],
          let words = json["stopwords"], let sfx = json["suffixes"] else {
        fail("cannot read keyword tables from \(path)")
    }
    stopWords = Set(words)
    suffixes = sfx
}

func simpleStem(_ word: String) -> String {
    guard word.count > 4 else { return word }
    for suffix in suffixes {
        guard word.hasSuffix(suffix) else { continue }
        let stem = String(word.dropLast(suffix.count))
        if stem.count >= 3 { return stem }
    }
    return word
}

func extractKeywords(_ text: String) -> [String] {
    text.lowercased()
        .components(separatedBy: .alphanumerics.inverted)
        .filter { $0.count > 2 && !stopWords.contains($0) }
        .map { simpleStem($0) }
}

func keywordScore(queryTerms: [String], chunkText: String) -> Double {
    guard !queryTerms.isEmpty else { return 0 }
    let chunkTerms = Set(extractKeywords(chunkText))
    let matches = queryTerms.filter { chunkTerms.contains($0) }.count
    return Double(matches) / Double(queryTerms.count)
}

// MARK: - Cosine

func cosine(_ a: [Double], _ b: [Double]) -> Double {
    guard a.count == b.count, !a.isEmpty else { return 0 }
    let dot = vDSP.dot(a, b)
    let magA = sqrt(vDSP.sumOfSquares(a))
    let magB = sqrt(vDSP.sumOfSquares(b))
    guard magA > 0 && magB > 0 else { return 0 }
    return dot / (magA * magB)
}

// MARK: - EmbeddingGemma through llama.cpp

final class EmbeddingEngine {
    private var model: OpaquePointer?
    private var context: OpaquePointer?
    let contextSize = 2048
    private(set) var lastTokens = 0
    private(set) var lastTruncated = false

    init(modelPath: String) {
        var modelParams = llama_model_default_params()
        modelParams.n_gpu_layers = 999
        guard let m = llama_model_load_from_file(modelPath, modelParams) else { fail("cannot load \(modelPath)") }
        model = m
        var ctxParams = llama_context_default_params()
        ctxParams.n_ctx = UInt32(contextSize)
        ctxParams.n_batch = UInt32(contextSize)
        ctxParams.n_ubatch = UInt32(contextSize)
        ctxParams.n_threads = 2
        ctxParams.n_threads_batch = 2
        ctxParams.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED
        ctxParams.embeddings = true
        ctxParams.pooling_type = LLAMA_POOLING_TYPE_MEAN
        guard let ctx = llama_init_from_model(m, ctxParams) else { fail("cannot create context") }
        context = ctx
    }

    var dimension: Int { Int(llama_model_n_embd(model)) }

    enum Mode {
        case document, query
        func prompt(for text: String) -> String {
            switch self {
            case .document: return "title: none | text: \(text)"
            case .query: return "task: search result | query: \(text)"
            }
        }
    }

    func embed(_ text: String, mode: Mode) -> [Double] {
        guard let model, let ctx = context else { fail("engine not loaded") }
        let vocab = llama_model_get_vocab(model)
        let prompt = mode.prompt(for: text)
        let capacity = Int32(prompt.utf8.count + 128)
        var tokens = [llama_token](repeating: 0, count: Int(capacity))
        let n = prompt.withCString { cStr in
            llama_tokenize(vocab, cStr, Int32(strlen(cStr)), &tokens, capacity, true, true)
        }
        guard n > 0 else { fail("tokenization failed") }
        tokens = Array(tokens.prefix(Int(n)))
        lastTruncated = tokens.count > contextSize
        if lastTruncated { tokens = Array(tokens.prefix(contextSize)) }
        lastTokens = tokens.count

        if let memory = llama_get_memory(ctx) { llama_memory_clear(memory, true) }
        var batch = llama_batch_init(Int32(tokens.count), 0, 1)
        defer { llama_batch_free(batch) }
        batch.n_tokens = Int32(tokens.count)
        for i in 0..<tokens.count {
            batch.token[i] = tokens[i]
            batch.pos[i] = Int32(i)
            batch.n_seq_id[i] = 1
            batch.seq_id[i]![0] = 0
            batch.logits[i] = 0
        }
        guard llama_decode(ctx, batch) == 0 else { fail("decode failed") }
        guard let ptr = llama_get_embeddings_seq(ctx, 0) else { fail("no sequence embedding") }
        let dim = dimension
        var vector = [Double](repeating: 0, count: dim)
        for i in 0..<dim { vector[i] = Double(ptr[i]) }
        let mag = sqrt(vector.reduce(0) { $0 + $1 * $1 })
        return mag > 0 ? vector.map { $0 / mag } : vector
    }

    deinit {
        if let context { llama_free(context) }
        if let model { llama_model_free(model) }
    }
}

// MARK: - Main

var options: [String: String] = [:]
var argv = CommandLine.arguments.dropFirst().makeIterator()
while let key = argv.next() {
    guard key.hasPrefix("--"), let value = argv.next() else { break }
    options[String(key.dropFirst(2))] = value
}
guard let mode = options["mode"], ["kw", "nl", "eg"].contains(mode),
      let contractsPath = options["contracts"], let chunksPath = options["chunks"],
      let itemsPath = options["items"], let outPath = options["out"] else {
    fail("usage: Scores --mode kw|nl|eg --contracts contracts.jsonl --chunks chunks.jsonl --items items.jsonl --out scores.jsonl [--keywords keywords.json] [--timing timing.jsonl] [--model PATH] [--limit N]")
}
if mode == "kw" {
    guard let path = options["keywords"] else { fail("--keywords is required for kw") }
    loadKeywordTables(path)
}
let limit = options["limit"].flatMap(Int.init) ?? Int.max

let decoder = JSONDecoder()
func lines(_ path: String) -> [Substring] {
    guard let text = try? String(contentsOfFile: path, encoding: .utf8) else { fail("cannot read \(path)") }
    return text.split(separator: "\n")
}
let contracts = lines(contractsPath).prefix(limit).map { line -> ContractIn in
    guard let c = try? decoder.decode(ContractIn.self, from: Data(line.utf8)) else { fail("bad contract line") }
    return c
}
var chunksByContract: [String: [ChunkIn]] = [:]
for line in lines(chunksPath) {
    guard let c = try? decoder.decode(ChunksIn.self, from: Data(line.utf8)) else { fail("bad chunks line") }
    chunksByContract[c.contract] = c.chunks
}
var itemsByContract: [String: [ItemIn]] = [:]
for line in lines(itemsPath) {
    guard let i = try? decoder.decode(ItemIn.self, from: Data(line.utf8)) else { fail("bad item line") }
    itemsByContract[i.contract, default: []].append(i)
}

FileManager.default.createFile(atPath: outPath, contents: nil)
guard let out = FileHandle(forWritingAtPath: outPath) else { fail("cannot write \(outPath)") }
defer { try? out.close() }
var timingOut: FileHandle?
if let timingPath = options["timing"] {
    FileManager.default.createFile(atPath: timingPath, contents: nil)
    timingOut = FileHandle(forWritingAtPath: timingPath)
}
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
func write(_ value: some Encodable, to handle: FileHandle?) {
    guard let data = try? encoder.encode(value) else { fail("encode failed") }
    handle?.write(data)
    handle?.write(Data("\n".utf8))
}

let recognizer = NLLanguageRecognizer()
func detectLanguage(_ text: String) -> NLLanguage {
    recognizer.reset()
    recognizer.processString(String(text.prefix(500)))
    return recognizer.dominantLanguage ?? .english
}
var embeddings: [NLLanguage: NLEmbedding] = [:]
func nlEmbedding(for language: NLLanguage) -> NLEmbedding? {
    if let cached = embeddings[language] { return cached }
    let embedding = NLEmbedding.sentenceEmbedding(for: language) ?? NLEmbedding.sentenceEmbedding(for: .english)
    if let embedding { embeddings[language] = embedding }
    return embedding
}

var engine: EmbeddingEngine?
if mode == "eg" {
    guard let modelPath = options["model"] else { fail("--model is required for eg") }
    llama_backend_init()
    llama_log_set({ level, text, _ in
        guard level == GGML_LOG_LEVEL_ERROR, let text else { return }
        FileHandle.standardError.write(Data(String(cString: text).utf8))
    }, nil)
    let loadStart = DispatchTime.now()
    engine = EmbeddingEngine(modelPath: modelPath)
    log("loaded \(modelPath) dim=\(engine!.dimension) in \(Int(elapsedMs(since: loadStart))) ms")
    _ = engine!.embed("warm-up", mode: .document)
}

for (n, contract) in contracts.enumerated() {
    guard let chunks = chunksByContract[contract.contract], let items = itemsByContract[contract.contract] else {
        fail("no chunks or items for \(contract.contract)")
    }
    let texts = chunks.map(\.text)
    var chunkMs: [Double] = []
    var queryMs: [Double] = []
    var tokens = 0
    var truncated = 0
    var nilChunks = 0

    switch mode {
    case "kw":
        for item in items {
            let terms = extractKeywords(item.question)
            let scores = texts.map { Optional(round6(keywordScore(queryTerms: terms, chunkText: $0))) }
            write(ScoreRecord(item: item.item, contract: item.contract, mode: mode, scores: scores,
                              language: nil, query_language: nil), to: out)
        }
    case "nl":
        let language = detectLanguage(contract.language_sample)
        let embedding = nlEmbedding(for: language)
        var vectors: [[Double]?] = []
        for text in texts {
            let start = DispatchTime.now()
            vectors.append(embedding?.vector(for: text))
            chunkMs.append(elapsedMs(since: start))
        }
        nilChunks = vectors.filter { $0 == nil }.count
        for item in items {
            let queryLanguage = detectLanguage(item.question)
            let start = DispatchTime.now()
            let query = nlEmbedding(for: queryLanguage)?.vector(for: item.question)
            queryMs.append(elapsedMs(since: start))
            let scores: [Double?] = vectors.map { v in
                guard let query, let v else { return nil }
                return round6(cosine(query, v))
            }
            write(ScoreRecord(item: item.item, contract: item.contract, mode: mode, scores: scores,
                              language: language.rawValue, query_language: queryLanguage.rawValue), to: out)
        }
    default:
        guard let engine else { fail("engine missing") }
        var vectors: [[Double]] = []
        for text in texts {
            let start = DispatchTime.now()
            vectors.append(engine.embed(text, mode: .document))
            chunkMs.append(elapsedMs(since: start))
            tokens += engine.lastTokens
            if engine.lastTruncated { truncated += 1 }
        }
        var queries: [String: [Double]] = [:]
        for item in items {
            if queries[item.question] == nil {
                let start = DispatchTime.now()
                queries[item.question] = engine.embed(item.question, mode: .query)
                queryMs.append(elapsedMs(since: start))
            }
            let query = queries[item.question]!
            let scores: [Double?] = vectors.map { round6(cosine(query, $0)) }
            write(ScoreRecord(item: item.item, contract: item.contract, mode: mode, scores: scores,
                              language: nil, query_language: nil), to: out)
        }
    }

    write(TimingRecord(mode: mode, contract: contract.contract, chunks: texts.count, tokens: tokens,
                       truncated: truncated, nil_chunks: nilChunks,
                       chunk_ms: chunkMs.map { (($0 * 100).rounded() / 100) },
                       query_ms: queryMs.map { (($0 * 100).rounded() / 100) }), to: timingOut)
    log("[\(n + 1)/\(contracts.count)] \(mode) chunks=\(texts.count) items=\(items.count)")
}

var usage = rusage()
getrusage(RUSAGE_SELF, &usage)
log("peak_rss_mb=\(usage.ru_maxrss / 1_048_576)")
engine = nil
if mode == "eg" { llama_backend_free() }
log("done")
