from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from bot_ia.config.loader import _resolve_universe_path
from bot_ia.interfaces.telegram_novel_v2 import EDITOR_MENU, EDITOR_REQUESTS, TelegramNovelV2Adapter


class NovelUiAndRuntimeTests(unittest.TestCase):
    def test_future_universe_without_env_is_allowed_as_unconfigured_path(self):
        old = os.environ.pop("BOT_IA_TEST_FUTURE_ROOT", None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = _resolve_universe_path("env:BOT_IA_TEST_FUTURE_ROOT", config_dir=Path(directory))
                self.assertFalse(path.is_dir())
                self.assertIn("BOT_IA_TEST_FUTURE_ROOT", path.parts)
        finally:
            if old is not None:
                os.environ["BOT_IA_TEST_FUTURE_ROOT"] = old

    def test_editor_menu_has_all_declared_actions(self):
        labels = [callback for row in EDITOR_MENU for callback in row]
        callbacks = {data for _, data in labels}
        self.assertEqual(callbacks - {"menu:main"}, set(EDITOR_REQUESTS))
        self.assertEqual(len(EDITOR_REQUESTS), 7)

    def test_novel_menu_exposes_research(self):
        callbacks = {data for row in TelegramNovelV2Adapter.MAIN_MENU for _, data in row}
        self.assertIn("menu:research", callbacks)
        self.assertLessEqual(max(len(data) for data in callbacks), 64)


if __name__ == "__main__":
    unittest.main()
