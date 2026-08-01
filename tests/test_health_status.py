import json
import os
import unittest
from unittest.mock import patch

from src.main import app, health, status


class HealthAndStatusTests(unittest.TestCase):
    def test_health_reports_process_liveness_independently(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(health(), {"status": "healthy"})

    def test_status_reports_incomplete_ollama_configuration_as_not_ready(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            payload = status()

        self.assertEqual(
            payload,
            {
                "status": "degraded",
                "dependencies": {
                    "ollama": {
                        "configured": False,
                        "ready": False,
                        "detail": "configuration_incomplete",
                    }
                },
            },
        )

    def test_status_does_not_claim_readiness_before_adapter_check_exists(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OLLAMA_HOST": "not-exposed.internal",
                "OLLAMA_PORT": "11434",
            },
            clear=True,
        ):
            payload = status()

        self.assertEqual(
            payload,
            {
                "status": "degraded",
                "dependencies": {
                    "ollama": {
                        "configured": True,
                        "ready": False,
                        "detail": "readiness_not_checked",
                    }
                },
            },
        )
        self.assertNotIn("not-exposed.internal", json.dumps(payload))
        self.assertNotIn("11434", json.dumps(payload))

    def test_status_reports_invalid_configuration_without_rejected_value(self) -> None:
        rejected = " rejected-secret-marker "
        with patch.dict(os.environ, {"OLLAMA_HOST": rejected}, clear=True):
            payload = status()

        self.assertEqual(
            payload,
            {
                "status": "degraded",
                "dependencies": {
                    "ollama": {
                        "configured": False,
                        "ready": False,
                        "detail": "configuration_invalid",
                    }
                },
            },
        )
        self.assertNotIn(rejected, json.dumps(payload))

    def test_unrelated_inert_configuration_does_not_misstate_ollama_status(self) -> None:
        with patch.dict(os.environ, {"AUTH_ENABLED": "not-a-boolean"}, clear=True):
            payload = status()

        self.assertEqual(
            payload["dependencies"]["ollama"],
            {
                "configured": False,
                "ready": False,
                "detail": "configuration_incomplete",
            },
        )

    def test_route_and_openapi_inventory_is_exact(self) -> None:
        routes = {
            route.path: sorted(route.methods or [])
            for route in app.routes
        }
        self.assertEqual(
            routes,
            {
                "/openapi.json": ["GET", "HEAD"],
                "/health": ["GET"],
                "/status": ["GET"],
            },
        )
        self.assertEqual(set(app.openapi()["paths"]), {"/health", "/status"})


if __name__ == "__main__":
    unittest.main()
