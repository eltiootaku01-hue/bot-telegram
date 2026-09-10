from pathlib import Path
import unittest

from bot_ia.config import load_default_runtime_config


class ProviderDefaultTests(unittest.TestCase):
    def test_runtime_does_not_enable_resource_heavy_local_ollama_by_default(self) -> None:
        config = load_default_runtime_config(Path(__file__).resolve().parents[1])
        ollama = config.provider("ollama")
        gemini = config.provider("gemini")
        self.assertFalse(ollama.enabled)
        self.assertEqual("qwen3:1b", ollama.model)
        self.assertTrue(gemini.enabled)


if __name__ == "__main__":
    unittest.main()
