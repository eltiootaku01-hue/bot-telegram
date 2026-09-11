import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bot_ia.config import load_default_runtime_config


class LocalModelPolicyTests(unittest.TestCase):
    def test_ollama_is_disabled_and_pins_compact_q4_baseline(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        config = load_default_runtime_config(project_root)
        ollama = next(provider for provider in config.providers if provider.provider_id == "ollama")

        self.assertFalse(ollama.enabled)
        self.assertEqual(ollama.model, "qwen3:1.7b-q4_K_M")
        self.assertLessEqual(ollama.max_output_tokens, 256)
        self.assertGreaterEqual(ollama.timeout_seconds, 60.0)

    def test_explicit_ollama_selection_enables_only_local_provider(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with patch.dict(os.environ, {"BOT_IA_PROVIDER": "ollama", "BOT_IA_ENABLE_LOCAL_OLLAMA": "true"}, clear=False):
            config = load_default_runtime_config(project_root)
        ollama = next(provider for provider in config.providers if provider.provider_id == "ollama")
        self.assertTrue(ollama.enabled)
        self.assertTrue(next(provider for provider in config.providers if provider.provider_id == "openai").enabled)


if __name__ == "__main__":
    unittest.main()
