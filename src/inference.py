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


class InferenceReadinessAdapter(Protocol):
    def check_readiness(self) -> DependencyReadiness: ...


class JsonTransport(Protocol):
    def get_json(self, url: str, timeout_seconds: float) -> object: ...


class UrllibJsonTransport:
    def get_json(self, url: str, timeout_seconds: float) -> object:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.load(response)


class OllamaClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        model: str,
        timeout_seconds: float,
        transport: JsonTransport,
    ) -> None:
        self._models_url = f"http://{host}:{port}/api/tags"
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def check_readiness(self) -> DependencyReadiness:
        try:
            payload = self._transport.get_json(
                self._models_url,
                self._timeout_seconds,
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
