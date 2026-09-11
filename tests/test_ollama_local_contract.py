import unittest

from bot_ia.providers.adapters import OllamaProvider
from bot_ia.providers.models import ProviderRequest


class OllamaLocalContractTests(unittest.TestCase):
    def test_ollama_needs_no_remote_api_key_and_keeps_model_ephemeral(self):
        provider = OllamaProvider(enabled=True, default_model="qwen3:1.7b", api_key_env=None)
        request = ProviderRequest(
            provider="ollama",
            model="qwen3:1.7b",
            input_text="hola",
            max_output_tokens=32,
            timeout_seconds=5,
            request_id="ollama-test",
            escalation_reason="local smoke test",
        )
        self.assertEqual(provider._headers(None), {"Content-Type": "application/json"})
        payload = provider._payload(request)
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["keep_alive"], 0)
        self.assertEqual(payload["model"], "qwen3:1.7b")
        self.assertEqual(payload["options"]["num_predict"], 32)


if __name__ == "__main__":
    unittest.main()
