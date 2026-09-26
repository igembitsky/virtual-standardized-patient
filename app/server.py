#!/usr/bin/env python3
"""Virtual Standardized Patient Simulator, the small web server for Linux.

Started by "Start on Linux.desktop", or from a terminal with:  python3 app/server.py
Uses only the Python that nearly every Linux has. Installs nothing.

  1. Starts Ollama if it is installed but not running.
  2. Serves the app folder on http://127.0.0.1:8756, to this computer only.
  3. Opens the browser there.
  4. Stops by itself when the last browser tab closes, or when Quit is pressed in the page.
     On the way out it unloads the patient model, so Ollama gives back the memory.

It keeps a log in the temporary folder, virtual-standardized-patient.log. If it cannot start,
it opens a page in the browser with an error report to email or post on GitHub.
"""
import http.server, json, os, platform, re, shutil, signal, subprocess, sys, tempfile, threading, time
import urllib.parse, urllib.request, webbrowser, zipfile

ROOT   = os.path.dirname(os.path.abspath(__file__))   # the app folder, served
TOP    = os.path.dirname(ROOT)                        # the folder that was downloaded
PORT   = 8756
URL    = f"http://127.0.0.1:{PORT}/"
OLLAMA = "http://127.0.0.1:11434"
# Where "Update" in the page gets the new files. VSP_ZIP overrides it for testing.
ZIP    = os.environ.get("VSP_ZIP") or "https://github.com/igembitsky/virtual-standardized-patient/archive/refs/heads/main.zip"
# The patient models. Only these are unloaded on the way out.
KNOWN  = re.compile(r"^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)")

# How long to wait before stopping, in seconds.
FIRST_TAB  = 120   # for the browser to open the first tab
LAST_TAB   = 10    # after the last tab closes, so a reload does not stop it
QUIET_TAB  = 240   # a tab that has not been heard from, e.g. the browser was killed

tabs, lock, state = {}, threading.Lock(), {"seen": False, "quit": False}
LOG = os.path.join(tempfile.gettempdir(), "virtual-standardized-patient.log")


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def log_tail(n=150):
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return "(no log)\n"


def version():
    try:
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            return re.search(r'version: "([^"]+)"', f.read()).group(1)
    except Exception:
        return "unknown"


def open_browser(url):
    if not os.environ.get("VSP_NO_BROWSER"):              # tests set this
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()


def fail(what):
    """It cannot start. Log why, and open a page with a report to send."""
    log("PROBLEM: " + what)
    report = "\n".join([
        "Virtual Standardized Patient Simulator: problem report",
        "Version: " + version(),
        "When: " + time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "Computer: " + platform.platform() + ", Python " + platform.python_version(),
        "Folder: " + TOP,
        "What happened: " + what,
        "", "--- launcher log, last lines ---", log_tail(80)])
    try:
        with open(os.path.join(ROOT, "problem.html"), encoding="utf-8") as f:
            page = f.read()
        data = json.dumps({"what": what, "report": report}).replace("</", "<\\/")
        out = os.path.join(tempfile.gettempdir(), "virtual-standardized-patient-problem.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(page.replace("/*REPORT*/null/*END*/", data))
        open_browser("file://" + out)
    except Exception as e:
        log("could not open the problem page: " + str(e))
    time.sleep(2)                                           # let the browser start
    sys.exit(3)


def ollama(path, body=None, timeout=3):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(OLLAMA + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def do_update():
    """Download the ZIP, unpack it in a temporary folder, check it is complete, then copy it
    over this folder. The old files stay until the whole ZIP has arrived and been checked."""
    tmp = tempfile.mkdtemp(prefix="vsp-update-")
    try:
        zpath = os.path.join(tmp, "latest.zip")
        with urllib.request.urlopen(ZIP, timeout=60) as r, open(zpath, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(zpath) as z:
            for info in z.infolist():
                z.extract(info, tmp)
                mode = info.external_attr >> 16          # keep the launchers executable
                if mode & 0o111:
                    os.chmod(os.path.join(tmp, info.filename), mode & 0o777)
        dirs = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
        src = os.path.join(tmp, dirs[0]) if dirs else None
        if not src or not os.path.isfile(os.path.join(src, "app", "index.html")) \
                or not os.path.isdir(os.path.join(src, "app", "cases")):
            return {"ok": False, "error": "the download was incomplete"}
        shutil.copytree(src, TOP, dirs_exist_ok=True)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": re.sub(r'["\\]', "", str(e))}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def reply(self, body, kind="text/plain"):
        body = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def tab(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        t = (q.get("tab") or [""])[0]
        return t if re.fullmatch(r"[\w-]{1,40}", t) else None

    def route(self, method):
        path = urllib.parse.urlparse(self.path).path
        if path == "/alive":                        # the page says it is still open
            with lock:
                t = self.tab()
                if t: tabs[t] = time.time()
                state["seen"] = True
            return self.reply("ok")
        if path == "/bye":                          # the page is closing
            with lock:
                tabs.pop(self.tab(), None)
            return self.reply("ok")
        if path == "/quit" and method == "POST":    # Quit in the page
            done = self.reply("ok")
            state["quit"] = True
            return done
        if path == "/update":                       # GET says it can; POST does it
            if method == "POST":
                r = do_update()
                log("Update: " + json.dumps(r))
                return self.reply(json.dumps(r), "application/json")
            return self.reply("can")
        if path == "/log":                          # for the problem report in the page
            return self.reply(log_tail())
        if path in ("/cases", "/cases/"):           # a list of the case files, so new ones just appear
            try:
                names = sorted(f for f in os.listdir(os.path.join(ROOT, "cases")) if f.lower().endswith(".txt"))
            except OSError:
                names = []
            return self.reply(json.dumps(names), "application/json")
        return False

    def do_GET(self):
        if not self.route("GET"):
            super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if 0 < n < 65536:
            self.rfile.read(n)                       # read what was sent before answering
        if not self.route("POST"):
            self.send_error(404)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *a):
        if len(a) > 1 and str(a[1]) not in ("200", "304"):   # only what went wrong
            log("%s %s" % (a[1], a[0]))


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    try:                                                    # keep the log small
        if os.path.getsize(LOG) > 200_000:
            os.replace(LOG, LOG + ".old")
    except OSError:
        pass
    log(f"Starting version {version()} on {platform.platform()}, Python {platform.python_version()}, in {ROOT}")
    try:
        httpd = Server(("127.0.0.1", PORT), H)
    except OSError as e:
        try:                                                # is it this simulator, already running?
            with urllib.request.urlopen(URL + "update", timeout=3) as r:
                mine = r.read() == b"can"
        except Exception:
            mine = False
        if mine:
            log("It is already running. Opening it.")
            open_browser(URL)
            return
        fail(f"Another program is using port {PORT}, so the simulator cannot start. ({e})")

    # Start Ollama if it is installed but not running. The page reports anything else.
    started_ollama = None
    try:
        ollama("/api/tags")
    except Exception:
        if shutil.which("ollama"):
            log("Ollama is not running. Starting it.")
            started_ollama = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            log("Ollama is not running, and the ollama command was not found.")

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    log(f"Running on {URL}. It stops by itself when you close the browser tab, or press Quit in the page.")
    open_browser(URL)

    for s in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, lambda *a: state.update(quit=True))

    begun = tick = time.time()
    empty_since = None
    why = "Quit was pressed"
    try:
        while not state["quit"]:
            time.sleep(1)
            now = time.time()
            with lock:
                if now - tick > 30:                  # the computer slept; that is not a closed tab
                    for t in tabs: tabs[t] = now
                    begun, empty_since = now, None
                tick = now
                for t in [t for t, seen in tabs.items() if now - seen > QUIET_TAB]:
                    del tabs[t]
                if tabs:
                    empty_since = None
                elif not state["seen"]:
                    if now - begun > FIRST_TAB:
                        why = "no browser tab opened in 2 minutes"; break
                else:
                    empty_since = empty_since or now
                    if now - empty_since >= LAST_TAB:
                        why = "the last tab closed"; break
    except KeyboardInterrupt:
        why = "Control-C"

    log("Stopping: " + why)
    httpd.shutdown()
    # Give back the memory the patient model holds. Ollama itself is left as it was found.
    try:
        for m in {m.get("name", "") for m in ollama("/api/ps").get("models", [])}:
            if KNOWN.match(m):
                ollama("/api/generate", {"model": m, "keep_alive": 0}, timeout=10)
                log("Unloaded " + m)
    except Exception:
        pass
    if started_ollama:
        started_ollama.terminate()
    log("Stopped.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        import traceback
        log(traceback.format_exc())
        fail(f"The launcher stopped with an error: {type(e).__name__}: {e}")
