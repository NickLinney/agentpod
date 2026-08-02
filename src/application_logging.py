import json
import logging
import sys
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import TextIO


_LOGGER_NAME = "agentpod.application"
_ALLOWED_METHODS = frozenset({"GET", "HEAD", "POST"})
_ALLOWED_ROUTES = frozenset({"/openapi.json", "/health", "/status", "/chat"})
_ERROR_STATUS_CODES = {
    "invalid_request": 422,
    "configuration_invalid": 503,
    "configuration_incomplete": 503,
    "model_unavailable": 503,
    "dependency_unavailable": 503,
    "dependency_timeout": 504,
    "dependency_error": 502,
    "dependency_invalid_response": 502,
    "internal_error": 500,
}
_REQUEST_SCOPE: ContextVar[Mapping[str, object] | None] = ContextVar(
    "agentpod_request_scope",
    default=None,
)


class _JsonEventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                timezone.utc,
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "event": record.agentpod_event,
        }
        payload.update(record.agentpod_fields)
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class _BelowErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.ERROR


def configure_application_logging(
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    formatter = _JsonEventFormatter()
    stdout_handler = logging.StreamHandler(sys.stdout if stdout is None else stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(_BelowErrorFilter())
    stdout_handler.setFormatter(formatter)

    stderr_handler = logging.StreamHandler(sys.stderr if stderr is None else stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)


def log_application_startup() -> None:
    _emit(logging.INFO, "application.startup", {})


def log_application_shutdown() -> None:
    _emit(logging.INFO, "application.shutdown", {})


def log_http_request(scope: Mapping[str, object], status_code: int) -> None:
    _emit(
        logging.INFO,
        "http.request",
        {
            "method": _safe_method(scope),
            "route": _safe_route(scope),
            "status_code": status_code,
        },
    )


def log_http_error(
    scope: Mapping[str, object],
    status_code: int,
    error_code: str,
) -> None:
    if _ERROR_STATUS_CODES.get(error_code) != status_code:
        status_code = 500
        error_code = "internal_error"
    _emit(
        logging.ERROR,
        "http.error",
        {
            "method": _safe_method(scope),
            "route": _safe_route(scope),
            "status_code": status_code,
            "error_code": error_code,
        },
    )


def log_current_http_error(status_code: int, error_code: str) -> None:
    scope = _REQUEST_SCOPE.get()
    if scope is not None:
        log_http_error(scope, status_code, error_code)


class StructuredLoggingMiddleware:
    def __init__(self, app: object) -> None:
        self._app = app

    async def __call__(
        self,
        scope: dict[str, object],
        receive: object,
        send: object,
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        token = _REQUEST_SCOPE.set(scope)
        status_code: int | None = None
        request_logged = False

        async def send_with_logging(message: dict[str, object]) -> None:
            nonlocal request_logged, status_code
            if message.get("type") == "http.response.start":
                status_code = int(message["status"])
            await send(message)
            if (
                message.get("type") == "http.response.body"
                and not message.get("more_body", False)
                and not request_logged
            ):
                log_http_request(scope, 500 if status_code is None else status_code)
                request_logged = True

        try:
            await self._app(scope, receive, send_with_logging)
        except Exception:
            log_http_error(scope, 500, "internal_error")
            if not request_logged:
                log_http_request(scope, 500 if status_code is None else status_code)
            raise
        finally:
            _REQUEST_SCOPE.reset(token)


def _safe_method(scope: Mapping[str, object]) -> str:
    method = scope.get("method")
    return method if method in _ALLOWED_METHODS else "OTHER"


def _safe_route(scope: Mapping[str, object]) -> str:
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path if route_path in _ALLOWED_ROUTES else "unmatched"


def _emit(level: int, event: str, fields: Mapping[str, object]) -> None:
    logging.getLogger(_LOGGER_NAME).log(
        level,
        "",
        extra={"agentpod_event": event, "agentpod_fields": fields},
    )


configure_application_logging()
