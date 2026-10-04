// The patient model, run with llama.cpp on the phone's graphics chip (Metal).
// The same model file Ollama uses on a laptop: qwen3:4b-instruct, a GGUF file.
import Foundation
import llama

struct ChatMessage { let role: String; let content: String }

final class LlamaEngine: @unchecked Sendable {
    static let shared = LlamaEngine()

    /// The context, in tokens. The laptop asks Ollama for 8,192.
    var nCtx: UInt32 = 8192
    private let queue = DispatchQueue(label: "llama")     // one thing at a time on the model
    private var model: OpaquePointer?
    private var ctx: OpaquePointer?
    private var vocab: OpaquePointer?
    private var cached: [llama_token] = []              // what the context holds now
    private(set) var loadedPath: String?
    private var backendReady = false

    var isLoaded: Bool { queue.sync { model != nil } }

    func load(path: String) throws {
        try queue.sync {
            if loadedPath == path, model != nil { return }
            unloadLocked()
            if !backendReady {
                llama_log_set({ level, text, _ in
                    guard let text, level.rawValue >= GGML_LOG_LEVEL_WARN.rawValue else { return }
                    Log.write("llama: " + String(cString: text).trimmingCharacters(in: .whitespacesAndNewlines))
                }, nil)
                llama_backend_init(); backendReady = true
            }
            Log.write("loading the model", memory: true)
            let t0 = Date()
            var mp = llama_model_default_params()
            mp.n_gpu_layers = 99                          // every layer on the graphics chip
            guard let m = llama_model_load_from_file(path, mp) else { throw err("the model file could not be loaded") }
            var cp = llama_context_default_params()
            cp.n_ctx = nCtx
            cp.n_batch = 512
            cp.n_ubatch = 512
            cp.n_threads = 4
            cp.n_threads_batch = 4
            cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED
            // 8-bit cache: half the memory of the laptop's 16-bit cache, the same answers in practice
            cp.type_k = GGML_TYPE_Q8_0
            cp.type_v = GGML_TYPE_Q8_0
            guard let c = llama_init_from_model(m, cp) else { llama_model_free(m); throw err("the model did not fit in memory") }
            model = m; ctx = c; vocab = llama_model_get_vocab(m); cached = []; loadedPath = path
            Log.write(String(format: "model loaded in %.1f s, context %d tokens", Date().timeIntervalSince(t0), nCtx), memory: true)
        }
    }

    func unload() { queue.sync { unloadLocked() } }
    private func unloadLocked() {
        if let ctx { llama_free(ctx) }
        if let model { llama_model_free(model) }
        ctx = nil; model = nil; vocab = nil; cached = []; loadedPath = nil
    }

    private func err(_ s: String) -> NSError { NSError(domain: "llama", code: 1, userInfo: [NSLocalizedDescriptionKey: s]) }

    /// Qwen's chat format, written out as Ollama's template for qwen3:4b-instruct writes it.
    static func prompt(_ msgs: [ChatMessage]) -> String {
        var s = ""
        for m in msgs {
            let role = m.role == "assistant" ? "assistant" : m.role == "system" ? "system" : "user"
            s += "<|im_start|>\(role)\n\(m.content)<|im_end|>\n"
        }
        return s + "<|im_start|>assistant\n"
    }

    private func tokenize(_ text: String) -> [llama_token] {
        let utf8 = Array(text.utf8CString)
        var toks = [llama_token](repeating: 0, count: utf8.count + 16)
        var n = llama_tokenize(vocab, text, Int32(utf8.count - 1), &toks, Int32(toks.count), false, true)
        if n < 0 {
            toks = [llama_token](repeating: 0, count: Int(-n))
            n = llama_tokenize(vocab, text, Int32(utf8.count - 1), &toks, Int32(toks.count), false, true)
        }
        return Array(toks.prefix(Int(max(n, 0))))
    }

    private func piece(_ t: llama_token) -> [UInt8] {
        var buf = [CChar](repeating: 0, count: 64)
        var n = llama_token_to_piece(vocab, t, &buf, Int32(buf.count), 0, false)
        if n < 0 { buf = [CChar](repeating: 0, count: Int(-n)); n = llama_token_to_piece(vocab, t, &buf, Int32(buf.count), 0, false) }
        return buf.prefix(Int(max(n, 0))).map { UInt8(bitPattern: $0) }
    }

    struct Stats { var promptTokens = 0; var reused = 0; var generated = 0; var prefillSeconds = 0.0; var genSeconds = 0.0 }

    /// Answers the conversation. Calls onText with each new piece of text. Returns when done.
    /// The conversation so far stays in the context, so the next question reads only what is new.
    func chat(_ messages: [ChatMessage], temperature: Float, maxTokens: Int,
              cancelled: @escaping () -> Bool, onText: @escaping (String) -> Void) throws -> Stats {
        try queue.sync {
            guard let ctx, let vocab else { throw err("the model is not loaded") }
            var st = Stats()
            var msgs = messages
            var toks = tokenize(Self.prompt(msgs))
            // Too long for the context: leave out the oldest turns after the patient's first words.
            while toks.count + maxTokens > Int(nCtx), msgs.count > 4 {
                msgs.removeSubrange(3...4); toks = tokenize(Self.prompt(msgs))
            }
            st.promptTokens = toks.count
            var keep = 0
            while keep < min(cached.count, toks.count), cached[keep] == toks[keep] { keep += 1 }
            if keep == toks.count { keep -= 1 }                    // the last token must be read again
            let mem = llama_get_memory(ctx)
            _ = llama_memory_seq_rm(mem, 0, Int32(keep), -1)
            cached = Array(cached.prefix(keep))
            st.reused = keep

            let t0 = Date()
            var i = keep
            while i < toks.count {
                if cancelled() { return st }
                let n = min(512, toks.count - i)
                var part = Array(toks[i..<(i + n)])
                let rc = part.withUnsafeMutableBufferPointer { llama_decode(ctx, llama_batch_get_one($0.baseAddress, Int32(n))) }
                if rc != 0 { cached = []; llama_memory_clear(mem, true); throw err("the model could not read the question (\(rc))") }
                cached += part; i += n
            }
            st.prefillSeconds = Date().timeIntervalSince(t0)

            let chain = llama_sampler_chain_init(llama_sampler_chain_default_params())!
            defer { llama_sampler_free(chain) }
            // Ollama's settings for qwen3:4b-instruct: top_k 20, top_p 0.8; the temperature comes from the page.
            llama_sampler_chain_add(chain, llama_sampler_init_top_k(20))
            llama_sampler_chain_add(chain, llama_sampler_init_top_p(0.8, 1))
            llama_sampler_chain_add(chain, llama_sampler_init_temp(temperature))
            llama_sampler_chain_add(chain, llama_sampler_init_dist(UInt32.random(in: 0...UInt32.max)))

            let t1 = Date()
            var pending: [UInt8] = []
            var text = ""
            for _ in 0..<maxTokens {
                if cancelled() { break }
                var t = llama_sampler_sample(chain, ctx, -1)
                if llama_vocab_is_eog(vocab, t) { break }
                pending += piece(t)
                // send only whole characters
                if let s = String(validating: pending, as: UTF8.self) {
                    text += s; pending = []
                    if text.contains("<|im_end|>") || text.contains("<|im_start|>") { break }
                    onText(s)
                }
                let rc = llama_decode(ctx, llama_batch_get_one(&t, 1))
                if rc != 0 { break }
                cached.append(t)
                st.generated += 1
            }
            st.genSeconds = Date().timeIntervalSince(t1)
            return st
        }
    }
}
