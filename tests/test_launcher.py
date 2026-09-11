import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import launcher


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class LauncherOllamaTests(unittest.TestCase):
    def test_ollama_is_selectable_without_api_key(self):
        self.assertEqual(("ollama", None), launcher.PROVIDERS["Ollama local"])

    def test_ollama_probe_detects_recommended_model(self):
        response = _FakeResponse({"models": [{"name": launcher.OLLAMA_MODEL}]})
        with patch("launcher.urlopen", return_value=response):
            reachable, model_present = launcher._ollama_probe()
        self.assertTrue(reachable)
        self.assertTrue(model_present)

    def test_ollama_probe_degrades_without_ollama(self):
        with patch("launcher.urlopen", side_effect=OSError("connection refused")):
            reachable, model_present = launcher._ollama_probe()
        self.assertFalse(reachable)
        self.assertFalse(model_present)

    def test_write_env_selects_ollama_and_does_not_store_a_key(self):
        with tempfile.TemporaryDirectory() as temp:
            env_path = Path(temp) / ".env"
            old_env_path = launcher.ENV_PATH
            launcher.ENV_PATH = env_path
            try:
                launcher._write_env(
                    universe="one_neko_punch",
                    library=Path(temp) / "biblioteca",
                    provider="Ollama local",
                    api_key="should-not-be-used",
                    telegram_token="",
                )
                values = launcher._read_env()
            finally:
                launcher.ENV_PATH = old_env_path

        self.assertEqual("ollama", values["BOT_IA_PROVIDER"])
        self.assertEqual(launcher.OLLAMA_BASE_URL, values["OLLAMA_BASE_URL"])
        self.assertEqual("", values["OPENAI_API_KEY"])
        self.assertEqual("", values["GROQ_API_KEY"])
        self.assertEqual("", values["OPENROUTER_API_KEY"])


if __name__ == "__main__":
    unittest.main()
