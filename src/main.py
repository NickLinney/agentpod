import os

from fastapi import FastAPI

from src.config import ConfigurationError, load_config
from src.inference import (
    InferenceReadinessAdapter,
    OllamaClient,
    UrllibJsonTransport,
)


app = FastAPI(
    title="NickLinney.AgentPod",
    version="unassigned",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)


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


def _build_ollama_adapter(
    host: str,
    port: int,
    model: str,
) -> InferenceReadinessAdapter:
    return OllamaClient(
        host=host,
        port=port,
        model=model,
        timeout_seconds=1.0,
        transport=UrllibJsonTransport(),
    )
