import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from src.application_logging import (
    StructuredLoggingMiddleware,
    log_application_shutdown,
    log_application_startup,
    log_current_http_error,
)
from src.config import ConfigurationError, load_config
from src.inference import (
    ChatResult,
    InferenceAdapter,
    OllamaClient,
    UrllibJsonTransport,
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: StrictStr

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be empty or whitespace-only")
        return value


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log_application_startup()
    try:
        yield
    finally:
        log_application_shutdown()


app = FastAPI(
    title="NickLinney.AgentPod",
    version="unassigned",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(StructuredLoggingMiddleware)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(
    _request: Request,
    _error: RequestValidationError,
) -> JSONResponse:
    return _error_response("invalid_request", 422)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/status")
def status() -> dict[str, object]:
    ollama_environment = {
        name: os.environ[name]
        for name in ("LOCAL_MODEL", "OLLAMA_HOST", "OLLAMA_PORT")
        if name in os.environ
    }
    try:
        config = load_config(ollama_environment)
    except ConfigurationError:
        ollama = {
            "configured": False,
            "ready": False,
            "detail": "configuration_invalid",
        }
    else:
        configured = config.ollama_host is not None and config.ollama_port is not None
        if configured:
            adapter = _build_ollama_adapter(
                config.ollama_host,
                config.ollama_port,
                config.local_model,
            )
            readiness = adapter.check_readiness()
            ollama = {
                "configured": True,
                "ready": readiness.ready,
                "detail": readiness.detail,
            }
        else:
            ollama = {
                "configured": False,
                "ready": False,
                "detail": "configuration_incomplete",
            }

    overall = "ready" if ollama["ready"] else "degraded"
    return {"status": overall, "dependencies": {"ollama": ollama}}


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
def chat(request: ChatRequest) -> ChatResponse | JSONResponse:
    ollama_environment = {
        name: os.environ[name]
        for name in ("LOCAL_MODEL", "OLLAMA_HOST", "OLLAMA_PORT")
        if name in os.environ
    }
    try:
        config = load_config(ollama_environment)
    except ConfigurationError:
        return _error_response("configuration_invalid", 503)

    if config.ollama_host is None or config.ollama_port is None:
        return _error_response("configuration_incomplete", 503)

    adapter = _build_ollama_adapter(
        config.ollama_host,
        config.ollama_port,
        config.local_model,
    )
    result = adapter.chat(request.message)
    if result.detail == "success" and result.response is not None:
        return ChatResponse(response=result.response)
    return _chat_error_response(result)


def _build_ollama_adapter(
    host: str,
    port: int,
    model: str,
) -> InferenceAdapter:
    return OllamaClient(
        host=host,
        port=port,
        model=model,
        readiness_timeout_seconds=1.0,
        chat_timeout_seconds=120.0,
        transport=UrllibJsonTransport(),
    )


def _chat_error_response(result: ChatResult) -> JSONResponse:
    mappings = {
        "model_unavailable": ("model_unavailable", 503),
        "service_unavailable": ("dependency_unavailable", 503),
        "timeout": ("dependency_timeout", 504),
        "service_error": ("dependency_error", 502),
        "invalid_response": ("dependency_invalid_response", 502),
    }
    code, status_code = mappings.get(result.detail, ("dependency_error", 502))
    return _error_response(code, status_code)


def _error_response(code: str, status_code: int) -> JSONResponse:
    log_current_http_error(status_code, code)
    return JSONResponse(status_code=status_code, content={"error": {"code": code}})
