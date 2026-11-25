"""Preview leve do build React real, com proxy /api. Apenas para laboratório."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.error
import urllib.request


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path("/app/frontend/dist")), **kwargs)

    def proxy(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {}
        for name in ["Authorization", "Content-Type", "Accept"]:
            if name in self.headers:
                headers[name] = self.headers[name]
        request = urllib.request.Request("http://api:8000" + self.path[4:],
                                         data=body, headers=headers, method=self.command)
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as exc:
            response = exc
        raw = response.read()
        self.send_response(response.status)
        self.send_header("Content-Type", response.headers.get("Content-Type", "application/octet-stream"))
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.proxy()
        return super().do_GET()

    def do_POST(self):
        self.proxy()

    def do_DELETE(self):
        self.proxy()


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 5173), Handler).serve_forever()
