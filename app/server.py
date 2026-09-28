#!/usr/bin/env python3
"""Virtual Standardized Patient Simulator, the small web server for Linux.

Started by "Start on Linux.desktop", or from a terminal with:  python3 app/server.py
Uses only the Python that nearly every Linux has. Installs nothing.

  1. Starts Ollama if it is installed but not running.
  2. Serves the app folder on http://127.0.0.1:8756, to this computer only.
  3. Opens the browser there.
  4. Stops by itself when the last browser tab closes, or when Quit is pressed in the page.
     On the way out it unloads the patient model, so Ollama gives back the memory.

It keeps a log, log.txt, in the downloaded folder beside the Start files, or in the temporary
folder as virtual-standardized-patient.log if the folder cannot be written. If it cannot start,
it opens a page in the browser with an error report to email or post on GitHub.
"""
import http.server, json, os, platform, re, shutil, signal, subprocess, sys, tempfile, threading, time
import urllib.parse, urllib.request, webbrowser

ROOT   = os.path.dirname(os.path.abspath(__file__))   # the app folder, served
TOP    = os.path.dirname(ROOT)                        # the folder that was downloaded
PORT   = 8756
URL    = f"http://127.0.0.1:{PORT}/"
OLLAMA = "http://127.0.0.1:11434"
# The patient models. Only these are unloaded on the way out.
KNOWN  = re.compile(r"^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)")

# How long to wait before stopping, in seconds.
FIRST_TAB  = 120   # for the browser to open the first tab
LAST_TAB   = 10    # after the last tab closes, so a reload does not stop it
QUIET_TAB  = 240   # a tab that has not been heard from, e.g. the browser was killed

tabs, lock, state = {}, threading.Lock(), {"seen": False, "quit": False}
# The log goes beside the Start files, where anyone can find it and send it. If the folder
# cannot be written, the temporary folder instead.
# The log is opened once, and never through a link (O_NOFOLLOW): a link could point anywhere,
# and one made later is not followed either, because the open file is kept.
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def open_log(p):
    if os.path.islink(p):
        raise OSError("the log is a link")
    try:                                                    # keep the log small
        if os.path.getsize(p) > 200_000:
            os.replace(p, p + ".old")
    except OSError:
        pass
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT | NOFOLLOW, 0o600)
    return os.fdopen(fd, "a", encoding="utf-8", buffering=1)


LOG, LOGF, log_lock = os.path.join(TOP, "log.txt"), None, threading.Lock()
try:
    LOGF = open_log(LOG)
except OSError:
    LOG = os.path.join(tempfile.gettempdir(), "virtual-standardized-patient.log")
    try:
        if os.path.islink(LOG):
            os.unlink(LOG)
        LOGF = open_log(LOG)
    except OSError:
        LOGF = None


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    try:
        if LOGF:
            with log_lock:
                LOGF.write(line + "\n")
    except (OSError, ValueError):
        pass


def log_tail(n=150):
    try:
        fd = os.open(LOG, os.O_RDONLY | NOFOLLOW)
        with os.fdopen(fd, encoding="utf-8", errors="replace") as f:
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
        # a fresh file each time, never written through an existing file or link
        try:
            os.unlink(out)
        except OSError:
            pass
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
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


class H(http.server.SimpleHTTPRequestHandler):
    timeout = 15                                     # a connection that sends nothing is dropped

    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def send_head(self):
        # Serve only real files inside the app folder: a link that leads outside is not found.
        p = self.translate_path(self.path)
        real, root = os.path.realpath(p), os.path.realpath(ROOT)
        if not (real == root or real.startswith(root + os.sep)):
            self.send_error(404)
            return None
        return super().send_head()

    def do_HEAD(self):
        self.send_error(405)                         # the page never uses HEAD

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
        # Only this computer's own page may use the simulator. Another web site open in the
        # browser must not quit it (Origin), or read its files through a changed name (Host).
        mine = (f"127.0.0.1:{PORT}", f"localhost:{PORT}")
        host, origin = self.headers.get("Host"), self.headers.get("Origin")
        site = self.headers.get("Sec-Fetch-Site")   # the browser says where a request comes from
        if (host and host.lower() not in mine) or (origin and origin.lower() not in tuple("http://" + m for m in mine)) \
                or (site and site.lower() not in ("same-origin", "none")):
            log(f"Refused {method} {path} from {origin or host}")
            self.send_response(403); self.send_header("Content-Length", "10"); self.end_headers()
            self.wfile.write(b"Forbidden\n")
            return True
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
        if path == "/ping":                         # "this is the simulator", for a second start
            return self.reply("virtual-standardized-patient")
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
        self.send_header("X-Frame-Options", "DENY")   # no other site may show it in a frame
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        super().end_headers()

    def log_message(self, fmt, *a):
        if len(a) > 1 and str(a[1]) not in ("200", "304"):   # only what went wrong
            log("%s %s" % (a[1], a[0]))


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        # The standard one looks up this computer's network name, which can take half a
        # minute on a computer with slow or no DNS. The name is not needed here.
        import socketserver
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", PORT


BEFORE = set()                                      # patient models loaded before we started


def main():
    global BEFORE
    try:                                                    # those belong to someone else
        BEFORE = {m.get("name", "") for m in ollama("/api/ps").get("models", [])}
    except Exception:
        pass
    log(f"Starting version {version()} on {platform.platform()}, Python {platform.python_version()}, in {ROOT}")
    try:
        httpd = Server(("127.0.0.1", PORT), H)
    except OSError as e:
        try:                                                # is it this simulator, already running?
            with urllib.request.urlopen(URL + "ping", timeout=3) as r:
                mine = r.read() == b"virtual-standardized-patient"
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
            if KNOWN.match(m) and m not in BEFORE:  # not ours if it was loaded before we started
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
