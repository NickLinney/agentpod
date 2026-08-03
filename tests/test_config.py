import unittest

from src.config import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OLLAMA_MODEL,
    OLLAMA_CHAT_TIMEOUT_SECONDS,
    OLLAMA_READINESS_TIMEOUT_SECONDS,
    AgentPodConfig,
    ConfigurationError,
    load_config,
)
from src.main import app


class ConfigurationContractTests(unittest.TestCase):
    def test_unset_values_use_only_the_approved_model_default(self) -> None:
        config = load_config({})

        self.assertEqual(config.local_model, DEFAULT_LOCAL_MODEL)
        self.assertIsNone(config.ollama_host)
        self.assertIsNone(config.ollama_port)
        self.assertIsNone(config.agent_name)
        self.assertIsNone(config.agent_id)
        self.assertIsNone(config.webui_port)
        self.assertIsNone(config.api_port)
        self.assertIsNone(config.log_level)
        self.assertIsNone(config.memory_backend)
        self.assertIsNone(config.auth_enabled)
        self.assertIsNone(config.telemetry_enabled)

    def test_valid_overrides_preserve_strings_and_parse_ports_and_booleans(self) -> None:
        config = load_config(
            {
                "LOCAL_MODEL": DEFAULT_LOCAL_MODEL,
                "OLLAMA_HOST": "ollama.internal",
                "OLLAMA_PORT": "11434",
                "AGENT_NAME": "reference-agent",
                "AGENT_ID": "agent-id-without-inferred-format",
                "WEBUI_PORT": "8080",
                "API_PORT": "8000",
                "LOG_LEVEL": "Notice",
                "MEMORY_BACKEND": "literal-backend",
                "AUTH_ENABLED": "TrUe",
                "TELEMETRY_ENABLED": "FALSE",
            }
        )

        self.assertEqual(
            config,
            AgentPodConfig(
                local_model=DEFAULT_LOCAL_MODEL,
                ollama_host="ollama.internal",
                ollama_port=11434,
                agent_name="reference-agent",
                agent_id="agent-id-without-inferred-format",
                webui_port=8080,
                api_port=8000,
                log_level="Notice",
                memory_backend="literal-backend",
                auth_enabled=True,
                telemetry_enabled=False,
            ),
        )

    def test_safe_diagnostics_mask_host_and_agent_identity(self) -> None:
        config = load_config(
            {
                "OLLAMA_HOST": "private-host",
                "AGENT_NAME": "private-name",
                "AGENT_ID": "private-id",
                "AUTH_ENABLED": "true",
            }
        )

        safe = config.to_safe_dict()
        self.assertEqual(safe["LOCAL_MODEL"], DEFAULT_LOCAL_MODEL)
        self.assertEqual(safe["OLLAMA_HOST"], "<configured>")
        self.assertEqual(safe["AGENT_NAME"], "<configured>")
        self.assertEqual(safe["AGENT_ID"], "<configured>")
        self.assertIs(safe["AUTH_ENABLED"], True)
        self.assertNotIn("private-host", safe.values())
        self.assertNotIn("private-name", safe.values())
        self.assertNotIn("private-id", safe.values())

    def test_live_inference_contract_uses_approved_mapping_and_timeouts(self) -> None:
        self.assertEqual(DEFAULT_LOCAL_MODEL, "meta-llama/Llama-3.2-1B")
        self.assertEqual(DEFAULT_OLLAMA_MODEL, "llama3.2:1b-text-q4_K_M")
        self.assertEqual(OLLAMA_READINESS_TIMEOUT_SECONDS, 1.0)
        self.assertEqual(OLLAMA_CHAT_TIMEOUT_SECONDS, 120.0)

    def test_model_allowlist_rejects_alias_alternate_and_mismatch_without_echo(self) -> None:
        rejected = (
            {"LOCAL_MODEL": "meta-llama/Llama-3.2-3B"},
            {"LOCAL_MODEL": "llama3.2:1b"},
        )
        for environ in rejected:
            with self.subTest(environ=environ):
                with self.assertRaises(ConfigurationError) as context:
                    load_config(environ)
                self.assertNotIn("llama3.2:1b", str(context.exception))
                self.assertNotIn("Llama-3.2-3B", str(context.exception))

    def test_blank_and_edge_whitespace_strings_are_rejected(self) -> None:
        names = (
            "LOCAL_MODEL",
            "OLLAMA_HOST",
            "AGENT_NAME",
            "AGENT_ID",
            "LOG_LEVEL",
            "MEMORY_BACKEND",
        )
        for name in names:
            for value in ("", " value", "value ", "\tvalue", "value\n"):
                with self.subTest(name=name, value=repr(value)):
                    with self.assertRaises(ConfigurationError):
                        load_config({name: value})

    def test_ports_require_canonical_decimal_values_in_range(self) -> None:
        names = ("OLLAMA_PORT", "WEBUI_PORT", "API_PORT")
        invalid_values = (
            "",
            "0",
            "65536",
            "01",
            "+1",
            "-1",
            "1.0",
            " 1",
            "1 ",
            "one",
            "١",
        )
        for name in names:
            for value in invalid_values:
                with self.subTest(name=name, value=repr(value)):
                    with self.assertRaises(ConfigurationError):
                        load_config({name: value})

            with self.subTest(name=name, value="non-string boolean"):
                with self.assertRaises(ConfigurationError):
                    load_config({name: True})  # type: ignore[dict-item]

    def test_boolean_values_are_unambiguous(self) -> None:
        for name in ("AUTH_ENABLED", "TELEMETRY_ENABLED"):
            for value, expected in (
                ("true", True),
                ("TRUE", True),
                ("false", False),
                ("FaLsE", False),
            ):
                with self.subTest(name=name, value=value):
                    config = load_config({name: value})
                    attribute = name.casefold()
                    self.assertIs(getattr(config, attribute), expected)

            for value in ("", " true", "true ", "1", "0", "yes", "no", "on", "off"):
                with self.subTest(name=name, value=repr(value)):
                    with self.assertRaises(ConfigurationError):
                        load_config({name: value})

    def test_validation_errors_do_not_echo_rejected_input(self) -> None:
        cases = (
            ("LOCAL_MODEL", " rejected-string-marker "),
            ("OLLAMA_PORT", "rejected-port-marker"),
            ("AUTH_ENABLED", "rejected-boolean-marker"),
        )
        for name, value in cases:
            with self.subTest(name=name):
                with self.assertRaises(ConfigurationError) as raised:
                    load_config({name: value})
                self.assertIn(name, str(raised.exception))
                self.assertNotIn(value, str(raised.exception))

    def test_excluded_subsystem_values_are_inert_configuration_shape(self) -> None:
        config = load_config(
            {
                "WEBUI_PORT": "8080",
                "MEMORY_BACKEND": "not-activated",
                "AUTH_ENABLED": "true",
                "TELEMETRY_ENABLED": "false",
            }
        )

        self.assertEqual(config.webui_port, 8080)
        self.assertEqual(config.memory_backend, "not-activated")
        self.assertIs(config.auth_enabled, True)
        self.assertIs(config.telemetry_enabled, False)
        self.assertEqual(
            [route.path for route in app.routes],
            ["/openapi.json", "/health", "/status", "/chat"],
        )


if __name__ == "__main__":
    unittest.main()
