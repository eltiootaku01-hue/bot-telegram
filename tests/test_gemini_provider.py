from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch
import unittest

from bot_ia.providers import GeminiProvider, ProviderRequest, ProviderStatus
from bot_ia.providers.adapters import _stdlib_transport
from bot_ia.providers.errors import (
    MissingApiKeyError,
    ProviderDisabledError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRemoteError,
    ProviderTimeoutError,
)


class GeminiProviderTests(unittest.TestCase):
    def request(self) -> ProviderRequest:
        return ProviderRequest(
            "gemini",
            "gemini-test",
            "Di hola en una palabra.",
            16,
            1.0,
            "gemini-test-1",
            "controlled smoke shape",
        )

    def provider(self, transport):
        return GeminiProvider(
            key_loader=lambda _: "test-key",
            transport=transport,
        )

    def test_builds_gemini_request_and_normalizes_response(self) -> None:
        provider = self.provider(
            lambda _, headers, payload, __: {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": "hola",
                            }
                        ],
                    }
                ],
                "usage": {
                    "total_input_tokens": 10,
                    "total_output_tokens": 2,
                    "total_tokens": 12,
                },
            }
        )

        response = provider.generate(self.request())

        self.assertEqual(
            ProviderStatus.SUCCESS,
            response.status,
        )
        self.assertEqual(
            "hola",
            response.output_text,
        )

    def test_missing_key_is_typed(self) -> None:
        with self.assertRaises(MissingApiKeyError):
            GeminiProvider(
                key_loader=lambda _: None,
                transport=lambda *_: {},
            ).generate(self.request())

    def test_invalid_key_is_controlled_remote_error(self) -> None:
        with self.assertRaises(ProviderRemoteError):
            self.provider(
                lambda *_: (_ for _ in ()).throw(
                    ProviderRemoteError("provider returned HTTP 401")
                )
            ).generate(self.request())

    def test_timeout_is_typed(self) -> None:
        with self.assertRaises(ProviderTimeoutError):
            self.provider(
                lambda *_: (_ for _ in ()).throw(
                    ProviderTimeoutError("timeout")
                )
            ).generate(self.request())

    def test_malformed_response_is_typed(self) -> None:
        with self.assertRaises(ProviderProtocolError):
            self.provider(
                lambda *_: {"candidates": []}
            ).generate(self.request())

    def test_rate_limit_is_typed(self) -> None:
        error = HTTPError(
            "https://example.invalid",
            429,
            "Too Many Requests",
            {},
            BytesIO(),
        )
        try:
            with patch(
                "bot_ia.providers.adapters.urlopen",
                side_effect=error,
            ):
                with self.assertRaises(ProviderRateLimitError):
                    _stdlib_transport(
                        "https://example.invalid",
                        {},
                        {},
                        1.0,
                    )
        finally:
            error.close()

    def test_temporary_http_error_is_remote_error(self) -> None:
        error = HTTPError(
            "https://example.invalid",
            503,
            "Unavailable",
            {},
            BytesIO(),
        )
        try:
            with patch(
                "bot_ia.providers.adapters.urlopen",
                side_effect=error,
            ):
                with self.assertRaises(ProviderRemoteError):
                    _stdlib_transport(
                        "https://example.invalid",
                        {},
                        {},
                        1.0,
                    )
        finally:
            error.close()

    def test_disabled_provider_is_typed(self) -> None:
        with self.assertRaises(ProviderDisabledError):
            GeminiProvider(
                enabled=False,
                key_loader=lambda _: "test-key",
                transport=lambda *_: {},
            ).generate(self.request())


if __name__ == "__main__":
    unittest.main()