import unittest

from bot_ia.config import SecretLoader


class Phase12SecretsTests(unittest.TestCase):
    def test_secret_loader_reads_configured_secret(self) -> None:
        loader = SecretLoader({"GEMINI_API_KEY": "test-secret"})

        self.assertEqual(
            "test-secret",
            loader.get("GEMINI_API_KEY"),
        )

    def test_secret_loader_returns_none_when_missing(self) -> None:
        loader = SecretLoader({})

        self.assertIsNone(
            loader.get("GEMINI_API_KEY"),
        )

    def test_secret_loader_treats_blank_as_missing(self) -> None:
        loader = SecretLoader({"GEMINI_API_KEY": "   "})

        self.assertIsNone(
            loader.get("GEMINI_API_KEY"),
        )

    def test_require_raises_controlled_error(self) -> None:
        loader = SecretLoader({})

        with self.assertRaises(RuntimeError) as error:
            loader.require("GEMINI_API_KEY")

        self.assertEqual(
            "required secret is not configured: GEMINI_API_KEY",
            str(error.exception),
        )

    def test_secret_value_is_not_part_of_error(self) -> None:
        loader = SecretLoader({"GEMINI_API_KEY": "super-secret-value"})

        with self.assertRaises(RuntimeError) as error:
            loader.require("OPENAI_API_KEY")

        self.assertNotIn(
            "super-secret-value",
            str(error.exception),
        )

    def test_secret_loader_method_matches_provider_key_loader_contract(self) -> None:
        loader = SecretLoader({"GEMINI_API_KEY": "test-secret"})

        key_loader = loader.get

        self.assertEqual(
            "test-secret",
            key_loader("GEMINI_API_KEY"),
        )

        self.assertIsNone(
            key_loader("OPENAI_API_KEY"),
        )
    def test_gemini_provider_uses_default_secret_loader(self) -> None:
        from bot_ia.providers import GeminiProvider, ProviderRequest

        calls = []

        class FakeSecretLoader:
            def get(self, name: str) -> str | None:
                calls.append(name)
                return "test-secret"

        original_loader = __import__(
            "bot_ia.providers.adapters",
            fromlist=["SecretLoader"],
        ).SecretLoader

        try:
            module = __import__(
                "bot_ia.providers.adapters",
                fromlist=["SecretLoader"],
            )
            module.SecretLoader = FakeSecretLoader

            provider = GeminiProvider(
                transport=lambda *_: {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "ok"}]
                            }
                        }
                    ]
                }
            )

            request = ProviderRequest(
                "gemini",
                "gemini-test",
                "hola",
                16,
                1.0,
                "secret-test",
                "test",
            )

            response = provider.generate(request)

            self.assertEqual("ok", response.output_text)
            self.assertEqual(["GEMINI_API_KEY"], calls)
        finally:
            module.SecretLoader = original_loader

if __name__ == "__main__":
    unittest.main()