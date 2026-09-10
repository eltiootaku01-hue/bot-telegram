import tomllib
from pathlib import Path
import unittest


class ProviderDefaultTests(unittest.TestCase):
    def test_runtime_does_not_enable_resource_heavy_local_ollama_by_default(self) -> None:
        path = Path(__file__).resolve().parents[1] / "config" / "runtime.toml"
        with path.open("rb") as handle:
            config = tomllib.load(handle)
        ollama = config["providers"]["ollama"]
        gemini = config["providers"]["gemini"]
        self.assertFalse(ollama["enabled"])
        self.assertEqual("qwen3:1b", ollama["model"])
        self.assertTrue(gemini["enabled"])


if __name__ == "__main__":
    unittest.main()
