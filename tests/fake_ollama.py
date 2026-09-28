"""A stand-in for Ollama, for the launcher tests. No models at first; a pull that streams
progress; ps, unload, chat.
GET /_calls lists every POST it received, so a test can check the model was unloaded."""
import http.server, json, os, sys, time

state = {"models": [], "loaded": set(), "calls": []}


class H(http.server.BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def send(self, body, kind="application/json"):
        body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(200); self.cors()
        self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags": return self.send({"models": [{"name": m} for m in state["models"]]})
        if self.path == "/api/ps": return self.send({"models": [{"name": m, "model": m} for m in state["loaded"]]})
        if self.path == "/api/version": return self.send({"version": "0.0.0-fake"})
        if self.path == "/_calls": return self.send(state["calls"])
        self.send_response(404); self.end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        state["calls"].append([self.path, body])
        if self.path == "/api/pull":
            self.send_response(200); self.cors()
            self.send_header("Content-Type", "application/x-ndjson"); self.end_headers()
            total = 2_500_000_000
            for i in range(11):
                self.wfile.write((json.dumps({"status": "pulling", "total": total, "completed": total * i // 10}) + "\n").encode())
                self.wfile.flush(); time.sleep(0.4)
            state["models"].append(body["model"]); state["loaded"].add(body["model"])
            self.wfile.write(b'{"status":"success"}\n'); return
        if self.path == "/api/chat":
            state["loaded"].add(body["model"])
            return self.send((json.dumps({"message": {"content": "It hurts here."}, "done": False}) + "\n"
                              + json.dumps({"done": True}) + "\n").encode(), "application/x-ndjson")
        if self.path == "/api/generate":
            if body.get("keep_alive") == 0: state["loaded"].discard(body["model"])
            return self.send({"done": True})
        self.send_response(404); self.end_headers()

    def log_message(self, *a):
        pass


class Server(http.server.ThreadingHTTPServer):
    def server_bind(self):                   # skip the slow network name lookup (macOS)
        import socketserver
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", 11434


Server(("127.0.0.1", 11434), H).serve_forever()
