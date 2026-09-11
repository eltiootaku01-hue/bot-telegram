import ast
from pathlib import Path
import unittest


class DesktopEntryTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).resolve().parents[1].joinpath("desktop_entry.py").read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_entrypoint_has_explicit_telegram_worker(self):
        self.assertIn("--telegram-worker", self.source)
        self.assertIn("TelegramApiClient", self.source)
        self.assertIn("TelegramPoller", self.source)

    def test_gui_worker_never_calls_tk_from_background_thread(self):
        self.assertIn("self._ui_queue.put((\"response\"", self.source)
        self.assertIn("self.root.after(50, self._drain_ui_queue)", self.source)
        handle = next(node for node in ast.walk(self.tree) if isinstance(node, ast.FunctionDef) and node.name == "handle_message")
        calls = [node for node in ast.walk(handle) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(call.func, ast.Attribute) and call.func.attr == "after" for call in calls))
        self.assertFalse(any(isinstance(call.func, ast.Attribute) and call.func.attr in {"configure", "insert", "delete"} for call in calls))

    def test_worker_entrypoint_has_failure_log(self):
        self.assertIn("telegram.log", self.source)
        self.assertIn("traceback.format_exc()", self.source)


if __name__ == "__main__":
    unittest.main()
