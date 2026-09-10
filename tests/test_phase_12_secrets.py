import unittest

from bot_ia.config import SecretLoader


class Phase12SecretsTests(unittest.TestCase):
    def test_secret_loader_reads_configured_secret(self) -> None:
        loader = SecretLoader({"OPENAI_API_KEY": "test-secret"})
        self.assertEqual("test-secret", loader.get("OPENAI_API_KEY"))

    def test_secret_loader_returns_none_when_missing(self) -> None:
        loader = SecretLoader({})
        self.assertIsNone(loader.get("OPENAI_API_KEY"))

    def test_secret_loader_treats_blank_as_missing(self) -> None:
        loader = SecretLoader({"OPENAI_API_KEY": "   "})
        self.assertIsNone(loader.get("OPENAI_API_KEY"))

    def test_require_raises_controlled_error(self) -> None:
        loader = SecretLoader({})
        with self.assertRaises(RuntimeError) as error:
            loader.require("OPENAI_API_KEY")
        self.assertEqual("required secret is not configured: OPENAI_API_KEY", str(error.exception))

    def test_secret_value_is_not_part_of_error(self) -> None:
        loader = SecretLoader({"OPENAI_API_KEY": "super-secret-value"})
        with self.assertRaises(RuntimeError) as error:
            loader.require("GROQ_API_KEY")
        self.assertNotIn("super-secret-value", str(error.exception))

    def test_secret_loader_method_matches_provider_key_loader_contract(self) -> None:
        loader = SecretLoader({"OPENAI_API_KEY": "test-secret"})
        key_loader = loader.get
        self.assertEqual("test-secret", key_loader("OPENAI_API_KEY"))
        self.assertIsNone(key_loader("GROQ_API_KEY"))

    def test_openai_provider_uses_default_secret_loader(self) -> None:
        from bot_ia.providers import OpenAIProvider, ProviderRequest
        calls = []

        class FakeSecretLoader:
            def get(self, name: str) -> str | None:
                calls.append(name)
                return "test-secret"

        module = __import__("bot_ia.providers.adapters", fromlist=["SecretLoader"])
        original_loader = module.SecretLoader
        try:
            module.SecretLoader = FakeSecretLoader
            provider = OpenAIProvider(transport=lambda *_: {"output_text": "ok"})
            response = provider.generate(ProviderRequest("openai", "openai-test", "hola", 16, 1.0, "secret-test", "test"))
            self.assertEqual("ok", response.output_text)
            self.assertEqual(["OPENAI_API_KEY"], calls)
        finally:
            module.SecretLoader = original_loader


if __name__ == "__main__":
    unittest.main()
