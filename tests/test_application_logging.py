import asyncio
import io
import json
import re
import unittest
from types import SimpleNamespace

from src.application_logging import (
    StructuredLoggingMiddleware,
    configure_application_logging,
    log_application_shutdown,
    log_application_startup,
    log_http_error,
    log_http_request,
)


TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)


class ApplicationLoggingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        configure_application_logging(self.stdout, self.stderr)

    def tearDown(self) -> None:
        configure_application_logging()

    def test_lifecycle_events_have_exact_schema_on_stdout(self) -> None:
        log_application_startup()
        log_application_shutdown()

        events = self._events(self.stdout)
        self.assertEqual(
            [(event["level"], event["event"]) for event in events],
            [("INFO", "application.startup"), ("INFO", "application.shutdown")],
        )
        for event in events:
            self.assertEqual(set(event), {"timestamp", "level", "event"})
            self.assertRegex(event["timestamp"], TIMESTAMP_PATTERN)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_request_event_normalizes_method_and_route(self) -> None:
        scope = {
            "method": "GET",
            "route": SimpleNamespace(path="/health"),
        }
        log_http_request(scope, 200)
        log_http_request(
            {
                "method": "SECRET-METHOD",
                "route": SimpleNamespace(path="/secret-path-marker"),
            },
            404,
        )

        events = self._events(self.stdout)
        self.assertEqual(
            [
                {
                    key: value
                    for key, value in event.items()
                    if key != "timestamp"
                }
                for event in events
            ],
            [
                {
                    "level": "INFO",
                    "event": "http.request",
                    "method": "GET",
                    "route": "/health",
                    "status_code": 200,
                },
                {
                    "level": "INFO",
                    "event": "http.request",
                    "method": "OTHER",
                    "route": "unmatched",
                    "status_code": 404,
                },
            ],
        )
        serialized = self.stdout.getvalue()
        self.assertNotIn("SECRET-METHOD", serialized)
        self.assertNotIn("secret-path-marker", serialized)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_error_event_uses_closed_mapping_on_stderr(self) -> None:
        scope = {
            "method": "POST",
            "route": SimpleNamespace(path="/chat"),
        }
        log_http_error(scope, 503, "configuration_incomplete")
        log_http_error(scope, 418, "dynamic-secret-error-marker")

        events = self._events(self.stderr)
        self.assertEqual(
            [
                {
                    key: value
                    for key, value in event.items()
                    if key != "timestamp"
                }
                for event in events
            ],
            [
                {
                    "level": "ERROR",
                    "event": "http.error",
                    "method": "POST",
                    "route": "/chat",
                    "status_code": 503,
                    "error_code": "configuration_incomplete",
                },
                {
                    "level": "ERROR",
                    "event": "http.error",
                    "method": "POST",
                    "route": "/chat",
                    "status_code": 500,
                    "error_code": "internal_error",
                },
            ],
        )
        self.assertNotIn("dynamic-secret-error-marker", self.stderr.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")

    def test_unhandled_exception_logs_only_safe_fixed_events(self) -> None:
        exception_marker = "raw-exception-secret-marker"

        async def failing_app(_scope, _receive, _send) -> None:
            raise RuntimeError(exception_marker)

        middleware = StructuredLoggingMiddleware(failing_app)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/private-path-marker",
            "query_string": b"private-query-marker",
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(_message: dict[str, object]) -> None:
            return None

        with self.assertRaisesRegex(RuntimeError, exception_marker):
            asyncio.run(middleware(scope, receive, send))

        stdout_events = self._events(self.stdout)
        stderr_events = self._events(self.stderr)
        self.assertEqual(
            {
                key: value
                for key, value in stdout_events[0].items()
                if key != "timestamp"
            },
            {
                "level": "INFO",
                "event": "http.request",
                "method": "POST",
                "route": "unmatched",
                "status_code": 500,
            },
        )
        self.assertEqual(
            {
                key: value
                for key, value in stderr_events[0].items()
                if key != "timestamp"
            },
            {
                "level": "ERROR",
                "event": "http.error",
                "method": "POST",
                "route": "unmatched",
                "status_code": 500,
                "error_code": "internal_error",
            },
        )
        combined = self.stdout.getvalue() + self.stderr.getvalue()
        for marker in (
            exception_marker,
            "RuntimeError",
            "private-path-marker",
            "private-query-marker",
        ):
            self.assertNotIn(marker, combined)

    @staticmethod
    def _events(stream: io.StringIO) -> list[dict[str, object]]:
        return [json.loads(line) for line in stream.getvalue().splitlines()]


if __name__ == "__main__":
    unittest.main()
