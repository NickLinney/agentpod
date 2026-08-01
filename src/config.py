import os
from collections.abc import Mapping
from dataclasses import dataclass


DEFAULT_LOCAL_MODEL = "meta-llama/Llama-3.2-1B"


class ConfigurationError(ValueError):
    """Raised when an AgentPod environment value violates its contract."""


@dataclass(frozen=True, slots=True)
class AgentPodConfig:
    local_model: str
    ollama_host: str | None
    ollama_port: int | None
    agent_name: str | None
    agent_id: str | None
    webui_port: int | None
    api_port: int | None
    log_level: str | None
    memory_backend: str | None
    auth_enabled: bool | None
    telemetry_enabled: bool | None

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "LOCAL_MODEL": self.local_model,
            "OLLAMA_HOST": _configured_marker(self.ollama_host),
            "OLLAMA_PORT": self.ollama_port,
            "AGENT_NAME": _configured_marker(self.agent_name),
            "AGENT_ID": _configured_marker(self.agent_id),
            "WEBUI_PORT": self.webui_port,
            "API_PORT": self.api_port,
            "LOG_LEVEL": self.log_level,
            "MEMORY_BACKEND": self.memory_backend,
            "AUTH_ENABLED": self.auth_enabled,
            "TELEMETRY_ENABLED": self.telemetry_enabled,
        }


def load_config(environ: Mapping[str, str] | None = None) -> AgentPodConfig:
    source = os.environ if environ is None else environ
    local_model = _parse_string(source, "LOCAL_MODEL")

    return AgentPodConfig(
        local_model=DEFAULT_LOCAL_MODEL if local_model is None else local_model,
        ollama_host=_parse_string(source, "OLLAMA_HOST"),
        ollama_port=_parse_port(source, "OLLAMA_PORT"),
        agent_name=_parse_string(source, "AGENT_NAME"),
        agent_id=_parse_string(source, "AGENT_ID"),
        webui_port=_parse_port(source, "WEBUI_PORT"),
        api_port=_parse_port(source, "API_PORT"),
        log_level=_parse_string(source, "LOG_LEVEL"),
        memory_backend=_parse_string(source, "MEMORY_BACKEND"),
        auth_enabled=_parse_bool(source, "AUTH_ENABLED"),
        telemetry_enabled=_parse_bool(source, "TELEMETRY_ENABLED"),
    )


def _parse_string(environ: Mapping[str, str], name: str) -> str | None:
    if name not in environ:
        return None

    value = environ[name]
    if not isinstance(value, str) or not value or value != value.strip():
        raise ConfigurationError(
            f"{name} must be a non-empty string without leading or trailing whitespace"
        )
    return value


def _parse_port(environ: Mapping[str, str], name: str) -> int | None:
    if name not in environ:
        return None

    value = environ[name]
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or (len(value) > 1 and value.startswith("0"))
    ):
        raise ConfigurationError(
            f"{name} must be a canonical base-10 integer from 1 through 65535"
        )

    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise ConfigurationError(f"{name} must be an integer from 1 through 65535")
    return parsed


def _parse_bool(environ: Mapping[str, str], name: str) -> bool | None:
    if name not in environ:
        return None

    value = environ[name]
    if not isinstance(value, str):
        raise ConfigurationError(f"{name} must be true or false")

    parsed = value.casefold()
    if parsed == "true":
        return True
    if parsed == "false":
        return False
    raise ConfigurationError(f"{name} must be true or false")


def _configured_marker(value: str | None) -> str | None:
    return None if value is None else "<configured>"
