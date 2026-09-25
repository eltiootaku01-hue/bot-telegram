# -*- coding: utf-8 -*-
from pathlib import Path
import ast
import os
import importlib
import unittest
from unittest.mock import patch


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

    def test_hybrid_playwright_and_ultra_lightweight_contract(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")

        for token in (
            'INITIAL_SETUP_MODE_ENV = "INITIAL_SETUP_MODE"',
            "def _initial_setup_mode()",
            "def _lightweight_browser_args(*, headless: bool)",
            '"--headless=new"',
            '"--disable-gpu"',
            '"--disable-dev-shm-usage"',
            '"--no-first-run"',
            '"--no-sandbox"',
            '"--disable-extensions"',
            '"--disable-background-networking"',
            '"--disable-background-timer-throttling"',
            '"--disable-client-side-phishing-detection"',
            '"--disable-default-apps"',
            '"--disable-hang-monitor"',
            '"--disable-popup-blocking"',
            '"--disable-prompt-on-repost"',
            '"--disable-sync"',
            '"--disable-translate"',
            '"--metrics-recording-only"',
            '"--no-zygote"',
            '"--blink-settings=imagesEnabled=false"',
            "PLAYWRIGHT_DISABLE_IMAGES",
            "setup_mode",
            "headless=self.headless",
            "SETUP_LOGIN_TIMEOUT_MS = 300_000",
            "class ManualBrowserSetupWorker(QObject):",
            "headless=False",
            "no_viewport=True",
            "launch_persistent_context(",
            "storage_state.json",
            "indexed_db=True",
            "self._manual_setup_thread",
            "self._finish_manual_setup_mode",
            "🔑 Iniciar Sesión Manual",
            "_enable_manual_setup_mode",
            "_lightweight_browser_args(headless=True)",
        ):
            self.assertIn(token, source)

        module = __import__(
            "gui.app",
            fromlist=["_initial_setup_mode", "_lightweight_browser_args"],
        )

        with patch.dict(
            os.environ,
            {
                "INITIAL_SETUP_MODE": "false",
                "PLAYWRIGHT_DISABLE_IMAGES": "false",
                "PLAYWRIGHT_SINGLE_PROCESS": "false",
            },
            clear=False,
        ):
            self.assertFalse(module._initial_setup_mode())
            args = module._lightweight_browser_args(headless=True)
            self.assertIn("--headless=new", args)
            self.assertIn("--disable-gpu", args)

        with patch.dict(
            os.environ,
            {"INITIAL_SETUP_MODE": "true"},
            clear=False,
        ):
            self.assertTrue(module._initial_setup_mode())
            args = module._lightweight_browser_args(headless=False)
            self.assertNotIn("--headless=new", args)
            self.assertIn("--disable-extensions", args)

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
        self.assertNotIn("self.signals.web_result.connect(\n            self._on_web_result", source)
        self.assertIn("self.signals.web_result.connect(\n            self._on_web_state", source)
        self.assertIn("self.signals.web_failed.connect(\n            self._on_web_state", source)
        self.assertNotIn("self.signals.web_failed.connect(\n            self._on_web_failed", source)

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


    def test_multi_provider_isolation_and_lightweight_chromium_contract(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")

        for token in (
            "class ProviderWebSpec:",
            "PROVIDER_WEB_SPECS = {",
            '"gemini": ProviderWebSpec(',
            '"chatgpt": ProviderWebSpec(',
            '"grok_claude": ProviderWebSpec(',
            "MATRIX_INITIALIZATION_ORDER =",
            '"./browser_data/cari"',
            '"./browser_data/cami"',
            '"./browser_data/sunna"',
            '"./browser_data/chie"',
            'provider.addItem("Google Gemini", "gemini")',
            'provider.addItem("OpenAI ChatGPT", "chatgpt")',
            'provider.addItem("Microsoft Copilot", "copilot")',
            'provider.addItem("Grok / Claude", "grok_claude")',
            "BOT_IA_GROK_CLAUDE_URL",
            "new_chat_selectors",
            "response_selectors",
            "LIGHTWEIGHT_CHROMIUM_ARGS",
            '"--disable-gpu"',
            '"--disable-dev-shm-usage"',
            '"--no-first-run"',
            '"--disable-extensions"',
            '"--renderer-process-limit=2"',
            '"--disable-features=Translate,BackForwardCache"',
            "PLAYWRIGHT_SINGLE_PROCESS",
            "chromium.launch_persistent_context(",
            "headless=False",
            "worker.ready.connect(self._on_bot_ready)",
            "thread.finished.connect(thread.deleteLater)",
            "self._start_next()",
            "⛓ Ejecutar cadena 4 bots",
            "🔑 Iniciar Sesión Manual",
            "self.lobby_manual_login_button",
            "matrix_grid.addWidget(",
            "layout.addWidget(matrix)",
            "def _enable_manual_setup_mode",
        ):
            self.assertIn(token, source)

        module = __import__(
            "gui.app",
            fromlist=[
                "MATRIX_BOT_SPECS",
                "MATRIX_INITIALIZATION_ORDER",
                "PROVIDER_WEB_SPECS",
            ],
        )
        self.assertEqual(
            ["cari", "sunna", "cami", "chie"],
            [spec.bot_id for spec in module.MATRIX_BOT_SPECS],
        )
        self.assertEqual(
            ("cari", "cami", "sunna", "chie"),
            module.MATRIX_INITIALIZATION_ORDER,
        )
        self.assertEqual(
            {"gemini", "chatgpt", "copilot", "grok_claude"},
            set(module.PROVIDER_WEB_SPECS),
        )
        self.assertEqual(
            [
                "./browser_data/cari",
                "./browser_data/sunna",
                "./browser_data/cami",
                "./browser_data/chie",
            ],
            [spec.browser_profile for spec in module.MATRIX_BOT_SPECS],
        )

    def test_expandable_bot_viewers_contract(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")

        for token in (
            "class BotExpandedDialog(QDialog):",
            "self._expanded_bot_dialogs",
            "tile.clicked_bot.connect(self._on_bot_tile_clicked)",
            'QPushButton("🔍 Ampliar")',
            "self._open_bot_expanded(bot_id)",
            "dialog.show()",
            "dialog.raise_()",
            "dialog.activateWindow()",
            "send_requested = Signal(str, str)",
            "manual_requested = Signal(str)",
            "start_requested = Signal(str)",
            "dialog.history.setPlainText(log.toPlainText())",
            "def _sync_expanded_bot(self, bot_id: str)",
            "self._sync_expanded_bot(bot_id)",
            "dialog.hide()",
            "dialog.deleteLater()",
        ):
            self.assertIn(token, source)

        self.assertEqual(
            1,
            source.count(
                "def _enable_manual_setup_mode("
            ),
        )

    def test_manual_login_uses_native_chromium_and_resets_to_headless(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")

        for token in (
            "class ManualBrowserSetupWorker(QObject):",
            "headless=False",
            "no_viewport=True",
            "launch_persistent_context(",
            "str(profile_path)",
            'profile_path / "storage_state.json"',
            "indexed_db=True",
            "TIMEOUT_MS = 300_000",
            "current_thread.isInterruptionRequested()",
            'os.environ[INITIAL_SETUP_MODE_ENV] = "false"',
            '{INITIAL_SETUP_MODE_ENV: "false"}',
            "self._enable_manual_setup_mode(bot_id)",
            "manual_requested.connect(",
        ):
            self.assertIn(token, source)

        self.assertIn(
            "browser_data/",
            (self.ROOT / ".gitignore").read_text(encoding="utf-8"),
        )

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


    def test_admin_provisioning_is_idempotent_and_creates_base_structure(self):
        import json
        import tempfile
        from gui.admin_provisioning import (
            AdminProvisioner,
            DEFAULT_ADMIN_VALUES,
        )

        class FakeConfig:
            def __init__(self):
                self.values = {}

            def set_values(self, values):
                self.values.update({str(k): str(v) for k, v in values.items()})
                return dict(self.values)

        with tempfile.TemporaryDirectory() as temp_dir:
            provisioner = AdminProvisioner(temp_dir)
            config = FakeConfig()
            first = provisioner.activate(config)
            self.assertEqual(
                {"animals_city", "cafe_otaku", "taberna"},
                set(first["panels"]),
            )
            self.assertEqual(
                {"animals_city", "cafe_otaku", "taberna"},
                set(first["themes"]),
            )
            self.assertEqual(set(DEFAULT_ADMIN_VALUES), set(config.values))

            structure_path = Path(first["path"])
            self.assertTrue(structure_path.is_file())
            payload = json.loads(structure_path.read_text(encoding="utf-8"))
            self.assertEqual(3, len(payload["panels"]))
            self.assertEqual(3, len(payload["themes"]))

            payload["panels"][0]["description"] = "personalizado"
            structure_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            second = provisioner.activate(config)
            self.assertFalse(second["config_created"])
            payload_after = json.loads(
                structure_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                "personalizado",
                payload_after["panels"][0]["description"],
            )

    def test_admin_button_contract_and_confirmation_message(self):
        source = (self.ROOT / "src" / "gui" / "app.py").read_text(
            encoding="utf-8"
        )
        for token in (
            'QPushButton("👑 Soy Admin")',
            "self.admin_button.setCheckable(True)",
            "self.admin_button.clicked.connect(self._activate_admin_mode)",
            "self.admin_provisioner = AdminProvisioner(ROOT)",
            "self.admin_provisioner.activate(self.config_manager)",
            "BOT_IA_ADMIN_MODE",
            "Modo Administrador activado: Paneles y temas estructurados correctamente.",
        ):
            self.assertIn(token, source)



    def test_multilink_provider_status_and_usage_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        for token in (
            'class BotExpandedDialog(QDialog):',
            'provider_changed = Signal(str, str)',
            'self.provider.addItem("Google Gemini", "gemini")',
            'self.provider.addItem("OpenAI ChatGPT", "chatgpt")',
            'self.provider.addItem("Microsoft Copilot", "copilot")',
            'self.manual_button = QPushButton("🔑 Registrarse / Candado")',
            'self.led.setText("🟢 Autenticado y Activo"',
            'self.led.setText("🔴 Desconectado"',
            'self._usage_seconds',
            'self._usage_timer',
            'storage_state.json',
            'ROOT / "browser_data" / bot_id',
            'def _browser_auth_state(',
            'def _on_expanded_provider_changed(',
            'provider_changed.connect(',
            'provider_id=provider_id',
        ):
            self.assertIn(token, app)

        self.assertIn('"copilot": ProviderWebSpec(', app)
        self.assertIn('https://copilot.microsoft.com/', app)

    def test_webqueue_single_seat_mutex_contract(self):
        source = (
            self.ROOT / "src" / "services" / "web_queue.py"
        ).read_text(encoding="utf-8")
        for token in (
            "import threading",
            "_WEB_MESA_UNICA = threading.Lock()",
            "self._mesa_unica_acquired = False",
            "_WEB_MESA_UNICA.acquire(",
            "timeout=max(1.0, self.timeout_ms / 1000)",
            "La espera ocurre únicamente en el worker, nunca en la GUI.",
            "_WEB_MESA_UNICA.release()",
            "MESA_UNICA_TIMEOUT",
        ):
            self.assertIn(token, source)

    def test_local_autonomy_for_cari_and_cami_avoids_webqueue(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")
        for token in (
            "def _try_local_bot_response(self, message: str) -> bool:",
            'if bot_id not in {"cari", "cami"}:',
            "respuesta local; WebQueue omitido",
            "if self._try_local_bot_response(message):",
        ):
            self.assertIn(token, source)

    def test_waifu_registry_and_tcg_prompt_contract(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")
        registry = (
            self.ROOT / "src" / "gui" / "waifu_registry.py"
        ).read_text(encoding="utf-8")
        for token in (
            "🎴 Registro de Waifus",
            "🎴 Waifu / TCG",
            'QPushButton("Generar Prompt")',
            'QPushButton("+ Subir Imagen")',
            'QPushButton("🃏 Ensamblar Carta")',
            "QProgressBar",
            "WaifuRegistry(ROOT)",
            "config/waifu_registry.json",
            "artifacts",
        ):
            self.assertIn(token, source)
        for token in (
            "class WaifuRecord",
            "class WaifuRegistry",
            "def generate_tcg_prompt",
            "isolated, simple white background",
            "no frame, no card border",
            "cosplay_reference",
            "progress",
        ):
            self.assertIn(token, registry)

    def test_waifu_registry_persistence_and_prompt_generation(self):
        import tempfile
        from pathlib import Path
        from gui.waifu_registry import (
            WaifuRecord,
            WaifuRegistry,
            generate_tcg_prompt,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry = WaifuRegistry(root)
            record = WaifuRecord(
                name="Aki",
                personality="tsundere",
                appearance="silver hair, red eyes, armored dress",
                element="Fuego",
                cosplay_reference="UR",
            )
            record.prompt = generate_tcg_prompt(record)
            registry.save([record])
            loaded = registry.load()
            self.assertEqual(1, len(loaded))
            self.assertEqual("Aki", loaded[0].name)
            self.assertIn("isolated, simple white background", loaded[0].prompt)
            self.assertIn("no frame, no card border", loaded[0].prompt)

    def test_manual_authentication_persists_provider_profile_state(self):
        source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")
        for token in (
            'profile_path = Path(self.browser_profile).resolve()',
            'context.storage_state(',
            'path=str(state_path)',
            'indexed_db=True',
            'headless=False',
            'no_viewport=True',
            'provider_id=',
            'BOT_IA_COPILOT_URL',
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
