# -*- coding: utf-8 -*-
from pathlib import Path
import ast
import importlib
import unittest


class CafeOtakuGuiContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_gui_package_and_qss_are_present(self):
        package = self.ROOT / "src" / "gui" / "__init__.py"
        app = self.ROOT / "src" / "gui" / "app.py"
        styles = self.ROOT / "src" / "gui" / "styles.py"
        widgets = self.ROOT / "src" / "gui" / "widgets.py"

        for path in (package, app, styles, widgets):
            self.assertTrue(path.is_file(), str(path))
            self.assertTrue(
                path.read_text(encoding="utf-8").startswith("# -*- coding: utf-8 -*-")
            )

        qss = styles.read_text(encoding="utf-8")
        for token in ("#0f1117", "#161a23", "border-radius: 16px", "#c88cad"):
            self.assertIn(token, qss)

    def test_gui_uses_qtcore_and_exposes_all_six_profiles(self):
        source = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        qtcore_imports = [
            node
            for node in imports
            if node.module == "PySide6.QtCore"
        ]
        self.assertTrue(qtcore_imports)

        module = importlib.import_module("gui.app")
        expected = {"cari", "cami", "sunna", "chie", "chloe", "scarlet"}
        self.assertEqual(expected, {profile.bot_id for profile in module.BOT_PROFILES})
        self.assertEqual(expected, set(module.BOT_MAP))

    def test_gui_backend_bindings_are_explicit(self):
        source = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        for symbol in (
            "build_runtime",
            "WaitressSessionManager",
            "WebChatQueueManager",
            "TelegramPoller",
        ):
            self.assertIn(symbol, source)

        self.assertIn("runtime.build_tavern_manager(", source)
        self.assertIn("web_queue_manager=self._web_queue", source)
        self.assertIn("runtime.create_novel(", source)
        self.assertIn("self._tavern.force_rest(", source)
        self.assertIn("start_web_chat", source)
        self.assertIn("--web-chat-worker", source)


    def test_desktop_core_delegates_to_qt(self):
        source = (
            self.ROOT / "desktop_entry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from gui.app import main as qt_main", source)
        self.assertIn("return qt_main()", source)
        self.assertIn("outbox_store=outbox_store", source)


if __name__ == "__main__":
    unittest.main()
