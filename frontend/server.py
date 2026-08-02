"""Dependency-free static server and closed same-origin API proxy."""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


LISTEN_ADDRESS = "0.0.0.0"
LISTEN_PORT = 3000
PROXY_TIMEOUT_SECONDS = 125
MAX_REQUEST_BODY_BYTES = 1_048_576
MAX_RESPONSE_BODY_BYTES = 2_097_152
UPSTREAM_BASE_URL = "http://agentpod:8000"
DIST_DIRECTORY = Path(__file__).resolve().parent / "dist"

_ROUTES = {
    ("GET", "/api/health"): "/health",
    ("GET", "/api/status"): "/status",
    ("POST", "/api/chat"): "/chat",
}
_API_PATHS = frozenset(path for _, path in _ROUTES)
_ERROR_BODIES = {
    400: b'{"error":"bad_request"}',
    404: b'{"error":"not_found"}',
    405: b'{"error":"method_not_allowed"}',
    413: b'{"error":"request_too_large"}',
    502: b'{"error":"bad_gateway"}',
}


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded server that does not print exception details."""

    daemon_threads = True

    def handle_error(self, request, client_address):  # noqa: ARG002
        return


class FrontendRequestHandler(SimpleHTTPRequestHandler):
    """Serve the built application and proxy only the approved API routes."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(
            *args,
            directory=str(DIST_DIRECTORY) if directory is None else directory,
            **kwargs,
        )

    def __getattr__(self, name: str):
        if name.startswith("do_"):
            return lambda: self._handle_unsupported_method(self.command)
        raise AttributeError(name)

    def log_message(self, format, *args):  # noqa: A002, ARG002
        return

    def send_response(self, code, message=None):
        self.log_request(code)
        self.send_response_only(code, message)
        self.send_header("Date", self.date_time_string())

    def send_error(self, code, message=None, explain=None):  # noqa: ARG002
        self._send_fixed_error(code if code in _ERROR_BODIES else 404)

    def do_GET(self):
        if not self._handle_api_request("GET"):
            super().do_GET()

    def do_HEAD(self):
        if not self._handle_api_request("HEAD"):
            super().do_HEAD()

    def do_POST(self):
        if not self._handle_api_request("POST"):
            self._send_fixed_error(405)

    def do_PUT(self):
        self._handle_unsupported_method("PUT")

    def do_PATCH(self):
        self._handle_unsupported_method("PATCH")

    def do_DELETE(self):
        self._handle_unsupported_method("DELETE")

    def do_OPTIONS(self):
        self._handle_unsupported_method("OPTIONS")

    def _handle_unsupported_method(self, method: str) -> None:
        if not self._handle_api_request(method):
            self._send_fixed_error(405)

    def _handle_api_request(self, method: str) -> bool:
        target = urlsplit(self.path)
        path = target.path
        is_api_path = path == "/api" or path.startswith("/api/")
        if not is_api_path:
            return False

        if target.scheme or target.netloc or target.query or target.fragment:
            self._send_fixed_error(404)
            return True

        if path not in _API_PATHS:
            self._send_fixed_error(404)
            return True

        upstream_path = _ROUTES.get((method, path))
        if upstream_path is None:
            self._send_fixed_error(405)
            return True

        body = None
        if method == "POST":
            body = self._read_request_body()
            if body is None:
                return True

        self._proxy(method, upstream_path, body)
        return True

    def _read_request_body(self) -> bytes | None:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return b""
        try:
            length = int(raw_length, 10)
        except ValueError:
            self._send_fixed_error(400)
            return None
        if length < 0:
            self._send_fixed_error(400)
            return None
        if length > MAX_REQUEST_BODY_BYTES:
            self._send_fixed_error(413)
            return None
        return self.rfile.read(length)

    def _proxy(self, method: str, upstream_path: str, body: bytes | None) -> None:
        headers = {"Accept": "application/json"}
        if method == "POST":
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{UPSTREAM_BASE_URL}{upstream_path}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=PROXY_TIMEOUT_SECONDS,
            ) as response:
                self._relay_upstream_response(response)
        except urllib.error.HTTPError as error:
            try:
                self._relay_upstream_response(error)
            finally:
                error.close()
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            http.client.HTTPException,
        ):
            self._send_fixed_error(502)

    def _relay_upstream_response(self, response) -> None:
        content_type = response.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            self._send_fixed_error(502)
            return

        body = response.read(MAX_RESPONSE_BODY_BYTES + 1)
        if len(body) > MAX_RESPONSE_BODY_BYTES:
            self._send_fixed_error(502)
            return

        status = response.getcode()
        if not isinstance(status, int) or not 100 <= status <= 599:
            self._send_fixed_error(502)
            return
        self._send_body(status, body, "application/json")

    def _send_fixed_error(self, status: int) -> None:
        self._send_body(status, _ERROR_BODIES[status], "application/json")

    def _send_body(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def main() -> None:
    server = QuietThreadingHTTPServer(
        (LISTEN_ADDRESS, LISTEN_PORT),
        FrontendRequestHandler,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
