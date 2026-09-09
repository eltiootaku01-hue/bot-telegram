from __future__ import annotations

import unittest

from bot_ia.core import Intent, Route, RouteDecision
from bot_ia.providers import GeminiProvider, OpenAIProvider, ProviderManager, ProviderRequest, ProviderStatus
from bot_ia.providers.errors import InputTooLargeError, MissingApiKeyError, ProviderDisabledError, ProviderTimeoutError


def key(_: str) -> str:
    return "test-key"


def openai_transport(_: str, headers: dict[str, str], payload: dict[str, object], __: float) -> dict[str, object]:
    assert headers["Authorization"] == "Bearer test-key"
    assert payload["input"] == "prepared context only"
    return {"output_text": "ok", "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}}


class Phase6Tests(unittest.TestCase):
    def request(self, provider: str = "openai", text: str = "prepared context only") -> ProviderRequest:
        return ProviderRequest(provider, "test-model", text, 32, 1.0, "request-1", "creative request")

    def llm_decision(self) -> RouteDecision:
        return RouteDecision(Route.LLM, "creative", __import__("bot_ia.contracts", fromlist=["Confidence"]).Confidence.HIGH, Intent.CREATIVE_WRITING, "one_neko_punch", requires_llm=True)

    def test_provider_contract_returns_response_and_usage(self) -> None:
        response = OpenAIProvider(key_loader=key, transport=openai_transport).generate(self.request())
        self.assertEqual(ProviderStatus.SUCCESS, response.status)
        self.assertEqual(5, response.usage.total_tokens)

    def test_gemini_adapter_parses_fake_response(self) -> None:
        provider = GeminiProvider(
            key_loader=key,
            transport=lambda *_: {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": "gemini ok",
                            }
                        ],
                    }
                ],
                "usage": {
                    "total_input_tokens": 3,
                    "total_output_tokens": 2,
                    "total_tokens": 5,
                },
            },
        )

        self.assertEqual(
            "gemini ok",
            provider.generate(
                self.request("gemini")
            ).output_text,
        )
    def test_provider_error_is_typed(self) -> None:
        with self.assertRaises(MissingApiKeyError):
            OpenAIProvider(key_loader=lambda _: None, transport=openai_transport).generate(self.request())

    def test_fallback_uses_configured_provider_after_failure(self) -> None:
        primary = OpenAIProvider(
            key_loader=key,
            transport=lambda *_: (
                _ for _ in ()
            ).throw(
                ProviderTimeoutError("timeout")
            ),
        )

        fallback = GeminiProvider(
            key_loader=key,
            transport=lambda *_: {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": "fallback",
                            }
                        ],
                    }
                ]
            },
        )

        outcome = ProviderManager(
            (primary, fallback)
        ).execute(
            self.llm_decision(),
            self.request(),
            fallback_provider="gemini",
        )

        self.assertEqual(
            ("openai", "gemini"),
            outcome.attempts,
        )
        self.assertTrue(
            outcome.response.fallback_used
        )
    def test_timeout_returns_error_without_fallback(self) -> None:
        provider = OpenAIProvider(key_loader=key, transport=lambda *_: (_ for _ in ()).throw(ProviderTimeoutError("timeout")))
        outcome = ProviderManager((provider,)).execute(self.llm_decision(), self.request())
        self.assertEqual(ProviderStatus.ERROR, outcome.response.status)
        self.assertEqual("ProviderTimeoutError", outcome.response.error_type)

    def test_large_input_is_rejected(self) -> None:
        provider = OpenAIProvider(key_loader=key, transport=openai_transport, max_input_chars=5)
        with self.assertRaises(InputTooLargeError):
            provider.generate(self.request(text="too long"))

    def test_disabled_provider_is_rejected(self) -> None:
        with self.assertRaises(ProviderDisabledError):
            OpenAIProvider(enabled=False, key_loader=key, transport=openai_transport).generate(self.request())

    def test_missing_key_is_rejected_without_exposure(self) -> None:
        with self.assertRaises(MissingApiKeyError):
            GeminiProvider(key_loader=lambda _: "", transport=lambda *_: {}).generate(self.request("gemini"))

    def test_provider_request_has_no_universe_or_memory_fields(self) -> None:
        request = self.request()
        self.assertFalse(hasattr(request, "universe_id"))
        self.assertFalse(hasattr(request, "memory"))
        self.assertFalse(hasattr(request, "evidence_pack"))

    def test_local_route_never_calls_provider(self) -> None:
        local = RouteDecision(Route.LOCAL, "hello", __import__("bot_ia.contracts", fromlist=["Confidence"]).Confidence.HIGH, Intent.GREETING, "one_neko_punch")
        outcome = ProviderManager((OpenAIProvider(key_loader=key, transport=lambda *_: (_ for _ in ()).throw(AssertionError("must not call"))),)).execute(local, self.request())
        self.assertEqual(ProviderStatus.SKIPPED, outcome.response.status)
        self.assertEqual((), outcome.attempts)

    def test_fallback_does_not_run_for_local_route(self) -> None:
        local = RouteDecision(Route.LOCAL, "help", __import__("bot_ia.contracts", fromlist=["Confidence"]).Confidence.HIGH, Intent.HELP, "one_neko_punch")
        outcome = ProviderManager(()).execute(local, self.request(), fallback_provider="gemini")
        self.assertEqual(ProviderStatus.SKIPPED, outcome.response.status)


if __name__ == "__main__":
    unittest.main()
