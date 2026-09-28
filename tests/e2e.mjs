// End-to-end test of one launcher's server, in a real browser, against tests/fake_ollama.py.
//
//   node tests/e2e.mjs <installed folder> <server command...>
//   e.g. node tests/e2e.mjs /tmp/inst/virtual-standardized-patient-main python3 app/server.py
//
// The folder is an unpacked "Download ZIP". ZIP_FILE is that ZIP, served for the update test.
// PYTHON names the Python to run the fake Ollama with. PW_CHANNEL=chrome uses the installed
// Chrome instead of Playwright's own Chromium.
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { createServer, connect } from "node:net";
import { request as httpRequest } from "node:http";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const [dir, ...cmd] = process.argv.slice(2);
const HERE = dirname(fileURLToPath(import.meta.url));
const URL = "http://127.0.0.1:8756/";
const env = { ...process.env, VSP_NO_BROWSER: "1", VSP_ZIP: "http://127.0.0.1:11434/latest.zip" };
const sleep = ms => new Promise(r => setTimeout(r, ms));
let failed = 0;
function check(ok, what, extra = "") {
  console.log((ok ? "  pass  " : "  FAIL  ") + what + (extra && !ok ? "\n        " + extra : ""));
  if (!ok) failed++;
}

// A plain ZIP (stored, no compression) from [name, text] pairs, for the update tests.
function makeZip(entries) {
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = b => { let c = 0xffffffff; for (const x of b) c = crcTable[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const parts = [], dirs = []; let off = 0;
  for (const [name, text] of entries) {
    const n = Buffer.from(name), d = Buffer.from(text), c = crc(d);
    const h = Buffer.alloc(30); h.writeUInt32LE(0x04034b50, 0); h.writeUInt16LE(20, 4); h.writeUInt32LE(c, 14);
    h.writeUInt32LE(d.length, 18); h.writeUInt32LE(d.length, 22); h.writeUInt16LE(n.length, 26);
    const e = Buffer.alloc(46); e.writeUInt32LE(0x02014b50, 0); e.writeUInt16LE(20, 4); e.writeUInt16LE(20, 6);
    e.writeUInt32LE(c, 16); e.writeUInt32LE(d.length, 20); e.writeUInt32LE(d.length, 24); e.writeUInt16LE(n.length, 28);
    e.writeUInt32LE(off, 42);
    parts.push(h, n, d); dirs.push(e, n); off += 30 + n.length + d.length;
  }
  const cd = Buffer.concat(dirs), end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(cd.length, 12); end.writeUInt32LE(off, 16);
  return Buffer.concat([...parts, cd, end]);
}

function startServer() {
  const p = spawn(cmd[0], cmd.slice(1), { cwd: dir, env, stdio: ["ignore", "pipe", "pipe"] });
  p.out = "";
  p.stdout.on("data", d => p.out += d); p.stderr.on("data", d => p.out += d);
  p.done = new Promise(r => p.on("exit", code => { p.code = code; r(code); }));
  return p;
}
async function waitFor(fn, ms, step = 250) {
  for (const end = Date.now() + ms; Date.now() < end; await sleep(step)) { try { if (await fn()) return true; } catch {} }
  return false;
}
const get = async (path, opts) => { const r = await fetch(URL + path.replace(/^\//, ""), opts); return { status: r.status, text: await r.text() }; };
const up = () => get("update").then(r => r.text === "can", () => false);
const exited = (p, ms) => Promise.race([p.done.then(() => true), sleep(ms).then(() => false)]);

let fake;
const startFake = () => { fake = spawn(process.env.PYTHON || "python3", [join(HERE, "fake_ollama.py")], { env, stdio: "inherit" }); };
const calls = async () => JSON.parse((await (await fetch("http://127.0.0.1:11434/_calls")).text()));

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || undefined });
try {
  console.log("1. First start, Ollama not running");
  let srv = startServer();
  check(await waitFor(up, 30000), "the server comes up", srv.out);
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", e => pageErrors.push(e.message));
  await page.goto(URL);
  check(await waitFor(async () => /Ollama is not running/.test(await page.textContent("#setupText")), 10000),
        "the page says Ollama is not running");
  await page.click("#reportLink");
  check(await waitFor(async () => /launcher log/.test(await page.inputValue("#reportText")), 8000),
        "Report a problem builds a report");
  const report = await page.inputValue("#reportText");
  check(/Version: \d/.test(report) && /Starting version/.test(report), "the report holds the version and the launcher log", report);
  await page.click("#repClose");

  console.log("2. Ollama starts; the model downloads in the page");
  startFake();
  check(await waitFor(async () => /\d+% of 2\.5 GB/.test(await page.textContent("#setupText")), 20000), "the download shows its progress");
  check(await waitFor(async () => (await page.textContent("#status")).startsWith("ready"), 20000), "then the page says ready");

  console.log("3. The server itself");
  const cases = JSON.parse((await get("cases/")).text);
  check(cases.length === 8, "lists the eight cases", String(cases));
  for (const p of ["../README.md", "%2e%2e/README.md", "cases/../../LICENSE", "nope.html"])
    check((await get(p)).status === 404, "refuses " + p);
  const idle = connect(8756, "127.0.0.1");          // a browser's spare connection, which sends nothing
  await sleep(300);
  let t = Date.now(); await get("cases/");
  check(Date.now() - t < 2000, "a silent connection does not hold up others", (Date.now() - t) + " ms");
  idle.destroy();
  check(/Starting version/.test((await get("log")).text), "GET /log returns the log");
  // another web site open in the browser must not control or read the simulator
  const evil = await fetch(URL + "quit", { method: "POST", headers: { Origin: "https://evil.example" } });
  check(evil.status === 403 && await up(), "refuses Quit from another web site", "status " + evil.status);
  const upd = await fetch(URL + "update", { method: "POST", headers: { Origin: "https://evil.example" } });
  check(upd.status === 403, "refuses Update from another web site", "status " + upd.status);
  // fetch() ignores a Host header, so send this one with the plain http module
  const rebind = await new Promise(res => {
    const r = httpRequest({ host: "127.0.0.1", port: 8756, path: "/log", headers: { Host: "evil.example:8756" } },
                          x => { x.resume(); res(x.statusCode); });
    r.on("error", () => res(0)); r.end();
  });
  check(rebind === 403, "refuses a request addressed to another name", "status " + rebind);

  console.log("4. Reload keeps it running; leaving the page stops it");
  await page.reload(); await sleep(12000);
  check(await up(), "still running 12 s after a reload");
  await page.goto("about:blank");
  t = Date.now();
  check(await exited(srv, 25000), "stops after the tab is gone", srv.out);
  console.log("        stopped after " + ((Date.now() - t) / 1000).toFixed(1) + " s, exit code " + srv.code);
  check((await calls()).some(([p, b]) => p === "/api/generate" && b.keep_alive === 0), "unloads the model on the way out");

  console.log("5. A second start while it runs");
  srv = startServer();
  check(await waitFor(up, 30000), "the server comes up again", srv.out);
  const second = startServer();
  check(await exited(second, 15000) && second.code === 0, "a second copy just opens the page and exits", second.out);

  console.log("6. Update");
  // An unsafe or incomplete download must be refused, and nothing written outside the folder.
  // The fake Ollama reads ZIP_FILE on every request, so swap in a crafted ZIP for a moment.
  if (process.env.ZIP_FILE) {
    const real = readFileSync(process.env.ZIP_FILE);
    const base = ["app/index.html", "app/server.pl", "app/server.py", "app/server.ps1", "app/problem.html",
      "Start on Windows.bat", "Start on Linux.desktop", "Start on Mac.app/Contents/MacOS/start", "app/cases/a.txt"]
      .map(n => ["v/" + n, "x"]);
    const outside = join(dirname(dir), "vsp-escape.txt");
    rmSync(outside, { force: true });
    writeFileSync(process.env.ZIP_FILE, makeZip([...base, ["v/../../vsp-escape.txt", "escaped"]]));
    const bad = JSON.parse((await get("update", { method: "POST" })).text);
    check(bad.ok === false && !existsSync(outside), "refuses a download with a ../ path", JSON.stringify(bad));
    writeFileSync(process.env.ZIP_FILE, makeZip(base.filter(([n]) => !n.endsWith("server.ps1"))));
    const part = JSON.parse((await get("update", { method: "POST" })).text);
    check(part.ok === false, "refuses a download that lacks a program file", JSON.stringify(part));
    writeFileSync(process.env.ZIP_FILE, real);
  }
  const graham = join(dir, "app", "cases", "graham.txt"), original = readFileSync(graham, "utf8");
  writeFileSync(graham, "changed\n");
  const u = JSON.parse((await get("update", { method: "POST" })).text);
  check(u.ok === true, "POST /update reports ok", JSON.stringify(u));
  check(readFileSync(graham, "utf8").replace(/\r\n/g, "\n") === original.replace(/\r\n/g, "\n"), "the files are replaced from the ZIP");

  console.log("7. Quit");
  const p2 = await browser.newPage();
  await p2.goto(URL); await sleep(1000);
  await p2.click("#stopApp");
  check(await exited(srv, 8000), "Quit stops it", srv.out);
  check(await waitFor(async () => /has stopped/.test(await p2.textContent("h1")), 5000), "the page says it has stopped");
  await p2.close();

  console.log("8. Port taken by another program");
  const out = join(tmpdir(), "virtual-standardized-patient-problem.html");
  rmSync(out, { force: true });
  const other = createServer(s => s.end("HTTP/1.0 200 OK\r\n\r\nnot the simulator")).listen(8756, "127.0.0.1");
  await sleep(300);
  srv = startServer();
  check(await exited(srv, 20000) && srv.code === 3, "it stops with a problem", `code ${srv.code}\n${srv.out}`);
  check(existsSync(out) && /Another program is using port 8756/.test(readFileSync(out, "utf8")),
        "and writes the problem page with the report", out);
  other.close();
  if (existsSync(out)) {
    const pp = await browser.newPage();
    await pp.goto("file://" + (out.startsWith("/") ? "" : "/") + out.replace(/\\/g, "/"));
    check(/Another program/.test(await pp.textContent("#what")), "the problem page shows what went wrong");
    check(/launcher log/.test(await pp.inputValue("#report")), "and the report, with the log");
    await pp.close();
  }

  check(pageErrors.length === 0, "no errors in the page", pageErrors.join("\n"));
} finally {
  await browser.close();
  if (fake) fake.kill();
}
console.log(failed ? `\n${failed} FAILED` : "\nAll passed");
process.exit(failed ? 1 : 0);
