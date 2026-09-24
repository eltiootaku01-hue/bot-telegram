# -*- coding: utf-8 -*-
import ast
from pathlib import Path
import unittest


class DesktopEntryTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("desktop_entry.py")
            .read_text(encoding="utf-8")
        )
        self.tree = ast.parse(self.source)

    def test_entrypoint_has_explicit_telegram_worker_and_durable_outbox(self):
        self.assertIn("--telegram-worker", self.source)
        self.assertIn("TelegramApiClient", self.source)
        self.assertIn("TelegramPoller", self.source)
        self.assertIn("TelegramOutboxStore", self.source)
        self.assertIn("outbox_store=outbox_store", self.source)

    def test_gui_entrypoint_delegates_to_qt_app(self):
        self.assertIn("from gui.app import main as qt_main", self.source)
        self.assertIn("return qt_main()", self.source)
        self.assertNotIn("import tkinter", self.source)
        self.assertNotIn("_install_threadsafe_desktop", self.source)

        main = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "main"
        )
        calls = [
            node
            for node in ast.walk(main)
            if isinstance(node, ast.Call)
        ]
        self.assertTrue(
            any(
                isinstance(call.func, ast.Name)
                and call.func.id == "qt_main"
                for call in calls
            )
        )

    def test_workers_close_runtime_in_finally(self):
        self.assertIn("finally:", self.source)
        self.assertIn("runtime.memory_store.close()", self.source)


if __name__ == "__main__":
    unittest.main()
