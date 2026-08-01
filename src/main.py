import os

from fastapi import FastAPI

from src.config import ConfigurationError, load_config


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
        ollama = {
            "configured": configured,
            "ready": False,
            "detail": "readiness_not_checked" if configured else "configuration_incomplete",
        }

    return {"status": "degraded", "dependencies": {"ollama": ollama}}
