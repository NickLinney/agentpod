from __future__ import annotations

import contextlib
import http.client
import io
import tempfile
import threading
import unittest
import urllib.error
from email.message import Message
from functools import partial
from pathlib import Path
from unittest import mock

import server


class FakeResponse:
    def __init__(
        self,
        status: int = 200,
        body: bytes = b'{"ok":true}',
        content_type: str = "application/json",
    ) -> None:
        self._status = status
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self) -> int:
        return self._status

    def read(self, amount: int = -1) -> bytes:
        return self._body if amount < 0 else self._body[:amount]


class FrontendServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.dist = root / "dist"
        self.dist.mkdir()
        (self.dist / "index.html").write_text("agentpod-index", encoding="utf-8")
        (self.dist / "asset.js").write_text("agentpod-asset", encoding="utf-8")
        (root / "secret.txt").write_text("outside-dist-secret", encoding="utf-8")

        handler = partial(server.FrontendRequestHandler, directory=str(self.dist))
        self.httpd = server.QuietThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def request(self, method: str, path: str, body=None, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.httpd.server_address[1],
            timeout=2,
        )
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_static_root_and_asset_are_served_without_server_header(self) -> None:
        status, headers, body = self.request("GET", "/")
        self.assertEqual(200, status)
        self.assertEqual(b"agentpod-index", body)
        self.assertNotIn("Server", headers)

        status, _, body = self.request("GET", "/asset.js")
        self.assertEqual(200, status)
        self.assertEqual(b"agentpod-asset", body)

    def test_static_path_traversal_cannot_escape_dist(self) -> None:
        for path in ("/../secret.txt", "/%2e%2e/secret.txt"):
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertEqual(404, status)
                self.assertEqual(b'{"error":"not_found"}', body)
                self.assertNotIn(b"outside-dist-secret", body)

    def test_allowed_get_routes_use_exact_upstream_and_timeout(self) -> None:
        for local_path, upstream_path in (
            ("/api/health", "/health"),
            ("/api/status", "/status"),
        ):
            with self.subTest(path=local_path):
                with mock.patch.object(
                    server.urllib.request,
                    "urlopen",
                    return_value=FakeResponse(),
                ) as urlopen:
                    status, headers, body = self.request(
                        "GET",
                        local_path,
                        headers={"Authorization": "secret", "Cookie": "secret"},
                    )

                self.assertEqual(200, status)
                self.assertEqual(b'{"ok":true}', body)
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                request = urlopen.call_args.args[0]
                self.assertEqual(
                    f"http://agentpod:8000{upstream_path}",
                    request.full_url,
                )
                self.assertEqual("GET", request.get_method())
                self.assertIsNone(request.data)
                self.assertNotIn("Authorization", request.headers)
                self.assertNotIn("Cookie", request.headers)
                self.assertEqual(125, urlopen.call_args.kwargs["timeout"])

    def test_allowed_chat_post_forwards_only_body_and_json_headers(self) -> None:
        payload = b'{"message":"hello"}'
        with mock.patch.object(
            server.urllib.request,
            "urlopen",
            return_value=FakeResponse(200, b'{"response":"world"}'),
        ) as urlopen:
            status, headers, body = self.request(
                "POST",
                "/api/chat",
                body=payload,
                headers={
                    "Content-Type": "text/plain",
                    "Authorization": "secret",
                    "X-Trace": "secret",
                },
            )

        self.assertEqual(200, status)
        self.assertEqual("application/json", headers["Content-Type"])
        self.assertEqual(b'{"response":"world"}', body)
        request = urlopen.call_args.args[0]
        self.assertEqual("http://agentpod:8000/chat", request.full_url)
        self.assertEqual("POST", request.get_method())
        self.assertEqual(payload, request.data)
        self.assertEqual("application/json", request.headers["Content-type"])
        self.assertNotIn("Authorization", request.headers)
        self.assertNotIn("X-trace", request.headers)
        self.assertEqual(125, urlopen.call_args.kwargs["timeout"])

    def test_closed_api_rejects_unknown_paths_queries_and_absolute_targets(self) -> None:
        paths = (
            "/api",
            "/api/config",
            "/api/health/",
            "/api/health?detail=true",
            "/api/%2e%2e/health",
            "http://example.invalid/api/health",
        )
        with mock.patch.object(server.urllib.request, "urlopen") as urlopen:
            for path in paths:
                with self.subTest(path=path):
                    status, _, body = self.request("GET", path)
                    self.assertEqual(404, status)
                    self.assertEqual(b'{"error":"not_found"}', body)
        urlopen.assert_not_called()

    def test_known_api_paths_reject_unapproved_methods(self) -> None:
        cases = (
            ("GET", "/api/chat"),
            ("POST", "/api/health"),
            ("POST", "/api/status"),
            ("PUT", "/api/health"),
            ("PATCH", "/api/chat"),
            ("DELETE", "/api/status"),
            ("OPTIONS", "/api/chat"),
            ("TRACE", "/api/health"),
        )
        with mock.patch.object(server.urllib.request, "urlopen") as urlopen:
            for method, path in cases:
                with self.subTest(method=method, path=path):
                    status, _, body = self.request(method, path)
                    self.assertEqual(405, status)
                    self.assertEqual(b'{"error":"method_not_allowed"}', body)
        urlopen.assert_not_called()

    def test_upstream_http_status_and_safe_json_body_are_preserved(self) -> None:
        headers = Message()
        headers["Content-Type"] = "application/json"
        error = urllib.error.HTTPError(
            "http://agentpod:8000/status",
            503,
            "upstream marker must not be rendered",
            headers,
            io.BytesIO(b'{"error":"configuration_incomplete"}'),
        )
        with mock.patch.object(
            server.urllib.request,
            "urlopen",
            side_effect=error,
        ):
            status, _, body = self.request("GET", "/api/status")

        self.assertEqual(503, status)
        self.assertEqual(b'{"error":"configuration_incomplete"}', body)
        self.assertNotIn(b"upstream marker", body)

    def test_upstream_failures_return_fixed_502_without_leakage_or_logs(self) -> None:
        marker = "private-upstream-detail"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            server.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError(marker),
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status, headers, body = self.request("GET", "/api/health")

        self.assertEqual(502, status)
        self.assertEqual(b'{"error":"bad_gateway"}', body)
        self.assertNotIn(marker.encode(), body)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_non_json_or_oversized_upstream_response_returns_safe_502(self) -> None:
        responses = (
            FakeResponse(content_type="text/plain", body=b"private-detail"),
            FakeResponse(body=b"x" * (server.MAX_RESPONSE_BODY_BYTES + 1)),
        )
        for response in responses:
            with self.subTest(content_type=response.headers["Content-Type"]):
                with mock.patch.object(
                    server.urllib.request,
                    "urlopen",
                    return_value=response,
                ):
                    status, _, body = self.request("GET", "/api/health")
                self.assertEqual(502, status)
                self.assertEqual(b'{"error":"bad_gateway"}', body)
                self.assertNotIn(b"private-detail", body)

    def test_invalid_or_oversized_request_length_is_rejected_locally(self) -> None:
        with mock.patch.object(server.urllib.request, "urlopen") as urlopen:
            status, _, body = self.request(
                "POST",
                "/api/chat",
                headers={"Content-Length": "not-a-number"},
            )
            self.assertEqual(400, status)
            self.assertEqual(b'{"error":"bad_request"}', body)

            status, _, body = self.request(
                "POST",
                "/api/chat",
                headers={"Content-Length": str(server.MAX_REQUEST_BODY_BYTES + 1)},
            )
            self.assertEqual(413, status)
            self.assertEqual(b'{"error":"request_too_large"}', body)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
