/* ============================================================
   Phone edition. Copyright 2026 Igor Gembitsky. MIT licence.

   The laptop program talks to Ollama at 127.0.0.1:11434 and to a small launcher.
   A phone has neither. This file stands in for both, so the program itself is the
   same page as on a laptop:

   - Requests to Ollama go to WebLLM, which runs the model inside this browser on the
     phone's graphics chip (WebGPU). The model is downloaded once, from Hugging Face,
     and kept in the browser's storage. After that it works with no internet.
   - Requests to the launcher (/alive, /bye, /quit, /log) are answered here.
   - A service worker (sw.js) keeps the page itself, so it opens with no internet.

   Nothing you type leaves the phone.
   ============================================================ */
(function () {
  "use strict";

  const OLLAMA = "http://127.0.0.1:11434";
  const WEBLLM = "lib/web-llm.js";       // @mlc-ai/web-llm 0.2.85, Apache 2.0
  const CTX = 4096;          // the context the phone models are built for
  const REPLY = 300;         // the longest reply, in tokens, as on a laptop

  // The names the program sees, and the WebLLM model behind each. Qwen3 4B is the same
  // model family as the laptop's qwen3:4b-instruct; its thinking is turned off per request.
  const MODELS = {
    "qwen3:4b": { label: "Standard", gb: 2.3, f16: "Qwen3-4B-q4f16_1-MLC", f32: "Qwen3-4B-q4f32_1-MLC",
      note: "Best answers. Needs a phone with 8 GB of memory, such as an iPhone 15 Pro or newer." },
    "qwen3:1.7b": { label: "Light", gb: 1.0, f16: "Qwen3-1.7B-q4f16_1-MLC", f32: "Qwen3-1.7B-q4f32_1-MLC",
      note: "Faster, and works on more phones. It makes more mistakes and holds back facts." }
  };
  const K = { choice: "vsp.phone.model", ready: "vsp.phone.ready.", loading: "vsp.phone.loading" };
  const ls = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
    del(k) { try { localStorage.removeItem(k); } catch {} }
  };

  const S = {
    gpu: null,            // null not checked, "" no WebGPU, "f16" or "f32"
    lib: null,            // the WebLLM module
    engine: null,         // the loaded engine
    name: "",             // the program's name for the loaded model
    loading: null,        // the promise of a load in progress
    pct: 0,
    phase: "",            // "download" or "load"
    error: "",
    wantDownload: false
  };

  const id = name => MODELS[name] && MODELS[name][S.gpu === "f16" ? "f16" : "f32"];
  const fail = (kind, msg) => Object.assign(new Error(msg || kind), { phone: kind });
  const json = (o, status) => new Response(JSON.stringify(o), { status: status || 200,
    headers: { "Content-Type": "application/json" } });

  async function gpu() {
    if (S.gpu !== null) return S.gpu;
    try {
      const a = navigator.gpu && await navigator.gpu.requestAdapter();
      S.gpu = !a ? "" : a.features.has("shader-f16") ? "f16" : "f32";
    } catch { S.gpu = ""; }
    return S.gpu;
  }
  async function lib() {
    if (!S.lib) S.lib = await import(new URL(WEBLLM, document.baseURI).href);
    return S.lib;
  }
  // A model counts as here only when a load finished once and the browser still has it.
  async function downloaded() {
    const out = [];
    for (const name of Object.keys(MODELS)) {
      if (!ls.get(K.ready + id(name))) continue;
      try { if (await (await lib()).hasModelInCache(id(name))) out.push(name); } catch {}
    }
    const want = ls.get(K.choice);
    return out.sort((a, b) => (b === want) - (a === want));
  }

  function progress(name, report) {
    const text = String(report.text || "");
    S.phase = /^(Start to fetch|Fetching)/.test(text) ? "download" : "load";
    S.pct = Math.max(0, Math.min(100, Math.floor((report.progress || 0) * 100)));
    // Mark only the step onto the graphics chip, where a phone with too little memory closes the page.
    if (S.phase === "load" && ls.get(K.loading) !== name) ls.set(K.loading, name);
    if (S.phase === "load") show();
    if (S.onDownload && S.phase === "download") S.onDownload(S.pct);
  }

  // Download (if needed) and load one model onto the graphics chip. Only one at a time.
  function load(name) {
    if (S.engine && S.name === name) return Promise.resolve(S.engine);
    if (S.loading) return S.loading;
    S.error = ""; S.pct = 0; S.phase = "load";
    S.loading = (async () => {
      const L = await lib();
      try {
        if (S.engine) { try { await S.engine.unload(); } catch {} S.engine = null; S.name = ""; }
        const e = new L.MLCEngine({ initProgressCallback: r => progress(name, r) });
        await e.reload(id(name), { context_window_size: CTX });
        S.engine = e; S.name = name;
        ls.set(K.ready + id(name), "1");
        ls.del(K.loading);
        try { navigator.storage && navigator.storage.persist && navigator.storage.persist(); } catch {}
        return e;
      } catch (err) {
        S.error = String(err && err.message || err).split("\n")[0].slice(0, 300);
        ls.del(K.loading);
        throw err;
      } finally {
        S.loading = null;
      }
    })();
    return S.loading;
  }

  /* ---- what the program sees as Ollama ---------------------------------- */
  async function tags() {
    if (!await gpu()) throw fail("nogpu");
    if (S.engine) return json({ models: [{ name: S.name, capabilities: ["completion"] }] });
    if (S.loading) throw fail("loading");
    const want = ls.get(K.choice), have = await downloaded();
    if (S.wantDownload && !have.includes(want)) return json({ models: [] });   // the program then asks to pull
    if (!have.length) throw fail("choose");
    if (S.error) throw fail("error");
    const name = have.includes(want) ? want : have[0];
    // The phone closed the page while it was loading the model last time: most likely it ran
    // out of memory. Ask before trying again, or the page would close itself again and again.
    if (ls.get(K.loading) === name) throw fail("crashed");
    load(name).then(() => window.checkConnection && checkConnection(), () => show());
    throw fail("loading");
  }

  function pull() {
    const name = ls.get(K.choice) || "qwen3:4b";
    const total = Math.round(MODELS[name].gb * 1e9);
    const enc = new TextEncoder();
    let ctl;
    const line = o => { try { ctl.enqueue(enc.encode(JSON.stringify(o) + "\n")); } catch {} };
    const body = new ReadableStream({
      start(c) {
        ctl = c;
        line({ status: "pulling manifest" });
        S.onDownload = pct => line({ status: "pulling", total, completed: Math.round(total * pct / 100) });
        load(name).then(() => {
          S.onDownload = null; S.wantDownload = false;
          line({ status: "success" }); c.close();
        }, err => {
          S.onDownload = null;
          line({ error: String(err && err.message || err).split("\n")[0] }); c.close();
        });
      }
    });
    return new Response(body, { headers: { "Content-Type": "application/x-ndjson" } });
  }

  // Keep the start of the conversation (the patient's script and first words) and the newest
  // turns. Drop the oldest turns in between when the conversation is longer than the model's
  // context. About 3.2 characters a token is a safe guess for English.
  function fit(messages, drop) {
    const m = messages.slice();
    const size = () => m.reduce((n, x) => n + Math.ceil(String(x.content).length / 3.2) + 6, 0);
    let dropped = 0;
    while (m.length > 4 && (size() > CTX - REPLY - 80 || dropped < drop)) { m.splice(3, 2); dropped++; }
    return m;
  }

  // WebLLM keeps the conversation it has read, and reads only the new question, when the
  // history it is given is exactly what it saw. The program sends each question with a note
  // added for that turn only, and keeps its history without the note and with the reply tidied.
  // So the history is given back to WebLLM as WebLLM saw it, when it is the same conversation.
  // Otherwise the phone reads the whole conversation again on every question.
  let seen = [];          // the messages WebLLM was given last time, and its reply
  function asSeen(messages) {
    const past = messages.slice(0, -1);
    if (past.length !== seen.length) return messages;
    for (let i = 0; i < past.length; i++) {
      const a = past[i], b = seen[i], x = String(a.content), y = String(b.content);
      if (a.role !== b.role) return messages;
      const same = x === y || (a.role === "user" && y.startsWith(x)) || (a.role === "assistant" && y.includes(x));
      if (!same) return messages;
    }
    return seen.concat(messages[messages.length - 1]);
  }

  function chat(init) {
    const req = JSON.parse(init.body);
    const signal = init.signal;
    const enc = new TextEncoder();
    let stopped = false;
    const body = new ReadableStream({
      async start(c) {
        const out = o => c.enqueue(enc.encode(JSON.stringify(o) + "\n"));
        const onAbort = () => {
          stopped = true;
          try { S.engine && S.engine.interruptGenerate(); } catch {}
          try { c.error(new DOMException("The question was stopped.", "AbortError")); } catch {}
        };
        if (signal) { if (signal.aborted) return onAbort(); signal.addEventListener("abort", onAbort); }
        let drop = 0;
        for (let attempt = 0; attempt < 3 && !stopped; attempt++) {
          try {
            const e = await load(S.name || req.model);
            const messages = fit(asSeen(req.messages), drop);
            let reply = "";
            const stream = await e.chat.completions.create({
              messages, stream: true, stream_options: { include_usage: true },
              temperature: (req.options && req.options.temperature) || 0.6, max_tokens: REPLY,
              extra_body: { enable_thinking: false }
            });
            for await (const ch of stream) {
              if (stopped) return;
              if (ch.usage) S.usage = ch.usage;
              const piece = ch.choices && ch.choices[0] && ch.choices[0].delta && ch.choices[0].delta.content;
              if (piece) { reply += piece; out({ message: { role: "assistant", content: piece } }); }
            }
            seen = stopped ? [] : messages.concat({ role: "assistant", content: reply });
            if (!stopped) { out({ done: true }); c.close(); }
            return;
          } catch (err) {
            seen = [];
            if (stopped) return;
            const msg = String(err && err.message || err);
            if (/context window|ContextWindow/i.test(msg)) { drop += 2; continue; }
            // The graphics chip was lost, for example after the phone locked: load again once.
            if (attempt === 0 && /device|lost|disposed|not loaded/i.test(msg)) {
              S.engine = null; S.name = ""; continue;
            }
            try { c.error(new Error(msg.split("\n")[0])); } catch {}
            return;
          }
        }
      }
    });
    return new Response(body, { headers: { "Content-Type": "application/x-ndjson" } });
  }

  async function ollama(path, init) {
    init = init || {};
    if (path.startsWith("/api/tags")) return tags();
    if (path.startsWith("/api/pull")) return pull();
    if (path.startsWith("/api/chat")) return chat(init);
    if (path.startsWith("/api/version")) return json({ version: "WebLLM in the browser, " + (S.gpu || "no WebGPU") });
    return json({ error: "not here" }, 404);
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.startsWith(OLLAMA)) return ollama(url.slice(OLLAMA.length), init);
    if (url === "cases/") return realFetch("cases/index.json", init);
    if (/^\/(alive|bye|quit|log)\b/.test(url)) return Promise.resolve(new Response(""));
    // The laptop's new-version notice links to a ZIP. The phone page updates by itself.
    if (url.includes("raw.githubusercontent.com/igembitsky/")) return Promise.resolve(new Response("", { status: 404 }));
    return realFetch(input, init);
  };
  const beacon = navigator.sendBeacon && navigator.sendBeacon.bind(navigator);
  navigator.sendBeacon = (url, data) => /^\/bye\b/.test(url) ? true : beacon ? beacon(url, data) : false;

  /* ---- what the learner sees while there is no patient yet ---------------- */
  function buttons(list) {
    return `<span class="phone-btns">` + list.map(([label, js, cls]) =>
      `<button type="button" class="btn ${cls || "ghost"} small" onclick="${js}">${label}</button>`).join("") + `</span>`;
  }
  function chooser(lead) {
    return lead + `<span class="phone-models">` + Object.entries(MODELS).map(([name, m]) =>
      `<button type="button" class="phone-model" onclick="PHONE.choose('${name}')">
         <b>${m.label}</b> <span class="phone-gb">${m.gb} GB</span><br><span>${m.note}</span></button>`).join("")
      + `</span>`;
  }
  function render(kind) {
    const busy = MODELS[S.name || ls.get(K.choice)] || MODELS["qwen3:4b"];
    switch (kind) {
      case "nogpu": return ["bad", "this browser cannot run the patient",
        `<b>This browser cannot run the patient.</b> The phone edition needs WebGPU: Safari on
         iOS 26 or newer, or Chrome on Android 12 or newer. On an older phone, use the laptop version.`];
      case "choose": return ["wait", "choose a patient model to download",
        chooser(`<b>Download the patient model, once.</b> After that it works with no internet.
          Use Wi-Fi, keep this page open, and keep the screen on until it finishes.`)];
      case "loading": return ["wait", "loading the patient into memory · " + S.pct + "%",
        `<b>Loading the ${busy.label.toLowerCase()} patient model into memory:</b> ${S.pct}%.
         This takes up to a minute each time the page opens.`, S.pct];
      case "crashed": return ["bad", "the patient model did not load",
        `<b>The page closed while it was loading the patient model.</b> The phone most likely ran out
         of memory. Close other apps and try again, or use the Light model.`
        + buttons([["Try again", "PHONE.retry()", "primary"], ["Use the Light model", "PHONE.choose('qwen3:1.7b')"],
                   ["Remove downloaded models", "PHONE.forget()"]])];
      default: return ["bad", "the patient model did not load",
        `<b>The patient model did not load:</b> ${esc(S.error || "unknown problem")}.`
        + buttons([["Try again", "PHONE.retry()", "primary"], ["Use the Light model", "PHONE.choose('qwen3:1.7b')"],
                   ["Remove downloaded models", "PHONE.forget()"]])];
    }
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch])); }
  let lastKind = "";
  function show(kind) {
    kind = kind || (S.loading ? "loading" : S.error ? "error" : lastKind);
    if (!kind || !window.setSetup) return;
    lastKind = kind;
    const [dot, status, html, pct] = render(kind);
    setStatus(dot, status);
    setSetup(html, pct == null ? null : pct, kind === "error" || kind === "crashed");
  }

  window.PHONE = {
    // checkConnection() calls this when the "Ollama" check fails. Returns its result.
    notReady(e) {
      if (!e || !e.phone) { S.error = String(e && e.message || e); show("error"); return false; }
      show(e.phone);
      return false;
    },
    sizeText(name) { return (MODELS[name] || MODELS["qwen3:4b"]).gb + " GB"; },
    choose(name) {
      if (!MODELS[name]) return;
      ls.set(K.choice, name); ls.del(K.loading);
      S.error = ""; S.wantDownload = true;
      try { WANTED = name; } catch {}
      if (S.engine && S.name !== name) { try { S.engine.unload(); } catch {} S.engine = null; S.name = ""; }
      downloaded().then(have => {
        if (have.includes(name)) { S.wantDownload = false; load(name).then(() => checkConnection(), () => show()); show("loading"); }
        else checkConnection();
      });
    },
    stats() { return JSON.stringify(S.usage || {}); },        // for tests and problem reports
    retry() { ls.del(K.loading); S.error = ""; checkConnection(); },
    async forget() {
      if (!confirm("Remove the downloaded patient models from this phone? Your saved encounters are kept.")) return;
      const L = await lib();
      for (const name of Object.keys(MODELS)) {
        for (const v of ["f16", "f32"]) {
          try { await L.deleteModelAllInfoInCache(MODELS[name][v]); } catch {}
          ls.del(K.ready + MODELS[name][v]);
        }
      }
      if (S.engine) { try { await S.engine.unload(); } catch {} }
      S.engine = null; S.name = ""; S.error = ""; ls.del(K.loading); ls.del(K.choice);
      checkConnection();
    }
  };

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "127.0.0.1")) {
    addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
  }
})();
