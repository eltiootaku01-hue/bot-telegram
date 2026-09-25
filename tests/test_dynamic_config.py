# -*- coding: utf-8 -*-
from pathlib import Path
import os
import tempfile
import unittest

from core.config import DynamicConfigManager


class DynamicConfigManagerTests(unittest.TestCase):
    def test_set_values_persists_and_updates_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env.example").write_text(
                "BOT_IA_PROVIDER=openai\nBOT_TOKEN_CARI=\n",
                encoding="utf-8",
            )
            manager = DynamicConfigManager(root)
            previous_provider = os.environ.get("BOT_IA_PROVIDER")
            previous_token = os.environ.get("BOT_TOKEN_CARI")
            try:
                manager.set_values(
                    {
                        "BOT_IA_PROVIDER": "groq",
                        "BOT_TOKEN_CARI": "123:test-token",
                    }
                )

                self.assertEqual(
                    "groq",
                    os.environ["BOT_IA_PROVIDER"],
                )
                self.assertEqual(
                    "123:test-token",
                    os.environ["BOT_TOKEN_CARI"],
                )
                text = (root / ".env").read_text(encoding="utf-8")
                self.assertIn("BOT_IA_PROVIDER=", text)
                self.assertIn("BOT_TOKEN_CARI=", text)
                self.assertEqual(
                    "123:test-token",
                    manager.get("BOT_TOKEN_CARI"),
                )
            finally:
                if previous_provider is None:
                    os.environ.pop("BOT_IA_PROVIDER", None)
                else:
                    os.environ["BOT_IA_PROVIDER"] = previous_provider
                if previous_token is None:
                    os.environ.pop("BOT_TOKEN_CARI", None)
                else:
                    os.environ["BOT_TOKEN_CARI"] = previous_token

    def test_factory_reset_removes_custom_keys_and_restores_example(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env.example").write_text(
                "BOT_IA_PROVIDER=openai\nBOT_TOKEN_CARI=\n",
                encoding="utf-8",
            )
            (root / ".env").write_text(
                "BOT_IA_PROVIDER=groq\n"
                "BOT_TOKEN_CARI=old-token\n"
                "CUSTOM_KEY=remove-me\n",
                encoding="utf-8",
            )
            os.environ["CUSTOM_KEY"] = "remove-me"
            os.environ["BOT_IA_PROVIDER"] = "groq"
            try:
                manager = DynamicConfigManager(root)
                manager.reset_to_factory()

                self.assertNotIn(
                    "CUSTOM_KEY",
                    os.environ,
                )
                self.assertEqual(
                    "openai",
                    os.environ["BOT_IA_PROVIDER"],
                )
                self.assertEqual(
                    "",
                    os.environ["BOT_TOKEN_CARI"],
                )
                self.assertEqual(
                    (root / ".env.example").read_text(encoding="utf-8"),
                    (root / ".env").read_text(encoding="utf-8"),
                )
            finally:
                os.environ.pop("CUSTOM_KEY", None)
                os.environ.pop("BOT_IA_PROVIDER", None)
                os.environ.pop("BOT_TOKEN_CARI", None)


if __name__ == "__main__":
    unittest.main()
