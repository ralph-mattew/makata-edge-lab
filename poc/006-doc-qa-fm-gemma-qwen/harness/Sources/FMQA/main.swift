// PoC 006 FoundationModels harness: one answer per item, with Xylo's chat options.
//
// Adapted from Xylo's DocumentChatEngine.askFoundationModels (private app, v1.2.0), first turn:
// a new LanguageModelSession on SystemLanguageModel(guardrails: .permissiveContentTransformations)
// with the grounding as instructions, the bare question as the prompt, and
// GenerationOptions(temperature: 0.3, maximumResponseTokens: 500), streamed. Removed: the app's
// repetition-loop break, the retry on an exceeded context window, and the post-processing
// (deduplication, dangling-fragment trim, empty-answer fallback). Errors are recorded, not
// retried. The framework takes no seed with the default sampling mode, so answers cannot be
// rerun token for token; that is why FMQA can repeat items (--repeat).
import Foundation
import FoundationModels

struct Arm: Decodable {
    let name: String
    let backend: String
    let temperature: Double
    let maximum_response_tokens: Int?
}

struct FMPrompt: Decodable {
    let instructions: String
    let prompt: String
}

struct Input: Decodable {
    let item: Int
    let fm: FMPrompt
}

struct Record: Encodable {
    let arm: String
    let item: Int
    let run: Int
    let instructions_tokens: Int?
    let response_tokens: Int?
    let stop: String
    let error: String?
    let first_text_ms: Double?
    let total_ms: Double
    let text: String
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

func errorName(_ error: Error) -> String {
    guard let e = error as? LanguageModelSession.GenerationError else { return "other: \(error)" }
    switch e {
    case .exceededContextWindowSize: return "exceededContextWindowSize"
    case .assetsUnavailable: return "assetsUnavailable"
    case .guardrailViolation: return "guardrailViolation"
    case .unsupportedGuide: return "unsupportedGuide"
    case .unsupportedLanguageOrLocale: return "unsupportedLanguageOrLocale"
    case .decodingFailure: return "decodingFailure"
    case .rateLimited: return "rateLimited"
    case .concurrentRequests: return "concurrentRequests"
    case .refusal: return "refusal"
    @unknown default: return "unknown: \(e)"
    }
}

var options: [String: String] = [:]
var argv = CommandLine.arguments.dropFirst().makeIterator()
while let key = argv.next() {
    guard key.hasPrefix("--"), let value = argv.next() else { break }
    options[String(key.dropFirst(2))] = value
}
guard let armsPath = options["arms"], let armName = options["arm"],
      let inputsPath = options["inputs"], let outPath = options["out"] else {
    fail("usage: FMQA --arms arms.json --arm NAME --inputs inputs.jsonl --out generations.jsonl [--limit N] [--run K]")
}
let limit = options["limit"].flatMap(Int.init) ?? Int.max
let runIndex = options["run"].flatMap(Int.init) ?? 1

let decoder = JSONDecoder()
guard let armsData = FileManager.default.contents(atPath: armsPath),
      let arms = try? decoder.decode([Arm].self, from: armsData),
      let arm = arms.first(where: { $0.name == armName }), arm.backend == "fm",
      let maxTokens = arm.maximum_response_tokens else { fail("arm \(armName): not a complete fm arm in \(armsPath)") }

guard let inputsText = try? String(contentsOfFile: inputsPath, encoding: .utf8) else { fail("cannot read \(inputsPath)") }
let inputs: [Input] = inputsText.split(separator: "\n").prefix(limit).map {
    guard let input = try? decoder.decode(Input.self, from: Data($0.utf8)) else { fail("bad line in \(inputsPath)") }
    return input
}

let model = SystemLanguageModel(guardrails: .permissiveContentTransformations)
guard model.isAvailable else { fail("FoundationModels unavailable: \(model.availability)") }
log("arm=\(arm.name) FoundationModels available; context_size=\(model.contextSize)")
log("settings: temperature=\(arm.temperature) maximumResponseTokens=\(maxTokens) guardrails=permissiveContentTransformations run=\(runIndex)")
let generationOptions = GenerationOptions(temperature: arm.temperature, maximumResponseTokens: maxTokens)

FileManager.default.createFile(atPath: outPath, contents: nil)
guard let out = FileHandle(forWritingAtPath: outPath) else { fail("cannot write \(outPath)") }
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]

for (n, input) in inputs.enumerated() {
    let session = LanguageModelSession(model: model, instructions: input.fm.instructions)
    let instructionsTokens = try? await model.tokenCount(for: Instructions(input.fm.instructions))
    var text = ""
    var firstTextMs: Double?
    var stop = "end"
    var errorText: String?
    let start = DispatchTime.now()
    do {
        for try await partial in session.streamResponse(to: input.fm.prompt, options: generationOptions) {
            if firstTextMs == nil, !partial.content.isEmpty { firstTextMs = elapsedMs(since: start) }
            text = partial.content
        }
    } catch {
        stop = "error"
        errorText = errorName(error)
    }
    let totalMs = elapsedMs(since: start)
    text = text.trimmingCharacters(in: .whitespacesAndNewlines)
    let responseTokens = text.isEmpty ? 0 : try? await model.tokenCount(for: text)
    let record = Record(
        arm: arm.name, item: input.item, run: runIndex, instructions_tokens: instructionsTokens,
        response_tokens: responseTokens, stop: stop, error: errorText,
        first_text_ms: firstTextMs.map { ($0 * 10).rounded() / 10 }, total_ms: (totalMs * 10).rounded() / 10,
        text: text)
    guard let line = try? encoder.encode(record) else { fail("encode failed") }
    out.write(line)
    out.write(Data("\n".utf8))
    log("[\(n + 1)/\(inputs.count)] item=\(input.item) arm=\(arm.name) run=\(runIndex) stop=\(stop)\(errorText.map { " error=\($0)" } ?? "") tokens=\(responseTokens.map(String.init) ?? "?")")
}
try? out.close()
log("done")
