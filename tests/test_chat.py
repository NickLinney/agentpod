import asyncio
import json
import os
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from src.inference import ChatResult
from src.main import ChatRequest, chat, invalid_request_handler


def response_payload(response: object) -> dict[str, object]:
    body = getattr(response, "body")
    return json.loads(body.decode("utf-8"))


class ChatApiContractTests(unittest.TestCase):
    def test_success_calls_adapter_once_with_original_message(self) -> None:
        adapter = Mock()
        adapter.chat.return_value = ChatResult(" exact assistant response ", "success")
        with (
            patch.dict(
                os.environ,
                {"OLLAMA_HOST": "ollama.internal", "OLLAMA_PORT": "11434"},
                clear=True,
            ),
            patch("src.main._build_ollama_adapter", return_value=adapter) as build,
        ):
            response = chat(ChatRequest(message=" original conversation "))

        self.assertEqual(
            response.model_dump(),
            {"response": " exact assistant response "},
        )
        build.assert_called_once_with(
            "ollama.internal",
            11434,
            "meta-llama/Llama-3.2-1B",
        )
        adapter.chat.assert_called_once_with(" original conversation ")

    def test_request_contract_rejects_invalid_shapes(self) -> None:
        invalid_payloads = (
            None,
            [],
            {},
            {"message": 1},
            {"message": ""},
            {"message": "   "},
            {"message": "valid", "extra": "not-allowed"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    ChatRequest.model_validate(payload)

    def test_validation_handler_returns_fixed_safe_error(self) -> None:
        response = asyncio.run(invalid_request_handler(Mock(), Mock()))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response_payload(response), {"error": {"code": "invalid_request"}})

    def test_incomplete_configuration_returns_fixed_error_without_adapter(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.main._build_ollama_adapter") as build,
        ):
            response = chat(ChatRequest(message="conversation-marker"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response_payload(response),
            {"error": {"code": "configuration_incomplete"}},
        )
        self.assertNotIn("conversation-marker", response.body.decode("utf-8"))
        build.assert_not_called()

    def test_invalid_configuration_returns_fixed_error_without_adapter(self) -> None:
        rejected = "rejected-configuration-marker"
        with (
            patch.dict(os.environ, {"OLLAMA_PORT": rejected}, clear=True),
            patch("src.main._build_ollama_adapter") as build,
        ):
            response = chat(ChatRequest(message="conversation-marker"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response_payload(response),
            {"error": {"code": "configuration_invalid"}},
        )
        serialized = response.body.decode("utf-8")
        self.assertNotIn(rejected, serialized)
        self.assertNotIn("conversation-marker", serialized)
        build.assert_not_called()

    def test_adapter_errors_map_to_fixed_safe_responses(self) -> None:
        cases = (
            (ChatResult(None, "model_unavailable"), 503, "model_unavailable"),
            (ChatResult(None, "service_unavailable"), 503, "dependency_unavailable"),
            (ChatResult(None, "timeout"), 504, "dependency_timeout"),
            (ChatResult(None, "service_error"), 502, "dependency_error"),
            (
                ChatResult(None, "invalid_response"),
                502,
                "dependency_invalid_response",
            ),
        )
        for result, expected_status, expected_code in cases:
            with self.subTest(result=result):
                adapter = Mock()
                adapter.chat.return_value = result
                with (
                    patch.dict(
                        os.environ,
                        {"OLLAMA_HOST": "private-host", "OLLAMA_PORT": "11434"},
                        clear=True,
                    ),
                    patch("src.main._build_ollama_adapter", return_value=adapter),
                ):
                    response = chat(ChatRequest(message="conversation-secret-marker"))

                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(
                    response_payload(response),
                    {"error": {"code": expected_code}},
                )
                serialized = response.body.decode("utf-8")
                self.assertNotIn("private-host", serialized)
                self.assertNotIn("11434", serialized)
                self.assertNotIn("conversation-secret-marker", serialized)


if __name__ == "__main__":
    unittest.main()
