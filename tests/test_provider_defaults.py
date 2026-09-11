import tomllib
from pathlib import Path
import unittest


class ProviderDefaultTests(unittest.TestCase):
    def test_runtime_uses_remote_providers_and_keeps_ollama_off(self) -> None:
        path = Path(__file__).resolve().parents[1] / "config" / "runtime.toml"
        with path.open("rb") as handle:
            config = tomllib.load(handle)
        providers = config["providers"]
        ollama = providers["ollama"]
        self.assertTrue(providers["openai"]["enabled"])
        self.assertTrue(providers["groq"]["enabled"])
        self.assertFalse(providers["coze"]["enabled"])
        self.assertFalse(ollama["enabled"])
        self.assertEqual("qwen3:1.7b", ollama["model"])
        self.assertNotIn("gemini", providers)


if __name__ == "__main__":
    unittest.main()
