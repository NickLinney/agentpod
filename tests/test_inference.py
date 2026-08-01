import io
import unittest
from urllib.error import HTTPError, URLError

from src.inference import ChatResult, DependencyReadiness, OllamaClient


class FakeTransport:
    def __init__(self, *, response: object = None, error: BaseException | None = None):
        self.response = response
        self.error = error
        self.get_calls: list[tuple[str, float]] = []
        self.post_calls: list[tuple[str, object, float]] = []

    def get_json(self, url: str, timeout_seconds: float) -> object:
        self.get_calls.append((url, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.response

    def post_json(self, url: str, payload: object, timeout_seconds: float) -> object:
        self.post_calls.append((url, payload, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.response


def build_client(transport: FakeTransport, model: str = "literal/model") -> OllamaClient:
    return OllamaClient(
        host="ollama.local",
        port=11434,
        model=model,
        readiness_timeout_seconds=1.0,
        chat_timeout_seconds=120.0,
        transport=transport,
    )


class OllamaClientContractTests(unittest.TestCase):
    def test_exact_model_match_reports_ready(self) -> None:
        transport = FakeTransport(response={"models": [{"name": "literal/model"}]})

        result = build_client(transport).check_readiness()

        self.assertEqual(result, DependencyReadiness(True, "ready"))
        self.assertEqual(
            transport.get_calls,
            [("http://ollama.local:11434/api/tags", 1.0)],
        )

    def test_model_field_is_accepted_only_on_exact_match(self) -> None:
        transport = FakeTransport(response={"models": [{"model": "literal/model"}]})
        self.assertEqual(
            build_client(transport).check_readiness(),
            DependencyReadiness(True, "ready"),
        )

    def test_model_name_is_not_corrected_or_normalized(self) -> None:
        transport = FakeTransport(response={"models": [{"name": "literal/model:latest"}]})
        self.assertEqual(
            build_client(transport, model="literal/model").check_readiness(),
            DependencyReadiness(False, "model_unavailable"),
        )

    def test_unavailable_service_maps_to_fixed_result(self) -> None:
        transport = FakeTransport(error=URLError(ConnectionRefusedError()))
        self.assertEqual(
            build_client(transport).check_readiness(),
            DependencyReadiness(False, "service_unavailable"),
        )

    def test_timeout_variants_map_to_fixed_result(self) -> None:
        for error in (TimeoutError(), URLError(TimeoutError())):
            with self.subTest(error=type(error).__name__):
                transport = FakeTransport(error=error)
                self.assertEqual(
                    build_client(transport).check_readiness(),
                    DependencyReadiness(False, "timeout"),
                )

    def test_http_error_maps_without_exposing_response(self) -> None:
        error = HTTPError(
            "http://not-exposed.invalid",
            503,
            "rejected-secret-marker",
            {},
            io.BytesIO(b"rejected-secret-marker"),
        )
        transport = FakeTransport(error=error)

        result = build_client(transport).check_readiness()

        self.assertEqual(result, DependencyReadiness(False, "service_error"))
        self.assertNotIn("rejected-secret-marker", repr(result))
        self.assertNotIn("not-exposed.invalid", repr(result))

    def test_invalid_response_shapes_map_to_fixed_result(self) -> None:
        invalid_payloads = (
            None,
            [],
            {},
            {"models": {}},
            {"models": ["not-an-object"]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                transport = FakeTransport(response=payload)
                self.assertEqual(
                    build_client(transport).check_readiness(),
                    DependencyReadiness(False, "invalid_response"),
                )


class OllamaChatContractTests(unittest.TestCase):
    def test_chat_sends_exact_model_and_original_message_once(self) -> None:
        transport = FakeTransport(
            response={"message": {"role": "assistant", "content": " exact response "}}
        )
        client = build_client(transport, model="exact/model")

        result = client.chat(" original message ")

        self.assertEqual(result, ChatResult(" exact response ", "success"))
        self.assertEqual(
            transport.post_calls,
            [
                (
                    "http://ollama.local:11434/api/chat",
                    {
                        "model": "exact/model",
                        "messages": [
                            {"role": "user", "content": " original message "}
                        ],
                        "stream": False,
                    },
                    120.0,
                )
            ],
        )

    def test_chat_maps_model_unavailable(self) -> None:
        error = HTTPError("http://not-exposed.invalid", 404, "not found", {}, None)
        transport = FakeTransport(error=error)
        self.assertEqual(
            build_client(transport).chat("message"),
            ChatResult(None, "model_unavailable"),
        )

    def test_chat_maps_service_unavailable(self) -> None:
        transport = FakeTransport(error=URLError(ConnectionRefusedError()))
        self.assertEqual(
            build_client(transport).chat("message"),
            ChatResult(None, "service_unavailable"),
        )

    def test_chat_maps_timeout_variants(self) -> None:
        for error in (TimeoutError(), URLError(TimeoutError())):
            with self.subTest(error=type(error).__name__):
                transport = FakeTransport(error=error)
                self.assertEqual(
                    build_client(transport).chat("message"),
                    ChatResult(None, "timeout"),
                )

    def test_chat_maps_service_error_without_exposing_upstream_content(self) -> None:
        error = HTTPError(
            "http://not-exposed.invalid",
            500,
            "rejected-secret-marker",
            {},
            io.BytesIO(b"rejected-secret-marker"),
        )
        result = build_client(FakeTransport(error=error)).chat("conversation-marker")

        self.assertEqual(result, ChatResult(None, "service_error"))
        self.assertNotIn("rejected-secret-marker", repr(result))
        self.assertNotIn("conversation-marker", repr(result))

    def test_chat_rejects_malformed_or_empty_response(self) -> None:
        invalid_payloads = (
            None,
            [],
            {},
            {"message": "not-an-object"},
            {"message": {}},
            {"message": {"content": None}},
            {"message": {"content": ""}},
            {"message": {"content": "   "}},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.assertEqual(
                    build_client(FakeTransport(response=payload)).chat("message"),
                    ChatResult(None, "invalid_response"),
                )


if __name__ == "__main__":
    unittest.main()
