from pathlib import Path
import tempfile
import unittest

from bot_ia.config import load_default_runtime_config
from bot_ia.providers import (
    OllamaProvider,
    ProviderRequest,
    ProviderStatus,
)


class FakeOllamaTransport:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {
            "response": "Respuesta simulada de Qwen.",
            "prompt_eval_count": 10,
            "eval_count": 7,
        }


class OllamaProviderTests(unittest.TestCase):
    def test_ollama_does_not_require_api_key(self) -> None:
        transport = FakeOllamaTransport()
        provider = OllamaProvider(
            key_loader=lambda _: None,
            transport=transport,
        )

        response = provider.generate(
            ProviderRequest(
                "ollama",
                "qwen3:1.7b-q4_K_M",
                "Responde: OK",
                32,
                5.0,
                "test-ollama-001",
                "test",
            )
        )

        self.assertEqual(
            ProviderStatus.SUCCESS,
            response.status,
        )
        self.assertEqual(
            "Respuesta simulada de Qwen.",
            response.output_text,
        )

    def test_ollama_builds_expected_payload(self) -> None:
        transport = FakeOllamaTransport()
        provider = OllamaProvider(
            transport=transport,
        )

        provider.generate(
            ProviderRequest(
                "ollama",
                "qwen3:1.7b-q4_K_M",
                "Responde: OK",
                64,
                7.5,
                "test-ollama-002",
                "test",
            )
        )

        self.assertEqual(1, len(transport.calls))

        call = transport.calls[0]

        self.assertEqual(
            "http://localhost:11434/api/generate",
            call["url"],
        )
        self.assertEqual(
            "application/json",
            call["headers"]["Content-Type"],
        )
        self.assertEqual(
            7.5,
            call["timeout"],
        )

        self.assertEqual(
            {
                "model": "qwen3:1.7b-q4_K_M",
                "prompt": "Responde: OK",
                "stream": False,
                "think": False,
                "keep_alive": 0,
                "options": {
                    "num_predict": 64,
                },
            },
            call["payload"],
        )

    def test_ollama_preserves_usage(self) -> None:
        provider = OllamaProvider(
            transport=FakeOllamaTransport(),
        )

        response = provider.generate(
            ProviderRequest(
                "ollama",
                "qwen3:1.7b-q4_K_M",
                "Responde: OK",
                32,
                5.0,
                "test-ollama-003",
                "test",
            )
        )

        self.assertEqual(10, response.usage.input_tokens)
        self.assertEqual(7, response.usage.output_tokens)
        self.assertEqual(17, response.usage.total_tokens)

    def test_runtime_config_contains_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_dir = root / "config"
            config_dir.mkdir()

            (config_dir / "runtime.toml").write_text(
                """
[providers.ollama]
enabled = true
model = "qwen3:1.7b-q4_K_M"
max_output_tokens = 256
timeout_seconds = 120.0
fallback = ""
""".strip(),
                encoding="utf-8",
            )

            config = load_default_runtime_config(root)

        ollama = config.provider("ollama")

        self.assertTrue(ollama.enabled)
        self.assertEqual(
            "qwen3:1.7b-q4_K_M",
            ollama.model,
        )
        self.assertEqual(
            256,
            ollama.max_output_tokens,
        )
        self.assertEqual(
            120.0,
            ollama.timeout_seconds,
        )
        self.assertIsNone(
            ollama.fallback_provider,
        )


if __name__ == "__main__":
    unittest.main()
