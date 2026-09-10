import importlib
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


if __name__ == "__main__":
    unittest.main()
