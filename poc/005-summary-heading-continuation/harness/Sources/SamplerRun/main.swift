// PoC 005 harness: PoC 003's harness (runs Xylo's generation loop once per (document, seed, arm))
// with one addition, an optional intervention per arm when the model tries to end before all
// four Summary sections are written:
//
// - "none": PoC 003's loop, unchanged. Its outputs must be token-identical to PoC 003's.
// - "insert_heading": when the model samples an end token while a later section is missing,
//   the end token is dropped and the next section's heading ("\n\n## Key Points\n") is appended
//   to the output, then sampling continues. Inserted tokens count toward the budget and enter the
//   penalty window like generated ones.
// - "suppress_end": while a later section is missing, the end tokens' logits are set to -inf
//   before sampling, so the model has to keep writing.
//
// Everything below that is not part of an intervention is PoC 003's code.
//
// The context settings, sampler chain, tokenization and stop checks are adapted from Xylo's
// GemmaLLMEngine (private app, commit 196a729): load + createContext + generate. Removed: the
// app's memory guards, thermal pacing and cancellation. Changed: the dist sampler gets a fixed
// seed instead of a random one, so every generation can be rerun. As in the app, only
// generated tokens enter the penalty window; prompt tokens are never accepted by the sampler.
import Foundation
import LlamaSwift

struct Arm: Decodable {
    let name: String
    let temperature: Float
    let top_p: Float
    let top_k: Int32
    let repeat_penalty: Float
    let frequency_penalty: Float
    let presence_penalty: Float
    let penalty_last_n: Int32
    let intervention: String
}

let interventions: Set<String> = ["none", "insert_heading", "suppress_end"]

struct Input: Decodable {
    let doc: Int
    let file: String
    let prompt: String
}

struct Record: Encodable {
    let arm: String
    let intervention: String
    let inserted: [Insertion]
    let doc: Int
    let file: String
    let seed: UInt32
    let prompt_tokens: Int
    let budget: Int
    let generated_tokens: Int
    let stop: String
    let prefill_ms: Double
    let generate_ms: Double
    let text: String
    let tokens: [Int32]
}

struct Insertion: Encodable {
    let heading: String
    let at_token: Int   // index in `tokens` where the inserted heading starts
    let n_tokens: Int
}

struct Generation {
    let budget: Int
    let stop: String
    let prefillMs: Double
    let generateMs: Double
    let text: String
    let tokens: [llama_token]
    let inserted: [Insertion]
}

// The four Summary sections, in order, and the heading check PoC 003's summarize.py scores with.
let sectionTitles = ["Introduction", "Summary", "Key Points", "Action Items"]
let headingPattern = try! NSRegularExpression(
    pattern: #"^\s*#{2,3}\s*(introduction|summary|key points|action items)\s*:?\s*$"#,
    options: [.caseInsensitive, .anchorsMatchLines])

/// The section that should come next: the one after the last section already written, or nil if
/// Action Items is written. Starts at Introduction if no heading is there yet.
func nextSection(after text: String) -> String? {
    let range = NSRange(text.startIndex..., in: text)
    var last = -1
    for m in headingPattern.matches(in: text, range: range) {
        guard let r = Range(m.range(at: 1), in: text) else { continue }
        let name = text[r].lowercased()
        if let i = sectionTitles.firstIndex(where: { $0.lowercased() == name }) { last = max(last, i) }
    }
    return last + 1 < sectionTitles.count ? sectionTitles[last + 1] : nil
}

// Xylo's 6 GB Qwen analysis settings (GemmaAnalysisService, useChatML branch).
let contextSize = 4096
let maxNewTokens = 288
let nGpuLayers: Int32 = 99
let nThreads: Int32 = 2
let nUbatch: UInt32 = 128   // the app's value below 8 GB of RAM
let stopString = "<|im_end|>"
let seeds: [UInt32] = [1, 2, 3, 4, 5]

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

var options: [String: String] = [:]
var argv = CommandLine.arguments.dropFirst().makeIterator()
while let key = argv.next() {
    guard key.hasPrefix("--"), let value = argv.next() else { break }
    options[String(key.dropFirst(2))] = value
}
guard let modelPath = options["model"], let armsPath = options["arms"],
      let inputsPath = options["inputs"], let outPath = options["out"] else {
    fail("usage: SamplerRun --model M.gguf --arms arms.json --inputs inputs.jsonl --out generations.jsonl")
}

let decoder = JSONDecoder()
guard let armsData = FileManager.default.contents(atPath: armsPath),
      let arms = try? decoder.decode([Arm].self, from: armsData) else { fail("cannot read \(armsPath)") }
for arm in arms where !interventions.contains(arm.intervention) {
    fail("arm \(arm.name): unknown intervention \(arm.intervention)")
}
guard let inputsText = try? String(contentsOfFile: inputsPath, encoding: .utf8) else { fail("cannot read \(inputsPath)") }
let inputs: [Input] = inputsText.split(separator: "\n").map {
    guard let input = try? decoder.decode(Input.self, from: Data($0.utf8)) else { fail("bad line in \(inputsPath)") }
    return input
}

llama_backend_init()
llama_log_set({ level, text, _ in
    guard level == GGML_LOG_LEVEL_ERROR, let text else { return }
    FileHandle.standardError.write(Data(String(cString: text).utf8))
}, nil)

var modelParams = llama_model_default_params()
modelParams.n_gpu_layers = nGpuLayers
guard let model = llama_model_load_from_file(modelPath, modelParams) else { fail("cannot load \(modelPath)") }

var ctxParams = llama_context_default_params()
ctxParams.n_ctx = UInt32(contextSize)
ctxParams.n_batch = UInt32(contextSize)
ctxParams.n_ubatch = nUbatch
ctxParams.n_threads = nThreads
ctxParams.n_threads_batch = nThreads
ctxParams.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED
guard let ctx = llama_init_from_model(model, ctxParams) else { fail("cannot create context") }
let vocab = llama_model_get_vocab(model)

var descBuf = [CChar](repeating: 0, count: 256)
llama_model_desc(model, &descBuf, descBuf.count)
log("model=\(String(cString: descBuf))")
log("system_info=\(String(cString: llama_print_system_info()))")
log("settings: ctx=\(contextSize) batch=\(contextSize) ubatch=\(nUbatch) threads=\(nThreads) gpu_layers=\(nGpuLayers) flash_attn=off max_new_tokens=\(maxNewTokens)")

func tokenize(_ text: String) -> [llama_token] {
    let capacity = Int32(text.utf8.count + 128)
    var tokens = [llama_token](repeating: 0, count: Int(capacity))
    let n = text.withCString { cStr in
        llama_tokenize(vocab, cStr, Int32(strlen(cStr)), &tokens, capacity, true, true)
    }
    guard n > 0 else { fail("tokenization failed") }
    return Array(tokens.prefix(Int(n)))
}

func piece(_ token: llama_token) -> String {
    var buf = [CChar](repeating: 0, count: 256)
    let len = llama_token_to_piece(vocab, token, &buf, 256, 0, true)
    return len > 0 ? String(cString: Array(buf.prefix(Int(len))) + [0]) : ""
}

// The ChatML markers must be single special tokens, or the prompt is not what the app sends.
guard tokenize("<|im_start|>").count == 1, tokenize(stopString).count == 1 else {
    fail("ChatML markers do not tokenize as single special tokens")
}

/// Plain text to tokens, with no special tokens added or parsed (for inserted headings).
func tokenizePlain(_ text: String) -> [llama_token] {
    let capacity = Int32(text.utf8.count + 16)
    var tokens = [llama_token](repeating: 0, count: Int(capacity))
    let n = text.withCString { cStr in
        llama_tokenize(vocab, cStr, Int32(strlen(cStr)), &tokens, capacity, false, false)
    }
    guard n > 0 else { fail("tokenization failed") }
    return Array(tokens.prefix(Int(n)))
}

// Tokens that end the output in the loop below: end-of-sequence, and <|im_end|> (the stop string).
let endTokens: [llama_token] = Array(Set([llama_vocab_eos(vocab), tokenize(stopString)[0]]))

func generate(prompt: [llama_token], arm: Arm, seed: UInt32) -> Generation {
    if let memory = llama_get_memory(ctx) { llama_memory_clear(memory, true) }

    var batch = llama_batch_init(Int32(prompt.count), 0, 1)
    defer { llama_batch_free(batch) }
    batch.n_tokens = Int32(prompt.count)
    for i in 0..<prompt.count {
        batch.token[i] = prompt[i]
        batch.pos[i] = Int32(i)
        batch.n_seq_id[i] = 1
        batch.seq_id[i]![0] = 0
        batch.logits[i] = (i == prompt.count - 1) ? 1 : 0
    }
    let prefillStart = DispatchTime.now()
    guard llama_decode(ctx, batch) == 0 else { fail("prefill failed") }
    let prefillMs = elapsedMs(since: prefillStart)

    guard let sampler = llama_sampler_chain_init(llama_sampler_chain_default_params()) else { fail("sampler init failed") }
    defer { llama_sampler_free(sampler) }
    llama_sampler_chain_add(sampler, llama_sampler_init_penalties(
        arm.penalty_last_n, arm.repeat_penalty, arm.frequency_penalty, arm.presence_penalty))
    if arm.top_k > 0 {
        llama_sampler_chain_add(sampler, llama_sampler_init_top_k(arm.top_k))
    }
    llama_sampler_chain_add(sampler, llama_sampler_init_temp(arm.temperature))
    llama_sampler_chain_add(sampler, llama_sampler_init_top_p(arm.top_p, 1))
    llama_sampler_chain_add(sampler, llama_sampler_init_dist(seed))

    let eos = llama_vocab_eos(vocab)
    let budget = min(maxNewTokens, contextSize - prompt.count - 1)
    var generated: [llama_token] = []
    var stop = "cap"
    var step = llama_batch_init(1, 0, 1)
    defer { llama_batch_free(step) }
    var pos = Int32(prompt.count)

    var inserted: [Insertion] = []
    var text = ""   // decoded output so far, for the section check

    /// Decodes one token at the next position; false on a decode error.
    func feed(_ token: llama_token, logits: Bool) -> Bool {
        step.n_tokens = 1
        step.token[0] = token
        step.pos[0] = pos
        step.n_seq_id[0] = 1
        step.seq_id[0]![0] = 0
        step.logits[0] = logits ? 1 : 0
        guard llama_decode(ctx, step) == 0 else { return false }
        pos += 1
        return true
    }

    let generateStart = DispatchTime.now()
    while generated.count < budget {
        if arm.intervention == "suppress_end", nextSection(after: text) != nil,
           let logits = llama_get_logits_ith(ctx, -1) {
            for t in endTokens { logits[Int(t)] = -.infinity }
        }
        let token = llama_sampler_sample(sampler, ctx, -1)
        let ends = token == eos || piece(token).contains(stopString)
        if ends, arm.intervention == "insert_heading", let next = nextSection(after: text) {
            let headingTokens = tokenizePlain("\n\n## \(next)\n")
            if generated.count + headingTokens.count < budget {
                inserted.append(Insertion(heading: next, at_token: generated.count, n_tokens: headingTokens.count))
                var ok = true
                for (i, t) in headingTokens.enumerated() {
                    llama_sampler_accept(sampler, t)
                    generated.append(t)
                    text += piece(t)
                    if !feed(t, logits: i == headingTokens.count - 1) { ok = false; break }
                }
                if !ok { stop = "decode_error"; break }
                continue
            }
        }
        if token == eos { stop = "eos"; break }
        if piece(token).contains(stopString) { stop = "stop_string"; break }
        generated.append(token)
        text += piece(token)

        guard feed(token, logits: true) else { stop = "decode_error"; break }
    }
    let generateMs = elapsedMs(since: generateStart)

    text = generated.map(piece).joined().trimmingCharacters(in: .whitespacesAndNewlines)
    return Generation(budget: budget, stop: stop, prefillMs: prefillMs, generateMs: generateMs,
                      text: text, tokens: generated, inserted: inserted)
}

FileManager.default.createFile(atPath: outPath, contents: nil)
guard let out = FileHandle(forWritingAtPath: outPath) else { fail("cannot write \(outPath)") }
defer { try? out.close() }
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]

let total = inputs.count * seeds.count * arms.count
var done = 0
// Arms are interleaved inside each (document, seed) so slow drift on the host hits all arms alike.
for input in inputs {
    let prompt = tokenize(input.prompt)
    for seed in seeds {
        for arm in arms {
            let g = generate(prompt: prompt, arm: arm, seed: seed)
            let record = Record(
                arm: arm.name, intervention: arm.intervention, inserted: g.inserted, doc: input.doc, file: input.file, seed: seed,
                prompt_tokens: prompt.count, budget: g.budget, generated_tokens: g.tokens.count,
                stop: g.stop, prefill_ms: (g.prefillMs * 10).rounded() / 10,
                generate_ms: (g.generateMs * 10).rounded() / 10, text: g.text, tokens: g.tokens)
            guard let line = try? encoder.encode(record) else { fail("encode failed") }
            out.write(line)
            out.write(Data("\n".utf8))
            done += 1
            log("[\(done)/\(total)] doc=\(input.doc) seed=\(seed) arm=\(arm.name) stop=\(g.stop) tokens=\(g.tokens.count) inserted=\(g.inserted.count) prompt=\(prompt.count)")
        }
    }
}

llama_free(ctx)
llama_model_free(model)
llama_backend_free()
log("done")
