import ast
import importlib
from pathlib import Path
import unittest


class DesktopInterfaceTests(unittest.TestCase):
    def test_desktop_module_exposes_visual_menu_without_starting_window(self):
        module = importlib.import_module("desktop")
        self.assertIn("📖 Novela", module.MENU_ACTIONS)
        self.assertIn("📊 Estado API", module.MENU_ACTIONS)
        self.assertIsNone(module.MENU_ACTIONS["🧰 Destrabar escena"])

    def test_telegram_launcher_has_explicit_process_entrypoint(self):
        module = importlib.import_module("desktop")
        self.assertTrue(hasattr(module.BotIADesktop, "start_telegram"))

    def test_desktop_script_has_real_main_entrypoint(self):
        source = Path(__file__).resolve().parents[1].joinpath("desktop.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(
            any(
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
                and any(isinstance(op, ast.Eq) for op in node.test.ops)
                and any(
                    isinstance(value, ast.Constant) and value.value == "__main__"
                    for value in node.test.comparators
                )
                for node in ast.walk(tree)
            ),
            "desktop.py debe conservar el guard __name__ == '__main__' para que BOT-IA-Core arranque.",
        )


if __name__ == "__main__":
    unittest.main()
