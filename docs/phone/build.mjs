// Builds the phone edition from the laptop program, so there is one program to change.
//
//   node docs/phone/build.mjs           write docs/phone/index.html, cases/, sw.js
//   node docs/phone/build.mjs --check   fail if those files are out of date
//
// It copies app/index.html, changes the few lines that only make sense on a laptop, and adds
// phone.js, which stands in for Ollama and the launcher. Every change must match exactly, so a
// change to app/index.html that breaks one stops the build instead of passing quietly.
import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync, rmSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const CHECK = process.argv.includes("--check");

const HEAD = `<meta name="theme-color" content="#0B6B4F">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Patient">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" href="icon-192.png">
<style>
/* Phone edition: there is no launcher to quit, and the choice of model is two big buttons. */
#stopApp{display:none!important}
.phone-models{display:grid;gap:10px;margin-top:12px}
.phone-model{all:unset;box-sizing:border-box;display:block;cursor:pointer;padding:12px 14px;border:1px solid var(--line);
  border-radius:10px;background:var(--panel);color:var(--body);line-height:1.4}
.phone-model b{color:var(--ink)} .phone-model:focus-visible{outline:2px solid var(--green);outline-offset:2px}
.phone-gb{color:var(--green-ink);font-weight:600}
.phone-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
</style>
<script src="phone.js"></script>
`;

// [what to find, what to put there, how many times it must be found]
const EDITS = [
  ["<title>Virtual Standardized Patient Simulator</title>",
   "<title>Virtual Standardized Patient Simulator</title>\n" + HEAD, 1],
  // the models: Qwen3 4B, as on a laptop, or Qwen3 1.7B for phones with less memory
  [`  model: "qwen3:4b-instruct",\n  fallbackModels: ["qwen3:4b-instruct", "qwen3:4b", "llama3.1:8b", "granite4.1:3b"],`,
   `  model: "qwen3:4b",\n  fallbackModels: ["qwen3:4b", "qwen3:1.7b"],`, 1],
  ["const WANTED = CFG.model;", "let WANTED = CFG.model;", 1],
  // phone.js explains what is missing: WebGPU, a model to download, or a model loading
  [`    noteProblem("cannot reach Ollama: " + e.message);`,
   `    if (window.PHONE) return PHONE.notReady(e);\n    noteProblem("cannot reach Ollama: " + e.message);`, 1],
  ["About 2.5 GB, once.", "About ${PHONE.sizeText(WANTED)}, once.", 1],
  ["Check that Ollama is running, then try again.", "Try again. If it happens again, reload the page.", 1],
  // words: phone, not computer; WebLLM in the browser, not Ollama
  ["a patient who lives on your own computer.", "a patient who lives on your own phone.", 1],
  ["All on your own computer.", "All on your own phone.", 1],
  ["Downloads an open source AI model and runs it on your computer.",
   "Downloads an open source AI model and runs it inside the web browser, on the phone&rsquo;s graphics chip.", 1],
  ["Nothing leaves your computer. There is no server.", "Nothing you type leaves your phone.", 1],
  ["checks that Ollama is running with a model ready.", "checks that the model is downloaded and loads it into memory.", 1],
  ["to Ollama. Ollama runs the model.", "to WebLLM. WebLLM runs the model.", 1],
  ["<b>Ollama</b></div>", "<b>WebLLM</b></div>", 1],
  ["<i></i>Ollama</span>", "<i></i>WebLLM</span>", 2],
  [`<tr><td><b>Ollama</b><br><span class="sm">runs the model on your computer</span></td><td>MIT</td></tr>`,
   `<tr><td><b>WebLLM</b><br><span class="sm">runs the model in your browser</span></td><td>Apache 2.0</td></tr>`, 1],
  ["nothing leaves this computer", "nothing leaves this phone", 1],
  ["Delete every saved encounter on this computer?", "Delete every saved encounter on this phone?", 1],
  [`", run offline on this computer"`, `", run offline in the browser on this phone"`, 1],
];

let html = readFileSync(join(ROOT, "app", "index.html"), "utf8");
const bad = [];
for (const [from, to, n] of EDITS) {
  const found = html.split(from).length - 1;
  if (found !== n) { bad.push(`expected ${n}, found ${found}: ${from.slice(0, 80)}`); continue; }
  html = html.split(from).join(to);
}
if (bad.length) {
  console.error("app/index.html changed, so the phone edition cannot be built. Update EDITS in build.mjs:\n  " + bad.join("\n  "));
  process.exit(1);
}
html = html.replace("<!doctype html>", "<!doctype html>\n<!-- Built by docs/phone/build.mjs from app/index.html. Do not edit: change those instead. -->");

const cases = readdirSync(join(ROOT, "app", "cases")).filter(f => /\.txt$/i.test(f)).sort();
const out = new Map([["index.html", html], ["cases/index.json", JSON.stringify(cases) + "\n"]]);
for (const c of [...cases, "LICENSE.md"]) out.set("cases/" + c, readFileSync(join(ROOT, "app", "cases", c), "utf8"));

// The service worker keeps these, so the page opens with no internet. Its cache name changes
// whenever one of them changes, so a phone that is online gets the new version.
const KEEP = ["./", "index.html", "phone.js", "lib/web-llm.js", "manifest.webmanifest",
  "icon-180.png", "icon-192.png", "icon-512.png", "cases/index.json", ...cases.map(c => "cases/" + c)];
const hash = createHash("sha256");
for (const f of KEEP.slice(1)) hash.update(out.has(f) ? out.get(f) : readFileSync(join(HERE, f)));
const VERSION = hash.digest("hex").slice(0, 12);
out.set("sw.js", `// Built by build.mjs. Keeps the phone edition's own files so it opens with no internet.
// The patient model is not here: WebLLM keeps it in the browser's storage by itself.
// Online, every file comes fresh from the network, and the copy here is updated.
// Offline, or after 6 seconds with no answer, the copy here is used.
const CACHE = "vsp-phone-${VERSION}";
const KEEP = ${JSON.stringify(KEEP)};
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(KEEP.map(f => new Request(f, { cache: "reload" })))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("vsp-phone-") && k !== CACHE)
    .map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    // WebLLM and the icons change only with a new version, and WebLLM is 6.6 MB: keep the copy.
    if (req.url.includes("/lib/") || req.url.includes("/icon-")) { const hit = await cache.match(req); if (hit) return hit; }
    try {
      const res = await Promise.race([fetch(req, { cache: "no-store" }),
        new Promise((_, no) => setTimeout(() => no(new Error("slow")), 6000))]);
      if (res.ok) cache.put(req, res.clone());
      return res;
    } catch (err) {
      const hit = await cache.match(req, { ignoreSearch: true });
      if (hit) return hit;
      throw err;
    }
  })());
});
`);

try { new Function(out.get("sw.js")); }      // a syntax error would stop the page working offline
catch (e) { console.error("sw.js does not parse: " + e.message); process.exit(1); }

const stale = [];
for (const [f, text] of out) {
  const p = join(HERE, f);
  const now = existsSync(p) ? readFileSync(p, "utf8") : null;
  if (now === text) continue;
  if (CHECK) { stale.push(f); continue; }
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, text);
}
// a case removed from app/cases leaves the phone edition too
for (const f of readdirSync(join(HERE, "cases"))) {
  if (out.has("cases/" + f)) continue;
  if (CHECK) stale.push("cases/" + f); else rmSync(join(HERE, "cases", f));
}
if (stale.length) {
  console.error("The phone edition is out of date. Run: node docs/phone/build.mjs\n  " + stale.join("\n  "));
  process.exit(1);
}
console.log(CHECK ? "The phone edition is up to date." : `Built the phone edition, ${cases.length} cases, cache ${VERSION}.`);
