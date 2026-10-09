// PoC 006 GGUF harness: one answer per (item, arm), through Xylo's chat generation loop.
//
// The context settings, sampler chain, tokenization and stop checks are adapted from Xylo's
// GemmaLLMEngine (private app, v1.2.0): createContext + prefillPrefix + generateWithCache, as a
// first chat turn runs them. As in the app, the prompt prefix is tokenized with BOS and the
// suffix without, and the two are joined. Removed: the app's memory guards, thermal pacing and
// cancellation. Changed: the dist sampler gets a fixed seed instead of a random one, and the
// prompt is prefilled in one batch instead of prefix then suffix (same tokens and positions).
// Only generated tokens enter the penalty window; prompt tokens are never accepted by the
// sampler, as in the app.
import Foundation
import LlamaSwift

struct Arm: Decodable {
    let name: String
    let backend: String
    let prompt_form: String?
    let model: String?
    let context: Int?
    let ubatch: UInt32?
    let threads: Int32?
    let gpu_layers: Int32?
    let max_new_tokens: Int?
    let stop_string: String?
    let temperature: Float
    let top_p: Float?
    let top_k: Int32?
    let repeat_penalty: Float?
    let frequency_penalty: Float?
    let presence_penalty: Float?
    let penalty_last_n: Int32?
    let seed: UInt32?
}

struct Prompt: Decodable {
    let prefix: String
    let suffix: String
}

struct Input: Decodable {
    let item: Int
    let gemma: Prompt
    let qwen: Prompt
}

struct Record: Encodable {
    let arm: String
    let item: Int
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
guard let armsPath = options["arms"], let armName = options["arm"],
      let inputsPath = options["inputs"], let outPath = options["out"] else {
    fail("usage: GGUFQA --arms arms.json --arm NAME --inputs inputs.jsonl --out generations.jsonl [--limit N] [--model PATH]")
}
let limit = options["limit"].flatMap(Int.init) ?? Int.max

let decoder = JSONDecoder()
guard let armsData = FileManager.default.contents(atPath: armsPath),
      let arms = try? decoder.decode([Arm].self, from: armsData) else { fail("cannot read \(armsPath)") }
guard let arm = arms.first(where: { $0.name == armName }), arm.backend == "gguf",
      let form = arm.prompt_form, let armModel = arm.model, let contextSize = arm.context,
      let nUbatch = arm.ubatch, let nThreads = arm.threads, let nGpuLayers = arm.gpu_layers,
      let maxNewTokens = arm.max_new_tokens, let stopString = arm.stop_string,
      let topP = arm.top_p, let topK = arm.top_k, let repeatPenalty = arm.repeat_penalty,
      let frequencyPenalty = arm.frequency_penalty, let presencePenalty = arm.presence_penalty,
      let penaltyLastN = arm.penalty_last_n, let seed = arm.seed,
      form == "gemma" || form == "qwen" else { fail("arm \(armName): not a complete gguf arm") }
let modelPath = options["model"] ?? armModel

guard let inputsText = try? String(contentsOfFile: inputsPath, encoding: .utf8) else { fail("cannot read \(inputsPath)") }
let inputs: [Input] = inputsText.split(separator: "\n").prefix(limit).map {
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
log("arm=\(arm.name) model=\(String(cString: descBuf)) file=\(modelPath)")
log("system_info=\(String(cString: llama_print_system_info()))")
log("settings: ctx=\(contextSize) batch=\(contextSize) ubatch=\(nUbatch) threads=\(nThreads) gpu_layers=\(nGpuLayers) flash_attn=off max_new_tokens=\(maxNewTokens) stop=\(stopString) seed=\(seed)")

func tokenize(_ text: String, addBOS: Bool) -> [llama_token] {
    let capacity = Int32(text.utf8.count + 128)
    var tokens = [llama_token](repeating: 0, count: Int(capacity))
    let n = text.withCString { cStr in
        llama_tokenize(vocab, cStr, Int32(strlen(cStr)), &tokens, capacity, addBOS, true)
    }
    guard n > 0 else { fail("tokenization failed") }
    return Array(tokens.prefix(Int(n)))
}

func piece(_ token: llama_token) -> String {
    var buf = [CChar](repeating: 0, count: 256)
    let len = llama_token_to_piece(vocab, token, &buf, 256, 0, true)
    return len > 0 ? String(cString: Array(buf.prefix(Int(len))) + [0]) : ""
}

// The turn markers must be single special tokens, or the prompt is not what the app sends.
let markers = form == "gemma" ? ["<|turn>", "<turn|>"] : ["<|im_start|>", "<|im_end|>"]
for marker in markers where tokenize(marker, addBOS: false).count != 1 {
    fail("\(marker) does not tokenize as a single special token")
}

struct Generation {
    let budget: Int
    let stop: String
    let prefillMs: Double
    let generateMs: Double
    let text: String
    let tokens: [llama_token]
}

func generate(prompt: [llama_token]) -> Generation {
    if let memory = llama_get_memory(ctx) { llama_memory_clear(memory, true) }
    // The app throws when the prompt leaves no room to generate; record it instead.
    guard prompt.count + 1 < contextSize else {
        return Generation(budget: 0, stop: "prompt_too_long", prefillMs: 0, generateMs: 0, text: "", tokens: [])
    }

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
        penaltyLastN, repeatPenalty, frequencyPenalty, presencePenalty))
    if topK > 0 {
        llama_sampler_chain_add(sampler, llama_sampler_init_top_k(topK))
    }
    llama_sampler_chain_add(sampler, llama_sampler_init_temp(arm.temperature))
    llama_sampler_chain_add(sampler, llama_sampler_init_top_p(topP, 1))
    llama_sampler_chain_add(sampler, llama_sampler_init_dist(seed))

    let eos = llama_vocab_eos(vocab)
    let budget = min(maxNewTokens, contextSize - prompt.count - 1)
    var generated: [llama_token] = []
    var stop = "cap"
    var step = llama_batch_init(1, 0, 1)
    defer { llama_batch_free(step) }
    var pos = Int32(prompt.count)

    let generateStart = DispatchTime.now()
    while generated.count < budget {
        let token = llama_sampler_sample(sampler, ctx, -1)
        if token == eos { stop = "eos"; break }
        if piece(token).contains(stopString) { stop = "stop_string"; break }
        generated.append(token)

        step.n_tokens = 1
        step.token[0] = token
        step.pos[0] = pos
        step.n_seq_id[0] = 1
        step.seq_id[0]![0] = 0
        step.logits[0] = 1
        guard llama_decode(ctx, step) == 0 else { stop = "decode_error"; break }
        pos += 1
    }
    let generateMs = elapsedMs(since: generateStart)

    let text = generated.map(piece).joined().trimmingCharacters(in: .whitespacesAndNewlines)
    return Generation(budget: budget, stop: stop, prefillMs: prefillMs, generateMs: generateMs,
                      text: text, tokens: generated)
}

FileManager.default.createFile(atPath: outPath, contents: nil)
guard let out = FileHandle(forWritingAtPath: outPath) else { fail("cannot write \(outPath)") }
defer { try? out.close() }
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]

for (n, input) in inputs.enumerated() {
    let p = form == "gemma" ? input.gemma : input.qwen
    let prompt = tokenize(p.prefix, addBOS: true) + tokenize(p.suffix, addBOS: false)
    let g = generate(prompt: prompt)
    let record = Record(
        arm: arm.name, item: input.item, seed: seed, prompt_tokens: prompt.count, budget: g.budget,
        generated_tokens: g.tokens.count, stop: g.stop, prefill_ms: (g.prefillMs * 10).rounded() / 10,
        generate_ms: (g.generateMs * 10).rounded() / 10, text: g.text, tokens: g.tokens)
    guard let line = try? encoder.encode(record) else { fail("encode failed") }
    out.write(line)
    out.write(Data("\n".utf8))
    log("[\(n + 1)/\(inputs.count)] item=\(input.item) arm=\(arm.name) stop=\(g.stop) tokens=\(g.tokens.count) prompt=\(prompt.count)")
}

llama_free(ctx)
llama_model_free(model)
llama_backend_free()
log("done")
