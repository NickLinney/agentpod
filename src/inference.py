import json
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class DependencyReadiness:
    ready: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ChatResult:
    response: str | None
    detail: str


class InferenceReadinessAdapter(Protocol):
    def check_readiness(self) -> DependencyReadiness: ...


class InferenceChatAdapter(Protocol):
    def chat(self, message: str) -> ChatResult: ...


class InferenceAdapter(InferenceReadinessAdapter, InferenceChatAdapter, Protocol):
    pass


class JsonTransport(Protocol):
    def get_json(self, url: str, timeout_seconds: float) -> object: ...

    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> object: ...


class UrllibJsonTransport:
    def get_json(self, url: str, timeout_seconds: float) -> object:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.load(response)

    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> object:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.load(response)


class OllamaClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        model: str,
        readiness_timeout_seconds: float,
        chat_timeout_seconds: float,
        transport: JsonTransport,
    ) -> None:
        self._models_url = f"http://{host}:{port}/api/tags"
        self._chat_url = f"http://{host}:{port}/api/chat"
        self._model = model
        self._readiness_timeout_seconds = readiness_timeout_seconds
        self._chat_timeout_seconds = chat_timeout_seconds
        self._transport = transport

    def check_readiness(self) -> DependencyReadiness:
        try:
            payload = self._transport.get_json(
                self._models_url,
                self._readiness_timeout_seconds,
            )
        except HTTPError:
            return DependencyReadiness(False, "service_error")
        except (TimeoutError, socket.timeout):
            return DependencyReadiness(False, "timeout")
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                return DependencyReadiness(False, "timeout")
            return DependencyReadiness(False, "service_unavailable")
        except OSError:
            return DependencyReadiness(False, "service_unavailable")
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
            return DependencyReadiness(False, "invalid_response")

        if not isinstance(payload, Mapping):
            return DependencyReadiness(False, "invalid_response")

        models = payload.get("models")
        if not isinstance(models, list):
            return DependencyReadiness(False, "invalid_response")

        for model in models:
            if not isinstance(model, Mapping):
                return DependencyReadiness(False, "invalid_response")
            if model.get("name") == self._model or model.get("model") == self._model:
                return DependencyReadiness(True, "ready")

        return DependencyReadiness(False, "model_unavailable")

    def chat(self, message: str) -> ChatResult:
        request_payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        }
        try:
            payload = self._transport.post_json(
                self._chat_url,
                request_payload,
                self._chat_timeout_seconds,
            )
        except HTTPError as error:
            detail = "model_unavailable" if error.code == 404 else "service_error"
            return ChatResult(None, detail)
        except (TimeoutError, socket.timeout):
            return ChatResult(None, "timeout")
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                return ChatResult(None, "timeout")
            return ChatResult(None, "service_unavailable")
        except OSError:
            return ChatResult(None, "service_unavailable")
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
            return ChatResult(None, "invalid_response")

        if not isinstance(payload, Mapping):
            return ChatResult(None, "invalid_response")

        response_message = payload.get("message")
        if not isinstance(response_message, Mapping):
            return ChatResult(None, "invalid_response")

        content = response_message.get("content")
        if not isinstance(content, str) or not content.strip():
            return ChatResult(None, "invalid_response")
        return ChatResult(content, "success")
