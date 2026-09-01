#!/bin/sh
# Virtual Standardized Patient Simulator, Linux launcher.
# Run:  ./start-linux.sh      (or double-click start-linux.desktop)
# It does three things, in order, with the python3 that nearly every Linux has:
#   1. Makes sure Ollama is running, and downloads the patient model if it is missing.
#   2. Serves this folder on http://127.0.0.1:8756, to this computer only.
#   3. Opens your browser there.
# Nothing is installed. Press Control-C, or close this window, to stop.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Install it, or use any other static web server"
  echo "to serve this folder, then open http://127.0.0.1:8756/"
  exit 1
fi
exec python3 - "$@" <<'PY'
import http.server, socketserver, os, json, re, shutil, subprocess, sys, threading, time
import urllib.request, urllib.parse, webbrowser

ROOT   = os.getcwd()
PORT   = 8756
OLLAMA = "http://127.0.0.1:11434"
MODEL  = "qwen3:4b-instruct"
# Any one of these is enough. The page picks the first it recognises.
KNOWN  = re.compile(r"^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)")

def tags():
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3) as r:
            return json.load(r)
    except Exception:
        return None

def have_model(t):
    return bool(t) and any(KNOWN.match(m.get("name", "")) for m in t.get("models", []))

print("Virtual Standardized Patient Simulator\n")

# 1. Ollama
t = tags()
if not t:
    if shutil.which("ollama"):
        print("Ollama is not running. Starting it ...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(40):
            time.sleep(1)
            t = tags()
            if t: break
    else:
        print("\n  Ollama is not installed. Get it from https://ollama.com/download")
        print("  Install it, then run this again.\n")

# 2. The model, downloaded once
if have_model(t):
    print("Ollama is running and the patient model is ready.")
elif t:
    print(f"Downloading the patient model, {MODEL}. About 2.5 GB, once.")
    print("Leave this window open. It can take a while.")
    try:
        req = urllib.request.Request(OLLAMA + "/api/pull",
                                     data=json.dumps({"name": MODEL}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            for line in r:
                try: j = json.loads(line)
                except ValueError: continue
                if j.get("error"):
                    print("\n  Problem:", j["error"]); break
                tot, done = j.get("total"), j.get("completed")
                if tot and done is not None and tot > 100e6:
                    print(f"\r  {done * 100 // tot:3d}% of {tot / 1e9:.1f} GB", end="", flush=True)
                if j.get("status") == "success":
                    print("\r  Download complete.        ")
    except Exception as e:
        print("\n  The download did not finish:", e)
    if not have_model(tags()):
        print("\n  The model is still missing. Check your internet connection and run this again,")
        print(f"  or open a terminal and run:  ollama pull {MODEL}\n")

# 3. Serve, and open the browser
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/cases", "/cases/"):
            try:
                names = sorted(f for f in os.listdir(os.path.join(ROOT, "cases"))
                               if f.lower().endswith(".txt"))
            except OSError:
                names = []
            body = json.dumps(names).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def log_message(self, *a):
        pass

print(f"\nStarting on http://127.0.0.1:{PORT} ...")
socketserver.TCPServer.allow_reuse_address = True
try:
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), H)
except OSError:
    print(f"Port {PORT} is busy. The simulator is probably already running. Opening it ...")
    webbrowser.open(f"http://127.0.0.1:{PORT}/")
    sys.exit(1)
print(f"Running. Open http://127.0.0.1:{PORT}/")
print("Press Control-C, or close this window, to stop.")
threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/")).start()
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
PY
