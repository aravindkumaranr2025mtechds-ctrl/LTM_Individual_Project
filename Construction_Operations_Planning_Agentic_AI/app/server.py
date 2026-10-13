"""Dependency-free local HTTP adapter. The planning core is shared with FastAPI."""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from .service import ApplicationService, ROOT, allowed_request


def make_server(port=8765, db_path=None):
    service = ApplicationService(db_path)
    public = (ROOT / "frontend" / "dist").resolve()

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, data, content_type="application/json; charset=utf-8"):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not allowed_request(self.headers.get("Host"), self.headers.get("Origin")):
                return self.send(403, {"error": "Local same-origin requests only."})
            path = unquote(urlsplit(self.path).path)
            if path.startswith("/api/"):
                status, result = service.dispatch("GET", path)
                return self.send(status, result)
            target = (public / (path.lstrip("/") or "index.html")).resolve()
            if not target.is_relative_to(public) or not target.is_file():
                return self.send(404, {"error": "File not found."})
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".js":
                mime = "text/javascript"
            return self.send(200, target.read_bytes(), mime)

        def do_POST(self):
            if not allowed_request(self.headers.get("Host"), self.headers.get("Origin")):
                return self.send(403, {"error": "Local same-origin requests only."})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2_000_000:
                    return self.send(413, {"error": "JSON request must be between 1 byte and 2 MB."})
                if "application/json" not in self.headers.get("Content-Type", ""):
                    return self.send(415, {"error": "Use application/json."})
                body = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeError):
                return self.send(400, {"error": "Invalid JSON request."})
            try:
                status, result = service.dispatch("POST", self.path, body)
                self.send(status, result)
            except Exception:
                import traceback
                traceback.print_exc()
                self.send(500, {"error": "Server error. Check the terminal for details."})

        def log_message(self, fmt, *args):
            print("[BuildPlan] " + fmt % args)

    class Server(ThreadingHTTPServer):
        daemon_threads = True

    return Server(("127.0.0.1", port), Handler)
