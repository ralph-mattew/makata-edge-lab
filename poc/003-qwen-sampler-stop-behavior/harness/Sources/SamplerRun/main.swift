// PoC 003 harness: runs Xylo's generation loop once per (document, seed, arm).
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
}

struct Input: Decodable {
    let doc: Int
    let file: String
    let prompt: String
}

struct Record: Encodable {
    let arm: String
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

struct Generation {
    let budget: Int
    let stop: String
    let prefillMs: Double
    let generateMs: Double
    let text: String
    let tokens: [llama_token]
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

    let generateStart = DispatchTime.now()
    for _ in 0..<budget {
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

let total = inputs.count * seeds.count * arms.count
var done = 0
// Arms are interleaved inside each (document, seed) so slow drift on the host hits all arms alike.
for input in inputs {
    let prompt = tokenize(input.prompt)
    for seed in seeds {
        for arm in arms {
            let g = generate(prompt: prompt, arm: arm, seed: seed)
            let record = Record(
                arm: arm.name, doc: input.doc, file: input.file, seed: seed,
                prompt_tokens: prompt.count, budget: g.budget, generated_tokens: g.tokens.count,
                stop: g.stop, prefill_ms: (g.prefillMs * 10).rounded() / 10,
                generate_ms: (g.generateMs * 10).rounded() / 10, text: g.text, tokens: g.tokens)
            guard let line = try? encoder.encode(record) else { fail("encode failed") }
            out.write(line)
            out.write(Data("\n".utf8))
            done += 1
            log("[\(done)/\(total)] doc=\(input.doc) seed=\(seed) arm=\(arm.name) stop=\(g.stop) tokens=\(g.tokens.count) prompt=\(prompt.count)")
        }
    }
}

llama_free(ctx)
llama_model_free(model)
llama_backend_free()
log("done")
