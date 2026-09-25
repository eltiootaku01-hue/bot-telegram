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

    def test_gemini_lobby_worker_and_credentials_contract(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")
        for token in (
            "class GeminiLobbyWorker(QObject):",
            "finished = Signal(str)",
            "failed = Signal(str)",
            "launch_persistent_context(",
            '"./browser_data"',
            '"--disable-blink-features=AutomationControlled"',
            '"--hide-crash-restore-bubble"',
            '"--no-sandbox"',
            "div[contenteditable='true']",
            '"model-response"',
            "thread.started.connect(worker.run)",
            "worker.finished.connect(self._gemini_done)",
            "worker.failed.connect(self._gemini_failed)",
            "worker.finished.connect(thread.quit)",
            "worker.failed.connect(thread.quit)",
            "thread.finished.connect(thread.deleteLater)",
            "save_and_verify_credentials",
            "load_dotenv",
            "set_values",
        ):
            self.assertIn(token, source)

    def test_python_dotenv_dependency_is_declared(self):
        pyproject = (self.ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("python-dotenv>=1.1,<2", pyproject)

    def test_command_center_is_runtime_window_and_legacy_free(self):
        source = (self.ROOT / "src" / "gui" / "app.py").read_text(
            encoding="utf-8"
        )
        for token in (
            "class CommandCenterWindow(QMainWindow):",
            "CafeOtakuWindow = CommandCenterWindow",
            "class SystemDiagnosticWorker(QObject):",
            "finished = Signal(dict)",
            "failed = Signal(str)",
            "_show_diagnostic_dialog",
            "_start_system_diagnostic",
            "json.dumps",
            "reset_to_factory",
            "window = CommandCenterWindow()",
            "sync_playwright",
            "launch_persistent_context(",
            '"./browser_data"',
            '"model-response"',
            "thread.started.connect(worker.run)",
            "worker.finished.connect(self._gemini_done)",
            "worker.failed.connect(self._gemini_failed)",
            "worker.finished.connect(thread.quit)",
            "worker.failed.connect(thread.quit)",
            "worker.finished.connect(worker.deleteLater)",
            "worker.failed.connect(worker.deleteLater)",
            "thread.finished.connect(thread.deleteLater)",
            "DynamicConfigManager",
            "load_dotenv",
            "set_values",
            "BOT_TOKEN_{profile.bot_id.upper()}",
            "PROVEEDORES LLM / APIs",
            "Restablecer Configuración de Fábrica",
            "config_manager.set_values",
        ):
            self.assertIn(token, source)

        self.assertNotIn("keyring", source)
        self.assertNotIn("DynamicLLMPool", source)

    def test_env_example_contains_all_bot_credentials(self):
        source = (self.ROOT / ".env.example").read_text(encoding="utf-8")
        for bot_id in (
            "CARI",
            "CAMI",
            "SUNNA",
            "CHIE",
            "CHLOE",
            "SCARLET",
        ):
            self.assertIn(f"BOT_TOKEN_{bot_id}=", source)

    def test_async_qt_entrypoint_and_shutdown_contract_are_present(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")

        for token in (
            "async def _async_main(",
            "from qasync import QEventLoop",
            "asyncio.run(",
            "loop_factory=QEventLoop",
            "app.aboutToQuit.connect(quit_event.set)",
            "await window.shutdown_async_engine()",
            "WebQueueManager()",
            "TaskOrchestrator(",
            "web_worker_callback=web_queue.process_task",
            "asyncio.create_task(",
        ):
            self.assertIn(token, source)

        self.assertIn(
            'python_version < "3.14"',
            (self.ROOT / "pyproject.toml").read_text(
                encoding="utf-8"
            ),
        )

    def test_qt_fallback_is_guarded_for_python_314(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "and sys.version_info < (3, 14)",
            source,
        )
        self.assertIn(
            "return _qt_main(app)",
            source,
        )


    def test_desktop_core_delegates_to_qt(self):
        source = (
            self.ROOT / "desktop_entry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from gui.app import main as qt_main", source)
        self.assertIn("return qt_main()", source)
        self.assertIn("outbox_store=outbox_store", source)


if __name__ == "__main__":
    unittest.main()
