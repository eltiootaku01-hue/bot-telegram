# -*- coding: utf-8 -*-
import ast
from pathlib import Path
import unittest


class GuiBridgeContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_gui_bridge_has_utf8_header_and_qtcore(self):
        path = self.ROOT / "src" / "gui" / "gui_bridge.py"
        source = path.read_text(encoding="utf-8")

        self.assertTrue(
            source.startswith("# -*- coding: utf-8 -*-")
        )

        tree = ast.parse(source)
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        self.assertTrue(
            any(
                node.module == "PySide6.QtCore"
                for node in imports
            )
        )

    def test_gui_bridge_declares_signals_cards_and_mocha_palette(self):
        source = (
            self.ROOT / "src" / "gui" / "gui_bridge.py"
        ).read_text(encoding="utf-8")

        for token in (
            "class WorkerSignals(QObject):",
            "status_changed = Signal(str, str)",
            "message_received = Signal(str, str)",
            "class WaitressCard(QFrame):",
            "class DarkCozyWindow(QMainWindow):",
            "QFrame#WaitressCard",
            "#1e1e2e",
            "#2a2a3d",
            "#cba6f7",
            "#a6e3a1",
        ):
            self.assertIn(token, source)

    def test_gui_bridge_contains_exact_six_waitress_ids(self):
        source = (
            self.ROOT / "src" / "gui" / "gui_bridge.py"
        ).read_text(encoding="utf-8")
        expected = {
            "cari",
            "cami",
            "sunna",
            "chie",
            "chloe",
            "scarlet",
        }

        for waitress_id in expected:
            self.assertIn(f'"{waitress_id}"', source)


if __name__ == "__main__":
    unittest.main()
