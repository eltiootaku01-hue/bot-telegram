# -*- coding: utf-8 -*-
from pathlib import Path
import asyncio
import ast
import os
import importlib
import unittest
from unittest.mock import patch


class CafeOtakuGuiContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_browser_style_tabs_and_incidents_panel_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        panel = (self.ROOT / "src" / "gui" / "incidents_panel.py").read_text(encoding="utf-8")

        for token in (
            "QTabWidget",
            'self.main_tabs.addTab(web_tab, "🌐 Navegador Web")',
            'self.main_tabs.addTab(self._build_schrodinger_tab(), "⚛ Chat Schrödinger")',
            'self.main_tabs.addTab(self._build_orders_tab(), "🎴 Pedidos & Hashtags")',
            'self.main_tabs.addTab(self.incidents_panel, "🛡 Incidencias & Moderación")',
            "self.main_tabs.currentChanged.connect(self._on_main_tab_changed)",
            "setWindowState(self.windowState() | Qt.WindowMaximized)",
            "def _build_schrodinger_tab",
            "def _build_orders_tab",
        ):
            self.assertIn(token, app)

        for token in (
            "class IncidentStore",
            "class IncidentsPanel",
            "Errores",
            "Queja / Reembolso",
            "Aislamiento / Incidente",
            "ID único:",
            "Perdones previos:",
            "Nivel de confianza:",
            "Fecha de registro en el bot:",
            "Regla/error roto:",
            "def _forgive",
            "def _refund",
            "def _reject",
            "✅ Perdonar",
            "💸 Aceptar Reembolso",
            "❌ Rechazar / Ban Permanent",
            "ComplaintStore",
        ):
            self.assertIn(token, panel)

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

    def test_tcg_frame_templates_and_card_tracker_contract(self):
        registry_source = (
            self.ROOT / "src" / "gui" / "waifu_registry.py"
        ).read_text(encoding="utf-8")
        gui_source = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")
        for token in (
            "class CardSlot",
            "card_slots",
            "def frame_candidates",
            "frame_{rarity}_{element_slug}.svg",
            "frame_{rarity}.svg",
            "def record_progress",
        ):
            self.assertIn(token, registry_source)
        for token in (
            "assets/tcg_frames",
            "QPixmap",
            "QPainter",
            "QFont",
            "self.card_slot",
            "Carta 1 · R",
            "Carta 2 · SR",
            "Cosplay UR · UR",
            "slot.complete = True",
        ):
            self.assertIn(token, gui_source)

        frame_dir = self.ROOT / "assets" / "tcg_frames"
        for rarity in ("R", "SR", "UR"):
            self.assertTrue((frame_dir / f"frame_{rarity}.svg").is_file())

    def test_card_slot_progress_is_derived_from_completion(self):
        from gui.waifu_registry import CardSlot, WaifuRecord, record_progress

        record = WaifuRecord(
            name="Aki",
            personality="tsundere",
            appearance="silver hair",
            element="Fuego",
            cosplay_reference="UR",
            card_slots=[
                CardSlot("Carta 1", "R", complete=True),
                CardSlot("Carta 2", "SR", image_path="sprite.png"),
                CardSlot("Cosplay UR", "UR"),
            ],
        )
        self.assertEqual(50, record_progress(record))
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


    def test_local_mini_games_router_is_webqueue_free(self):
        from gui.mini_games import LocalGameRouter

        router = LocalGameRouter()
        for bot_id in ("cari", "sunna", "cami", "chie"):
            ppt = router.route("piedra", "desktop-user", bot_id)
            self.assertIsNotNone(ppt)
            self.assertIn("PPT local", ppt)

        opening = router.route("21 nuevo", "desktop-user", "sunna")
        self.assertIn("21 local", opening)
        action = router.route("carta", "desktop-user", "sunna")
        self.assertIn("21 local", action)
        self.assertIn("No se usa WebQueue", router.route("21 ???", "desktop-user", "sunna"))

    def test_game_card_lora_prompt_and_auto_crop_contract(self):
        from PySide6.QtGui import QImage, QColor
        from gui.waifu_registry import (
            WaifuRecord,
            crop_sprite_to_ratio,
            generate_tcg_prompt,
            normalize_lora_tags,
        )

        self.assertEqual("[LORA_NAME] [STYLE_TAG]", normalize_lora_tags("[LORA_NAME], STYLE_TAG"))
        record = WaifuRecord(
            name="Aki",
            personality="tsundere",
            appearance="silver hair",
            element="Luz",
            cosplay_reference="UR",
            card_category="UNO",
            lora_tags="[LORA_NAME]",
        )
        prompt = generate_tcg_prompt(record)
        self.assertIn("Category: UNO", prompt)
        self.assertIn("LoRA tags: [LORA_NAME]", prompt)
        self.assertIn("simple white background", prompt)
        self.assertIn("isolated", prompt)

        image = QImage(400, 400, QImage.Format_RGBA8888)
        image.fill(QColor(255, 255, 255, 255))
        for y in range(100, 300):
            for x in range(150, 250):
                image.setPixelColor(x, y, QColor(30, 30, 30, 255))
        cropped = crop_sprite_to_ratio(image, ratio=3 / 4)
        self.assertEqual(3, cropped.width() * 4 // cropped.height())
        self.assertLess(cropped.width(), image.width())
        self.assertLess(cropped.height(), image.height())

    def test_app_routes_games_and_exposes_card_catalog(self):
        source = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        registry = (self.ROOT / "src" / "gui" / "waifu_registry.py").read_text(encoding="utf-8")
        for token in (
            "LocalGameRouter",
            "self._mini_game_router.route(",
            "Mini-Juegos",
            "Cartas de Juego",
            "Póker",
            "UNO",
            "crop_sprite_to_ratio(",
            "target_ratio = 1.0 if",
            "WebQueue omitido",
        ):
            self.assertIn(token, source)
        for token in (
            "card_category",
            "lora_tags",
            "normalize_lora_tags",
            "crop_sprite_to_ratio",
            "simple white background",
            "isolated",
        ):
            self.assertIn(token, registry)


    def test_playing_card_catalog_and_template_contract(self):
        registry = (self.ROOT / "src" / "gui" / "waifu_registry.py").read_text(encoding="utf-8")
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        mini = (self.ROOT / "src" / "gui" / "mini_games.py").read_text(encoding="utf-8")
        for token in (
            "card_number",
            "card_suit",
            "Playing card:",
            "matching playing-card template",
        ):
            self.assertIn(token, registry)
        for token in (
            "Número / Rango",
            "Palo",
            "Corazones",
            "Diamantes",
            "Tréboles",
            "Picas",
            "def _draw_playing_card_template",
            "suit_symbols",
            "QColor",
        ):
            self.assertIn(token, app)
        for token in (
            "GAME_HOSTS",
            '"ppt": "Cari"',
            '"21": "Sunna"',
            '"uno": "Cami"',
            "class UnoState",
            "def _new_uno",
            "def _uno_response",
        ):
            self.assertIn(token, mini)

    def test_playing_card_record_persists_rank_and_suit(self):
        import tempfile
        from pathlib import Path
        from gui.waifu_registry import WaifuRecord, WaifuRegistry, generate_tcg_prompt

        with tempfile.TemporaryDirectory() as temp_dir:
            record = WaifuRecord(
                name="Aki",
                personality="serena",
                appearance="cabello plateado",
                element="Neutro",
                cosplay_reference="SR",
                card_category="Póker",
                card_number="Q",
                card_suit="Picas",
                lora_tags="[CARD_LORA]",
            )
            record.prompt = generate_tcg_prompt(record)
            registry = WaifuRegistry(Path(temp_dir))
            registry.save([record])
            loaded = registry.load()[0]
            self.assertEqual("Q", loaded.card_number)
            self.assertEqual("Picas", loaded.card_suit)
            self.assertIn("Playing card: Q of Picas", loaded.prompt)

    def test_uno_is_an_actual_local_game_route(self):
        from gui.mini_games import LocalGameRouter

        router = LocalGameRouter()
        opening = router.route("UNO nuevo", "desktop-user", "cami")
        self.assertIn("UNO local", opening)
        self.assertIn("Cami", opening)
        table = router.route("juego de mesa", "desktop-user", "chie")
        self.assertIn("Chie", table)
        self.assertNotIn("WebQueue", table)
        draw = router.route("robar", "desktop-user", "cami")
        self.assertIn("UNO local", draw)
        self.assertNotIn("WebQueue", draw)


    def test_waifumon_stats_card_contract(self):
        registry = (
            self.ROOT / "src" / "gui" / "waifu_registry.py"
        ).read_text(encoding="utf-8")
        app = (
            self.ROOT / "src" / "gui" / "app.py"
        ).read_text(encoding="utf-8")
        for token in (
            "card_hp",
            "card_attack",
            "card_type",
            "Waifumon / Ficha de Stats",
            "Waifumon stats:",
            "matching Waifumon stats-card template",
        ):
            self.assertIn(token, registry)
        for token in (
            "Waifumon / Ficha de Stats",
            'QLabel("HP")',
            'QLabel("Ataque")',
            'QLabel("Tipo")',
            "def _draw_waifumon_stats_template",
            '"HP", record.card_hp',
            '"ATAQUE", record.card_attack',
            '"ELEMENTO", record.element',
            '"TIPO", record.card_type',
        ):
            self.assertIn(token, app)

    def test_waifumon_stats_persist_and_prompt(self):
        import tempfile
        from pathlib import Path
        from gui.waifu_registry import (
            WaifuRecord,
            WaifuRegistry,
            generate_tcg_prompt,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            record = WaifuRecord(
                name="Aki",
                personality="valiente",
                appearance="cabello plateado",
                element="Fuego",
                cosplay_reference="UR",
                card_category="Waifumon / Ficha de Stats",
                card_hp="120",
                card_attack="80",
                card_type="Guerrero",
            )
            record.prompt = generate_tcg_prompt(record)
            registry = WaifuRegistry(Path(temp_dir))
            registry.save([record])
            loaded = registry.load()[0]
            self.assertEqual("120", loaded.card_hp)
            self.assertEqual("80", loaded.card_attack)
            self.assertEqual("Guerrero", loaded.card_type)
            self.assertIn(
                "Waifumon stats: HP 120, Attack 80, Element Fuego, Type Guerrero.",
                loaded.prompt,
            )
            self.assertIn(
                "matching Waifumon stats-card template",
                loaded.prompt,
            )


    def test_tutorial_elemental_matrix_and_card_parts_contract(self):
        from bot_ia.interfaces.tutorials import build_tutorial_html, build_tutorial_text

        text = build_tutorial_text()
        html = build_tutorial_html()
        self.assertIn("Fuego → Aire → Tierra → Agua → Fuego", text)
        for token in ("Marco / rareza", "Arte", "Elemento", "HP", "Ataque", "Cosplay"):
            self.assertIn(token, text)
        self.assertIn("<table", html)
        self.assertIn("Fuego", html)
        self.assertIn("Waifumon", html)

    def test_cafe_economy_wallet_pricing_and_gacha_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_economy import (
            CafeWalletStore,
            GACHA_COST,
            GAME_REWARDS,
            ORDER_COST_HIGH,
            ORDER_COST_NORMAL,
            draw_gacha,
            maid_consolation,
            quote_bebida_order,
        )

        with TemporaryDirectory() as tmp:
            store = CafeWalletStore(Path(tmp))
            self.assertEqual(50, store.balance("u1"))
            store.credit("u1", 10)
            self.assertEqual(60, store.balance("u1"))
            self.assertEqual(ORDER_COST_NORMAL, quote_bebida_order(existing=True, points=60).cost)
            self.assertEqual(ORDER_COST_HIGH, quote_bebida_order(existing=False, points=60).cost)
            self.assertEqual("R", draw_gacha("u1", store, roll=lambda: 0, maid="Cami").rarity)
            store.credit("u1", GACHA_COST * 2)
            self.assertEqual("SR", draw_gacha("u1", store, roll=lambda: 70, maid="Cami").rarity)
            store.credit("u1", GACHA_COST * 2)
            result = draw_gacha("u1", store, roll=lambda: 99, maid="Cami")
            self.assertEqual("UR", result.rarity)
            self.assertEqual(70, store.balance("u1"))
            self.assertIn("Cami", result.consolation)
            self.assertIn("R", maid_consolation("Cari", "R"))
            self.assertEqual({"21": 10, "uno": 12, "ppt": 5}, GAME_REWARDS)

    def test_cafe_rarity_pricing_and_pity_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_economy import (
            CafeWalletStore,
            PITY_SR_LIMIT,
            PITY_UR_LIMIT,
            RARITY_PRICES,
            draw_gacha,
            pity_text,
            quote_bebida_order,
        )

        self.assertEqual(
            {"R": 10, "SR": 35, "UR": 100, "SPECIAL": 150},
            RARITY_PRICES,
        )
        with TemporaryDirectory() as tmp:
            store = CafeWalletStore(Path(tmp))
            store.credit("pricing", 200)
            for rarity, expected in (("R", 10), ("SR", 35), ("UR", 100)):
                quote = quote_bebida_order(
                    existing=True,
                    target_rarity=rarity,
                    points=200,
                )
                self.assertEqual(expected, quote.cost)
                self.assertTrue(quote.can_afford)
            special = quote_bebida_order(
                existing=False,
                target_rarity="SPECIAL",
                points=200,
            )
            self.assertEqual(150, special.cost)

            store.credit("pity", 600)
            for _ in range(PITY_SR_LIMIT - 1):
                result = draw_gacha("pity", store, roll=lambda: 0, maid="Cami")
                self.assertEqual("R", result.rarity)
            self.assertEqual(PITY_SR_LIMIT - 1, store.get("pity").pity_sr)
            self.assertEqual(PITY_SR_LIMIT - 1, store.get("pity").pity_ur)

            sr = draw_gacha("pity", store, roll=lambda: 0, maid="Cami")
            self.assertEqual("SR", sr.rarity)
            self.assertEqual(0, store.get("pity").pity_sr)
            self.assertEqual(PITY_SR_LIMIT, store.get("pity").pity_ur)

            for _ in range(PITY_UR_LIMIT - PITY_SR_LIMIT - 1):
                draw_gacha("pity", store, roll=lambda: 0, maid="Cami")
            self.assertEqual(PITY_UR_LIMIT - 1, store.get("pity").pity_ur)

            ur = draw_gacha("pity", store, roll=lambda: 0, maid="Cami")
            self.assertEqual("UR", ur.rarity)
            self.assertEqual(0, store.get("pity").pity_ur)
            self.assertEqual(0, store.get("pity").pity_sr)

            message = pity_text("pity", store, maid="Cami")
            self.assertIn("tiradas hacia tu SR", message)
            self.assertIn("tiradas hacia tu UR", message)

    def test_cafe_pity_and_price_gui_telegram_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        registry = (self.ROOT / "src" / "gui" / "waifu_registry.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        economy = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_economy.py").read_text(encoding="utf-8")
        from gui.waifu_registry import bebida_rarity_price_menu
        menu = bebida_rarity_price_menu()
        for token in (
            "Bebida R: 10 Puntos",
            "Bebida SR: 35 Puntos",
            "Bebida UR: 100 Puntos",
            "Bebida Especial (Custom Prompt): 150 Puntos",
            "Rareza objetivo",
            "target_rarity",
            "🍀 Pity",
            "pity_text",
            "_show_pity",
            "_show_affinity",
            "affinity_level=self.waifu_registry.affinity_level",
        ):
            self.assertIn(token, app + registry + economy + menu)
        for token in ('"/pity"', '"pity:show"', '"gacha:draw"', "pity_text"):
            self.assertIn(token, telegram)

    def test_mini_games_are_connected_to_cafe_wallet_contract(self):
        source = (self.ROOT / "src" / "gui" / "mini_games.py").read_text(encoding="utf-8")
        for token in (
            "CafeWalletStore",
            "wallet_store",
            "reward_game",
            '"ppt"',
            '"21"',
            '"uno"',
        ):
            self.assertIn(token, source)

    def test_bebida_prompt_pricing_and_purchase_contract(self):
        source = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        orders = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_orders.py").read_text(encoding="utf-8")
        economy = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_economy.py").read_text(encoding="utf-8")
        for token in (
            "Puntos del Café",
            "Comprar / Clonar",
            "purchase_bebida_order",
            "bebida_order_quote",
            "simple white background, isolated",
        ):
            self.assertIn(token, source + orders)
        self.assertIn("ORDER_COST_HIGH", economy)
        self.assertIn("ORDER_COST_NORMAL", economy)

    def test_telegram_economy_commands_contract(self):
        source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        for token in (
            '"/puntos"',
            '"/economia"',
            '"/precios"',
            'command == "/gacha"',
            "CafeWalletStore",
            "draw_gacha",
            "economy_price_text",
        ):
            self.assertIn(token, source)

    def test_bebida_order_flow_and_local_autocomplete_contract(self):
        from bot_ia.interfaces.cafe_orders import (
            BOLDNESS_LEVELS,
            EXPOSURE_LEVELS,
            PRODUCT_TYPES,
            BebidaOrder,
            BebidaOrderFlow,
            build_bebida_prompt,
            character_suggestions,
        )
        from gui.waifu_registry import WaifuRecord

        record = WaifuRecord(
            name="Aki",
            danbooru_tag="aki_(anime)",
            personality="serena",
            appearance="cabello plateado",
            element="Fuego",
            cosplay_reference="UR",
            lora_tags="[AKI_LORA]",
        )
        self.assertEqual(["Aki", "aki_(anime)"], character_suggestions([record]))
        flow = BebidaOrderFlow(["aki_(anime)"])
        flow.start("user-1")
        flow.set_character("user-1", "Aki", "aki_(anime)")
        flow.choose("user-1", "exposure", "SFW")
        flow.choose("user-1", "boldness", "Atrevido")
        order = flow.choose("user-1", "product_type", "Waifumon")
        self.assertEqual("aki_(anime)", order.character_tag)
        self.assertIn("Character tag: aki_(anime)", build_bebida_prompt(order))
        self.assertEqual(EXPOSURE_LEVELS[0], "SFW")
        self.assertIn("Atrevido", BOLDNESS_LEVELS)
        self.assertIn("Waifumon", PRODUCT_TYPES)

    def test_hardening_mutex_and_input_sanitization(self):
        import threading

        from bot_ia.interfaces.hardening import (
            MutexGuard,
            sanitize_control_text,
            whitelist_tag,
        )
        from bot_ia.interfaces.cafe_orders import BebidaOrder, BebidaOrderFlow

        guard = MutexGuard()
        self.assertTrue(guard.try_acquire("catch:user-1"))
        self.assertFalse(guard.try_acquire("catch:user-1"))
        guard.release("catch:user-1")
        self.assertTrue(guard.try_acquire("catch:user-1"))
        guard.release("catch:user-1")

        results: list[bool] = []
        acquired = threading.Event()
        release = threading.Event()

        def first_worker() -> None:
            results.append(guard.try_acquire("catch:concurrent"))
            acquired.set()
            release.wait(1.0)
            guard.release("catch:concurrent")

        worker = threading.Thread(target=first_worker)
        worker.start()
        self.assertTrue(acquired.wait(1.0))
        self.assertFalse(guard.try_acquire("catch:concurrent"))
        release.set()
        worker.join(1.0)
        self.assertEqual([True], results)
        self.assertTrue(guard.try_acquire("catch:concurrent"))
        guard.release("catch:concurrent")

        dirty = "  hola\\x00\\x1b\nusuario  "
        clean = sanitize_control_text(dirty)
        self.assertNotIn("\\x00", clean)
        self.assertNotIn("\\x1b", clean)
        self.assertEqual("hola usuario", clean)
        self.assertEqual("aki_(anime)", whitelist_tag("aki_(anime)", ["aki_(anime)"]))
        self.assertEqual("", whitelist_tag("forged_(anime)", ["aki_(anime)"]))

        flow = BebidaOrderFlow(["aki_(anime)"])
        flow.start("hard-user")
        flow.set_character("hard-user", "Aki" + chr(0), "forged_(anime)")
        self.assertEqual("", flow.get("hard-user").character_tag)
        flow.set_character("hard-user", "Aki" + chr(0), "aki_(anime)")
        order = flow.choose("hard-user", "exposure", "SFW")
        safe = order.normalized()
        self.assertEqual("aki_(anime)", safe.character_tag)
        self.assertNotIn(chr(0), safe.character)

        raw = BebidaOrder(
            character="Aki",
            character_tag="aki_(anime)",
            pose="De pie" + chr(0),
            outfit="Casual" + chr(27),
            cosplay="UR" + chr(0),
        ).normalized()
        self.assertNotIn(chr(0), raw.pose)
        self.assertNotIn(chr(27), raw.outfit)
        self.assertNotIn(chr(0), raw.cosplay)

    def test_schrodinger_router_contract(self):
        import os
        from bot_ia.interfaces.schrodinger import LiveTarget, SchrodingerError, SchrodingerRouter

        sent = []
        moderation = []

        def tg(chat_id, text, media):
            sent.append(("telegram", chat_id, text, media))
            return True

        def dc(chat_id, text, media):
            sent.append(("discord", chat_id, text, media))
            return True

        def mod(action, guild_id, user_id):
            moderation.append((action, guild_id, user_id))
            return True

        os.environ["SCHRODINGER_BOT_TOKEN"] = "test-token"
        router = SchrodingerRouter(
            telegram_sender=tg,
            discord_sender=dc,
            moderation_action=mod,
        )
        router.send_text(
            LiveTarget("telegram", "-100", "Café"),
            "Hola",
            "photo-file-id",
        )
        router.send_text(
            LiveTarget("discord", "123", "Servidor"),
            "Buenas",
            "https://example.invalid/image.png",
        )
        self.assertEqual(sent[0], ("telegram", "-100", "Hola", "photo-file-id"))
        self.assertEqual(sent[1], ("discord", "123", "Buenas", "https://example.invalid/image.png"))

        router.moderate("unmute", "guild", "user")
        router.moderate("kick", "guild", "user")
        router.moderate("ban", "guild", "user")
        self.assertEqual(
            moderation,
            [("unmute", "guild", "user"), ("kick", "guild", "user"), ("ban", "guild", "user")],
        )
        self.assertEqual(router.token(), "test-token")

        with self.assertRaises(SchrodingerError):
            router.send_text(LiveTarget("matrix", "1"), "x")

    def test_schrodinger_gui_and_env_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        env = (self.ROOT / ".env.example").read_text(encoding="utf-8")
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        module = (self.ROOT / "src" / "bot_ia" / "interfaces" / "schrodinger.py").read_text(encoding="utf-8")

        for token in (
            "class SchrodingerDialog",
            "⚛ Schrödinger",
            "Perdonar / Unmute",
            "Kick",
            "Ban Permanent",
            "SCHRODINGER_TARGETS",
            "build_schrodinger_router",
            "TelegramApiClient",
            "send_channel_message",
        ):
            self.assertIn(token, app)

        self.assertIn("SCHRODINGER_BOT_TOKEN=", env)
        self.assertIn("clear_timeout", group)
        for token in (
            "class SchrodingerRouter",
            "SCHRODINGER_BOT_TOKEN",
            "LiveTarget",
            "send_text",
            "moderate",
        ):
            self.assertIn(token, module)

    def test_auto_moderation_priority_and_cari_suggestions(self):
        from bot_ia.interfaces.auto_moderation import (
            CANTINA_REDIRECT_MESSAGE,
            CARI_LEGAL_MESSAGE,
            CARI_PROFANITY_MESSAGE,
            moderate,
            moderation_action_priority,
        )

        illegal = moderate("quiero loli y contenido para menores")
        self.assertEqual("ban", illegal.action)
        self.assertEqual("illegal_minor_related", illegal.reason)
        self.assertEqual("Cari", illegal.waitress)
        self.assertEqual(CARI_LEGAL_MESSAGE, illegal.message)
        self.assertGreater(
            moderation_action_priority(illegal),
            moderation_action_priority(moderate("puta mierda")),
        )

        profanity = moderate("puta mierda")
        self.assertEqual("delete_warn", profanity.action)
        self.assertEqual("severe_profanity", profanity.reason)
        self.assertEqual(CARI_PROFANITY_MESSAGE, profanity.message)

        sfw = moderate("quiero porno explícito", room_key="pedidos_sfw")
        self.assertEqual("delete_redirect", sfw.action)
        self.assertEqual("#cantina-18", sfw.target_room)
        self.assertEqual("Scarlet", sfw.waitress)
        self.assertIn("Scarlet", sfw.message)
        self.assertIn("Chloé", sfw.message)
        self.assertEqual(CANTINA_REDIRECT_MESSAGE, sfw.message)

        self.assertEqual("allow", moderate("quiero un café con leche", room_key="pedidos_sfw").action)
        # La prioridad legal gana aunque también aparezca una señal SFW explícita.
        mixed = moderate("loli porno explícito", room_key="pedidos_sfw")
        self.assertEqual("ban", mixed.action)

    def test_discord_moderation_handler_contract(self):
        source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "discord_moderation.py").read_text(encoding="utf-8")
        for token in (
            "class DiscordModerationHandler",
            "self._client.delete_message",
            "self._client.ban_member",
            "moderate(",
        ):
            self.assertIn(token, source)

    def test_auto_moderation_integration_contract(self):
        moderation = (self.ROOT / "src" / "bot_ia" / "interfaces" / "auto_moderation.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        discord = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")

        for token in (
            "LEGAL_SAFETY_TERMS",
            "SEVERE_PROFANITY",
            "EXPLICIT_TERMS",
            "CARI_LEGAL_MESSAGE",
            "CARI_PROFANITY_MESSAGE",
            "CANTINA_REDIRECT_MESSAGE",
            'return ModerationDecision("ban"',
            'return ModerationDecision("delete_redirect"',
        ):
            self.assertIn(token, moderation)

        for token in (
            "moderate(",
            "self._client.delete_message",
            "self._client.ban_chat_member",
            "TelegramInputError",
        ):
            self.assertIn(token, telegram)

        for token in (
            "def delete_message",
            "def ban_member",
            "def timeout_member",
        ):
            self.assertIn(token, discord)

    def test_hardening_shutdown_contract(self):
        queue_source = (self.ROOT / "src" / "services" / "web_queue.py").read_text(encoding="utf-8")
        app_source = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        telegram_source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        main_source = (self.ROOT / "src" / "bot_ia" / "__main__.py").read_text(encoding="utf-8")
        hardening_source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "hardening.py").read_text(encoding="utf-8")

        for token in (
            "MutexGuard",
            "blocking=False",
            "sanitize_control_text",
            "whitelist_tag",
        ):
            self.assertIn(token, hardening_source)

        for token in (
            "_WEB_MESA_UNICA.release()",
            '"QUEUE_STOPPED"',
            "self.msg_queue.get_nowait()",
        ):
            self.assertIn(token, queue_source)

        for token in (
            "self._tea_scheduler.stop(timeout=2.0)",
            "self._web_queue.shutdown()",
            "await window.shutdown_async_engine()",
        ):
            self.assertIn(token, app_source)

        for token in (
            "self._callback_mutex",
            "_callback_key",
            "callback dropped by local mutex",
        ):
            self.assertIn(token, telegram_source)

        for token in (
            "signal.signal(signal.SIGTERM, request_stop)",
            "poller.stop()",
            "SIGBREAK",
        ):
            self.assertIn(token, main_source)

    def test_bebida_gui_and_telegram_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        registry = (self.ROOT / "src" / "gui" / "waifu_registry.py").read_text(encoding="utf-8")
        for token in (
            "BebidaOrderDialog",
            "🥤 Bebida Especial",
            "Grado de Exposición",
            "Nivel de Atrevimiento",
            "Pose",
            "Vestimenta",
            "Cosplay",
            "Carta TCG",
            "Naipe",
            "Waifumon",
            "QCompleter",
            "character_suggestions",
            "danbooru_tag",
        ):
            self.assertIn(token, app)
        for token in (
            'command == "/tutorial"',
            'command == "/bebida"',
            "BebidaOrderFlow",
            "build_tutorial_text",
            "bebida:exposure:",
            "bebida:boldness:",
            "bebida:product_type:",
        ):
            self.assertIn(token, telegram)
        self.assertIn("danbooru_tag", registry)

    def test_group_setup_and_rarity_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        registry = (self.ROOT / "src" / "gui" / "waifu_registry.py").read_text(encoding="utf-8")
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        for token in (
            "TelegramGroupSetup",
            "createForumTopic",
            "can_manage_topics",
            "DiscordGroupSetup",
            "/guilds/{guild_id}/channels",
            '"type": 0',
            "Administrador o Gestionar Canales",
            "📌 Anuncios / General",
            "🎴 Colección TCG",
            "🎮 Minijuegos (21 / UNO / PPT)",
            "💬 Zona de Meseras",
        ):
            self.assertIn(token, group)
        self.assertIn('command == "/setup_group"', telegram)
        self.assertIn("Estructurar Grupo", app)
        self.assertIn("frame_R.svg", registry)
        self.assertIn("frame_UR.svg", registry)
        self.assertIn('if rarity == "R":', registry)
        self.assertIn('if rarity == "UR":', registry)
        self.assertIn("def _draw_ur_element_effects", app)
        self.assertIn('if rarity == "UR":', app)

    def test_cafe_maid_personalities_and_tea_time_contract(self):
        from bot_ia.interfaces.cafe_immersion import (
            TEA_TIME_DURATION_SECONDS,
            TEA_TIME_MULTIPLIER,
            WAITRESS_PROFILES,
            TeaTimeScheduler,
            waitress_exclusive_dialogue,
        )

        self.assertEqual(
            {"Cari", "Sunna", "Cami", "Chie"},
            set(WAITRESS_PROFILES),
        )
        self.assertIn("Maid", WAITRESS_PROFILES["Cari"]["focus"])
        self.assertIn("21", WAITRESS_PROFILES["Sunna"]["focus"])
        self.assertIn("Bebidas", WAITRESS_PROFILES["Cami"]["focus"])
        self.assertIn("Trivias", WAITRESS_PROFILES["Chie"]["focus"])

        now = [1000.0]
        scheduler = TeaTimeScheduler(
            clock=lambda: now[0],
            min_interval_seconds=1,
            max_interval_seconds=1,
        )
        scheduler.activate(now=now[0])
        self.assertTrue(scheduler.is_active(now=now[0] + 1))
        self.assertEqual(TEA_TIME_MULTIPLIER, scheduler.multiplier(now=now[0] + 1))
        self.assertEqual(
            TEA_TIME_DURATION_SECONDS - 1,
            scheduler.remaining_seconds(now=now[0] + 1),
        )
        self.assertFalse(scheduler.is_active(now=now[0] + TEA_TIME_DURATION_SECONDS + 1))
        self.assertEqual(1, scheduler.multiplier(now=now[0] + TEA_TIME_DURATION_SECONDS + 1))
        self.assertIn("afinidad", waitress_exclusive_dialogue("Cami", 3))

    def test_tea_time_doubles_local_game_rewards(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_economy import CafeWalletStore
        from bot_ia.interfaces.cafe_immersion import TeaTimeScheduler
        from gui.mini_games import LocalGameRouter

        with TemporaryDirectory() as tmp:
            store = CafeWalletStore(Path(tmp))
            now = [100.0]
            scheduler = TeaTimeScheduler(
                clock=lambda: now[0],
                min_interval_seconds=1,
                max_interval_seconds=1,
            )
            scheduler.activate(now=now[0])
            router = LocalGameRouter(store, scheduler)
            router._reward_game("tea-user", "21")
            self.assertEqual(70, store.balance("tea-user"))

    def test_waitress_affinity_tip_persistence_and_gacha_bonus(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_economy import CafeWalletStore, draw_gacha
        from gui.waifu_registry import (
            AFFINITY_EXCLUSIVE_LEVEL,
            AFFINITY_GACHA_BONUS_LEVEL,
            HEART_LEVEL_MAX,
            WaifuRegistry,
        )

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wallet = CafeWalletStore(root)
            registry = WaifuRegistry(root)
            registry.save([])

            maid, charged, level = registry.tip_waitress("u1", "Cami", 15, wallet)
            self.assertEqual("Cami", maid)
            self.assertEqual(15, charged)
            self.assertEqual(AFFINITY_EXCLUSIVE_LEVEL, level)
            self.assertLessEqual(level, HEART_LEVEL_MAX)

            reloaded = WaifuRegistry(root)
            self.assertEqual(level, reloaded.affinity_level("u1", "Cami"))
            self.assertIn("Cami: 3/10", reloaded.affinity_summary("u1"))

            registry.tip_waitress("u2", "Cami", AFFINITY_GACHA_BONUS_LEVEL * 5, wallet)
            self.assertEqual(AFFINITY_GACHA_BONUS_LEVEL, registry.affinity_level("u2", "Cami"))
            result = draw_gacha(
                "u2",
                wallet,
                roll=lambda: 0,
                maid="Cami",
                affinity_level=registry.affinity_level("u2", "Cami"),
            )
            self.assertEqual("R", result.rarity)
            self.assertTrue(result.affinity_bonus)
            self.assertEqual(1, wallet.get("u2").pity_sr)

    def test_cafe_telegram_immersion_handlers_contract(self):
        source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        mini = (self.ROOT / "src" / "gui" / "mini_games.py").read_text(encoding="utf-8")
        registry = (self.ROOT / "src" / "gui" / "waifu_registry.py").read_text(encoding="utf-8")
        for token in (
            'command == "/propina"',
            'command == "/afinidad"',
            'command == "/mesera"',
            '"affinity:show"',
            "waitress_dialogue",
            "affinity_level=",
        ):
            self.assertIn(token, source)
        for token in (
            "WAITRESS_PROFILES",
            "TeaTimeScheduler",
            "TEA_TIME_DURATION_SECONDS",
            "TEA_TIME_MULTIPLIER",
            "waitress_exclusive_dialogue",
        ):
            self.assertIn(token, immersion)
        for token in (
            "TeaTimeScheduler",
            "tea_scheduler",
            "multiplier=self._tea_scheduler.multiplier()",
            "waitress_dialogue",
        ):
            self.assertIn(token, mini)
        for token in (
            "WAITRESS_IDS",
            "HEART_LEVEL_MAX",
            "waitress_affinity",
            "tip_waitress",
        ):
            self.assertIn(token, registry)

    def test_cafe_group_sfw_mature_feeds_and_admin_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        rooms = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_rooms.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        mini = (self.ROOT / "src" / "gui" / "mini_games.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")

        for token in (
            '"#general"',
            '"#tcg-collection"',
            '"#pedidos-sfw"',
            '"#noticias-otaku"',
            '"#cantina-18"',
            '"#pedidos-nsfw"',
            '"#mesa-de-apuestas-21"',
            '"#pedidos-admin"',
            "SFW_ROOM_KEYS",
            "MATURE_ROOM_KEYS",
            "ADMIN_ROOM_KEY",
            "REPOST_FEEDS",
            "https://t.me/eltiootaku",
            "https://t.me/yandere_nsfw",
            "https://t.me/danbooru_sfw",
            "https://t.me/danbooru_nsfw",
            '"feeds"',
        ):
            self.assertIn(token, group)

        for token in (
            "MATURE_KEYWORDS",
            "sfw_transition",
            "Scarlet",
            "Chloé",
            "mature_game_host",
            "#cantina-18",
        ):
            self.assertIn(token, rooms)

        for token in (
            'command == "/21"',
            'command == "/blackjack"',
            'command == "/apuestas"',
            'value.casefold() == "nsfw"',
            "#cantina-18",
            "Scarlet o Chloé",
        ):
            self.assertIn(token, telegram)

        self.assertIn('"21": "Scarlet"', mini)
        self.assertIn("mature_game_message", mini)
        self.assertIn("Scarlet", immersion)
        self.assertIn("Chloé", immersion)

    def test_sfw_mature_transition_behavior(self):
        from bot_ia.interfaces.cafe_rooms import mature_game_host, sfw_transition

        transition = sfw_transition("Quiero una bebida whisky para adulto", waitress="Cami")
        self.assertIsNotNone(transition)
        self.assertEqual("#cantina-18", transition.target)
        self.assertEqual("Scarlet", transition.waitress)
        self.assertIn("Cantina +18", transition.message)
        self.assertIn("Scarlet", transition.message)
        self.assertIsNone(sfw_transition("Quiero un café con leche", waitress="Cari"))
        self.assertEqual("Scarlet", mature_game_host("21"))
        self.assertEqual("Scarlet", mature_game_host("blackjack"))
        self.assertEqual("Chloé", mature_game_host("apuestas"))

    def test_inline_external_redirect_and_anti_abuse_contract(self):
        source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "inline_router.py").read_text(encoding="utf-8")
        for token in (
            "class InlineAbuseGuard",
            "class InlineRedirectHandler",
            "3",
            "60.0",
            "Oh... ¿me seguiste hasta aquí?",
            "☕ Ir al Café Otaku",
            "Inline Abuse",
            ">3 consultas Inline/minuto fuera de la comunidad",
        ):
            self.assertIn(token, source)

        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        for token in (
            "TelegramInlineQuery",
            "parse_inline_query_update",
            "answer_inline_query",
            "InlineRedirectHandler",
            "inline_query",
            "CAFE_OTAKU_INVITE_URL",
        ):
            self.assertIn(token, telegram)

        from bot_ia.interfaces.inline_router import InlineAbuseGuard
        guard = InlineAbuseGuard(limit=3, window_seconds=60)
        self.assertIsNone(guard.check("u1", official=False, now=0))
        self.assertIsNone(guard.check("u1", official=False, now=1))
        self.assertIsNone(guard.check("u1", official=False, now=2))
        blocked = guard.check("u1", official=False, now=3)
        self.assertTrue(blocked.blocked)
        self.assertTrue(guard.is_blocked("u1", now=3))

    def test_start_web_chat_accepts_qt_checked_bool_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def start_web_chat(self, button: QPushButton | bool | None = None)", app)
        self.assertIn("if isinstance(button, bool) or button is None:", app)
        self.assertIn("sender = self.sender()", app)
        self.assertIn("isinstance(sender, QPushButton)", app)
        self.assertNotIn("button.setText", app[app.index("def start_web_chat"):app.index("def start_telegram")])

    def test_app_python_and_embedded_js_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        compile(app, "src/gui/app.py", "exec")
        # Any future injected JavaScript must be delimited as a complete script;
        # this contract prevents accidental Python string fragments being added.
        for marker in ("runJavaScript(", "execute_script(", "page.evaluate("):
            if marker in app:
                self.assertNotIn("\\' +", app)

    def test_order_confirmation_and_complaint_refund_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_economy import CafeWalletStore
        from bot_ia.interfaces.order_support import (
            ComplaintStore,
            OrderConfirmation,
            OrderStore,
            order_destination,
        )
        from gui.waifu_registry import WaifuRegistry

        self.assertEqual("🎴 Carta TCG para el Pool", order_destination("Carta TCG"))
        self.assertEqual("🖼️ Imagen IA Personalizada", order_destination("Imagen IA Personalizada"))
        from bot_ia.interfaces.cafe_orders import PRODUCT_TYPES
        self.assertIn("Imagen IA Personalizada", PRODUCT_TYPES)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wallet = CafeWalletStore(root)
            registry = WaifuRegistry(root)
            registry.save([])
            store = ComplaintStore(root)

            complaint = store.create(
                "u-refund",
                "chat-1",
                "La carta no era la que confirmé.",
                order_id="ORD-TEST",
                product_type="Carta TCG",
                points_paid=35,
            )
            self.assertEqual("OPEN", complaint.status)
            self.assertEqual("ORD-TEST", store.get(complaint.complaint_id).order_id)

            before = wallet.balance("u-refund")
            resolved = store.resolve(
                complaint.complaint_id,
                "refund",
                wallet_store=wallet,
                registry=registry,
            )
            self.assertEqual("REFUNDED", resolved.status)
            self.assertEqual(before + 35, wallet.balance("u-refund"))

            raw_registry = (root / "config" / "waifu_registry.json").read_text(encoding="utf-8")
            self.assertIn("complaint_balances", raw_registry)
            self.assertIn(complaint.complaint_id, raw_registry)
            self.assertIn('"balance": 85', raw_registry)

            with self.assertRaises(ValueError):
                store.resolve(
                    complaint.complaint_id,
                    "refund",
                    wallet_store=wallet,
                    registry=registry,
                )

            converted = store.create("u-refund", "chat-1", "Convertir por favor", points_paid=10)
            converted_result = store.resolve(
                converted.complaint_id,
                "convert_image",
                wallet_store=wallet,
                registry=registry,
            )
            self.assertEqual("CONVERTED_TO_IMAGE", converted_result.status)
            self.assertEqual(85, wallet.balance("u-refund"))

            rejected = store.create("u-refund", "chat-1", "No corresponde", points_paid=10)
            rejected_result = store.resolve(
                rejected.complaint_id,
                "reject",
                wallet_store=wallet,
                registry=registry,
            )
            self.assertEqual("REJECTED", rejected_result.status)
            self.assertEqual(85, wallet.balance("u-refund"))

    def test_social_publication_and_dynamic_group_cleanup_contract(self):
        social = (self.ROOT / "src" / "bot_ia" / "interfaces" / "social_publish.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")

        for token in (
            "class SocialPublication",
            "build_hashtags",
            "#AIArt",
            "open_x_draft",
            "https://x.com/intent/post?text=",
        ):
            self.assertIn(token, social)
        for token in (
            'QPushButton("🌐 Publicar en Redes")',
            "build_publication(",
            "open_x_draft(publication)",
            "DISCORD_INVITE_URL",
            "TELEGRAM_INVITE_URL",
        ):
            self.assertIn(token, app)
        for token in (
            "resolve_chat_title",
            'key = "title" if network == "telegram" else "name"',
            "chat_title: str | None = None",
        ):
            self.assertIn(token, immersion)
        self.assertNotIn("☕ Café Otaku ·", immersion)
        for token in (
            "list_guild_channels",
            "cleanup_managed_channels",
            "delete_channel",
            'topic.startswith("BOT-IA · ")',
        ):
            self.assertIn(token, group)

    def test_social_publication_hashtag_contract(self):
        from bot_ia.interfaces.social_publish import build_hashtags
        tags = build_hashtags(character="Kuro", anime="One Neko Punch", outfit="Maid")
        self.assertIn("#Kuro", tags)
        self.assertIn("#OneNekoPunch", tags)
        self.assertIn("#AIArt", tags)
        self.assertIn("#Maid", tags)


    def test_order_confirmation_gui_and_telegram_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        support = (self.ROOT / "src" / "bot_ia" / "interfaces" / "order_support.py").read_text(encoding="utf-8")

        for token in (
            "quote_bebida_order(",
            "⚠️ Confirmación final del pedido",
            "✅ Confirmar",
            "❌ Cancelar",
            "🎴 Carta TCG para el Pool",
            "🖼️ Imagen IA Personalizada",
            "La compra NO se ejecutará hasta pulsar [✅ Confirmar].",
            "📣 Queja / Reembolso",
        ):
            self.assertIn(token, app)

        for token in (
            'command == "/queja"',
            "OrderConfirmation",
            'callback.data == "order:confirm"',
            'callback.data == "order:cancel"',
            "complaint:refund:",
            "complaint:convert_image:",
            "complaint:reject:",
            "TELEGRAM_ADMIN_CHAT_ID",
            "TELEGRAM_ADMIN_USER_IDS",
            "followups=(admin,)",
            "message_thread_id",
        ):
            self.assertIn(token, telegram)

        for token in (
            "class ComplaintStore",
            "def resolve",
            "REFUNDED",
            "CONVERTED_TO_IMAGE",
            "REJECTED",
            "record_complaint_balance",
            "def order_destination",
        ):
            self.assertIn(token, support)

    def test_image_order_resolution_style_and_admin_upload_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_orders import (
            RESOLUTIONS,
            RENDER_STYLES,
            BebidaOrder,
            build_bebida_prompt,
            build_bebida_summary,
        )
        from bot_ia.interfaces.order_support import OrderConfirmation, OrderStore

        self.assertEqual("1104x1824", RESOLUTIONS["XL"])
        self.assertEqual("944x1584", RESOLUTIONS["L"])
        self.assertEqual("768x1280", RESOLUTIONS["M"])
        self.assertIn("classic anime style, cel shaded", RENDER_STYLES["Classic Anime"])
        self.assertIn("retro glam anime, 90s anime aesthetic", RENDER_STYLES["Retro Glam Anime"])
        self.assertIn("modern glam anime, detailed shading, soft lighting", RENDER_STYLES["Modern Glam Anime"])
        self.assertIn("hyper pop style, neon lines, vibrant colors", RENDER_STYLES["Hyper Pop"])

        order = BebidaOrder(
            character="Kuro",
            character_tag="kuro_(one_neko_punch)",
            product_type="Imagen IA Personalizada",
            resolution="XL",
            render_style="Hyper Pop",
        ).normalized()
        summary = build_bebida_summary(order)
        prompt = build_bebida_prompt(order)
        self.assertIn("Resolución: XL (1104x1824)", summary)
        self.assertIn("Estilo: Hyper Pop", summary)
        self.assertIn("Resolution: XL (1104x1824)", prompt)
        self.assertIn("hyper pop style, neon lines, vibrant colors", prompt)

        confirmation = OrderConfirmation(
            order_id="ORD-IMAGE-1",
            user_id="u-image",
            product_type="Imagen IA Personalizada",
            destination="🖼️ Imagen IA Personalizada",
            rarity="SPECIAL",
            cost=150,
            summary=summary,
            resolution="XL",
            render_style="Hyper Pop",
            prompt_en=prompt,
        )
        self.assertEqual("u-image", confirmation.user_id)
        self.assertEqual("XL", confirmation.resolution)
        self.assertIn("Character:", confirmation.prompt_en)

        with TemporaryDirectory() as tmp:
            order_store = OrderStore(Path(tmp))
            order_store.save(confirmation)
            restored = order_store.get("ORD-IMAGE-1")
            self.assertIsNotNone(restored)
            self.assertEqual("XL", restored.resolution)
            self.assertEqual("Hyper Pop", restored.render_style)

        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        orders = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_orders.py").read_text(encoding="utf-8")
        for token in (
            "RESOLUTIONS",
            "RENDER_STYLES",
            'self.resolution = QComboBox()',
            'self.render_style = QComboBox()',
        ):
            self.assertIn(token, app)
        for token in ("1104x1824", "944x1584", "768x1280", "classic anime style, cel shaded"):
            self.assertIn(token, orders)
        for token in (
            "prompt_en=build_bebida_prompt(order)",
            "resolution=order.resolution",
            "render_style=order.render_style",
            "_admin_order_followup",
            "order:attach:",
            "photo_file_id",
            "sendPhoto",
            "handle_photo_update",
            "TELEGRAM_ADMIN_ORDERS_THREAD_ID",
        ):
            self.assertIn(token, telegram)

    def test_admin_order_panel_preserves_spanish_and_english_prompt_contract(self):
        source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        self.assertIn("Texto original en español:", source)
        self.assertIn("Prompt optimizado en inglés:", source)
        self.assertIn("📎 Adjuntar / Subir imagen generada", source)
        self.assertIn("route="order_delivery"", source)
        self.assertIn("pending.user_id", source)

    def test_cross_platform_presence_and_transfer_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.presence import WaitressPresenceManager
        from gui.waifu_registry import WaifuRecord, WaifuRegistry

        manager = WaitressPresenceManager(clock=lambda: 100.0)
        manager.start("Cami", "discord", "procesando pedido")
        reply = manager.reply_for("Cami")
        self.assertTrue(reply.occupied)
        self.assertIn("Cami", reply.message)
        self.assertIn("Discord", reply.message)
        self.assertIn("atendiendo una mesa", reply.message)
        manager.transfer_interaction("Cami", "ORD-42")
        self.assertEqual(1, manager.transferred_count("Cami", "ORD-42"))
        manager.finish("Cami")
        self.assertFalse(manager.reply_for("Cami").occupied)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = WaifuRegistry(root)
            registry.save([WaifuRecord(name="Aki")])
            registry.record_interaction_transfer("u1", "Cami", "ORD-42", points=5)
            raw = (root / "config" / "waifu_registry.json").read_text(encoding="utf-8")
            self.assertIn("interaction_transfers", raw)
            self.assertIn("ORD-42", raw)
            self.assertEqual(1, registry.affinity_level("u1", "Cami"))

    def test_orders_channel_permissions_contract(self):
        source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        self.assertIn('ORDERS_ROOM_KEY = "pedidos"', source)
        self.assertIn("READ_ONLY_ORDERS", source)
        self.assertIn('"can_send_messages": False', source)
        self.assertIn('"attach_files": False', source)
        self.assertIn('key in {ADMIN_ROOM_KEY, ORDERS_ROOM_KEY}', source)
        self.assertIn('"permission_overwrites"', source)

    def test_discord_webhook_avatar_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        self.assertIn("def list_webhooks", group)
        self.assertIn("def create_webhook", group)
        self.assertIn("def ensure_webhook", group)
        self.assertIn("ensure_managed_webhooks", group)
        self.assertIn("waitress_avatar_data_uri", group)
        for token in ("assets", "avatars", "cari.png", "cami.png", "sunna.png", "chie.png", "scarlet.png", "chloe.png", "default.png"):
            self.assertIn(token, immersion)
        self.assertIn("data:image/png;base64,", immersion)


    def test_optional_vip_economy_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_vip import (
            DONATION_BUTTON,
            VIP_DISCORD_ROLE,
            VIP_ROOM_KEY,
            VipStore,
            donation_keyboard,
            vip_policy_text,
        )

        self.assertEqual("VIP", VIP_DISCORD_ROLE)
        self.assertEqual("zona_reservada", VIP_ROOM_KEY)
        self.assertEqual("✨ Apoyar al Café", DONATION_BUTTON)
        self.assertIn("100% gratuito", vip_policy_text())
        self.assertIn("#cantina-18", vip_policy_text())

        with TemporaryDirectory() as tmp:
            store = VipStore(Path(tmp))
            self.assertFalse(store.is_vip("u1"))
            manual = store.grant_manual("u1")
            self.assertTrue(manual.vip)
            self.assertEqual("manual", manual.source)

            donated = store.record_stars("u2", 10)
            self.assertTrue(donated.vip)
            self.assertEqual(10, donated.donated_stars)

            self.assertEqual(donation_keyboard(), ((("✨ Apoyar al Café", "vip:donate"),),))

    def test_vip_discord_setup_and_telegram_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        gui = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        vip = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_vip.py").read_text(encoding="utf-8")

        for token in (
            '"#zona-reservada"',
            '"zona_reservada"',
            'ensure_role(guild_id, "VIP"',
            "color=0xFFD700",
            "permission_overwrites",
        ):
            self.assertIn(token, group)
        for token in (
            'command == "/donar"',
            'command == "/vip"',
            'callback.data == "vip:donate"',
            "successful_payment",
            "validate_donation_event",
            "VipStore",
        ):
            self.assertIn(token, telegram)
        self.assertIn('QPushButton("✨ Apoyar al Café")', gui)
        for token in (
            "El acceso a SFW y #cantina-18 sigue siendo 100% gratuito.",
            "telegram_stars",
            "record_stars",
            "grant_manual",
            "VIP_DISCORD_ROLE",
        ):
            self.assertIn(token, vip)

    def test_group_setup_complaints_topics_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        self.assertIn('"#pedidos-admin"', group)
        self.assertIn('"pedidos_admin"', group)
        self.assertIn('"#atencion-y-quejas"', group)
        self.assertIn('"atencion_quejas"', group)
        self.assertIn('"#pedidos"', group)


    def test_cross_platform_presence_timeout_guard_contract(self):
        from bot_ia.interfaces.cafe_immersion import (
            BUSY_EVENT_TIMEOUT_SECONDS,
            OPPOSITE_NETWORK_LINKS,
            WaitressPresenceManager,
        )

        self.assertEqual(60.0, BUSY_EVENT_TIMEOUT_SECONDS)
        self.assertIn("Telegram", OPPOSITE_NETWORK_LINKS)
        self.assertIn("Discord", OPPOSITE_NETWORK_LINKS)

        now = [100.0]
        manager = WaitressPresenceManager(clock=lambda: now[0])
        self.assertTrue(manager.acquire("Cami", "Telegram", "evt-1", timeout=120))
        self.assertFalse(manager.acquire("Cami", "Discord", "evt-2"))
        message = manager.encargado_message("Cami", "Discord")
        self.assertIn("Cami", message)
        self.assertIn("Telegram", message)
        self.assertIn("https://t.me/eltiootaku", message)

        now[0] += 60.0
        self.assertIsNone(manager.state("Cami"))
        self.assertIsNone(manager.encargado_message("Cami", "Discord"))
        self.assertTrue(manager.acquire("Cami", "Discord", "evt-3"))

    def test_cross_platform_presence_source_contract(self):
        source = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        for token in (
            "WaitressPresenceManager",
            "BUSY_EVENT_TIMEOUT_SECONDS = 60.0",
            "OPPOSITE_NETWORK_LINKS",
            "encargado_message",
            "sweep_expired",
            "min(float(timeout), BUSY_EVENT_TIMEOUT_SECONDS)",
        ):
            self.assertIn(token, source)

    def test_discord_welcome_gate_and_strikes_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.discord_community import (
            STRIKE_TIMEOUT_SECONDS,
            WELCOME_COOLDOWN_SECONDS,
            ImmersiveStrikeEngine,
            StrikeStore,
            WelcomeGate,
            WelcomeDecision,
            admin_strike_actions,
            should_purge,
            welcome_embed_payload,
        )

        self.assertEqual(15.0, WELCOME_COOLDOWN_SECONDS)
        self.assertEqual(3600, STRIKE_TIMEOUT_SECONDS)
        payload = welcome_embed_payload()
        self.assertIn("Sé un buen nakama", payload["description"])
        component_ids = {
            component["custom_id"]
            for row in payload["components"]
            for component in row["components"]
        }
        self.assertEqual({"welcome:user", "welcome:bot"}, component_ids)

        now = [100.0]
        gate = WelcomeGate(clock=lambda: now[0])
        self.assertTrue(gate.start("u1"))
        self.assertFalse(gate.start("u1"))
        self.assertTrue(gate.ignore_during_cooldown("u1"))
        now[0] += 15.0
        self.assertFalse(gate.ignore_during_cooldown("u1"))
        self.assertTrue(gate.choose("u1", "usuario").grant_role)
        self.assertTrue(gate.choose("u2", "bot").kick)

        with TemporaryDirectory() as tmp:
            store = StrikeStore(Path(tmp))
            engine = ImmersiveStrikeEngine(store, superadmin="@tiootakuu")
            first = engine.evaluate("g1", "u1", "severe_profanity")
            second = engine.evaluate("g1", "u1", "severe_profanity")
            third = engine.evaluate("g1", "u1", "spam", burst=True)
            self.assertEqual("warn_delete", engine.action_for(first))
            self.assertEqual("timeout", engine.action_for(second))
            self.assertEqual("isolate", engine.action_for(third))
            self.assertIn("Cari", engine.cari_message(third))
            self.assertEqual("immune", engine.action_for(engine.evaluate("g1", "tiootakuu", "spam")))

        self.assertTrue(should_purge(0, now=7 * 24 * 60 * 60))
        self.assertEqual(0, should_purge(0, now=1))

    def test_discord_welcome_setup_and_strike_source_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        community = (self.ROOT / "src" / "bot_ia" / "interfaces" / "discord_community.py").read_text(encoding="utf-8")
        moderation = (self.ROOT / "src" / "bot_ia" / "interfaces" / "discord_moderation.py").read_text(encoding="utf-8")
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        health = (self.ROOT / "src" / "bot_ia" / "interfaces" / "platform_health.py").read_text(encoding="utf-8")

        for token in (
            '"#bienvenida"',
            '"bienvenida"',
            "ensure_role",
            "welcome_message",
            "send_channel_message",
            "kick_member",
            "add_role",
            "apply_strike",
            "Nakama",
            "Gestionar Roles",
        ):
            self.assertIn(token, group)
        for token in (
            "WELCOME_COOLDOWN_SECONDS = 15.0",
            "STRIKE_TIMEOUT_SECONDS",
            "DiscordWelcomeHandler",
            "DiscordStrikeHandler",
            "admin_strike_actions",
            "TRANSIENT_BOT_MESSAGE_SECONDS",
            "WEEKLY_PURGE_SECONDS",
            "SUPERADMIN_TELEGRAM",
            "@tiootakuu",
        ):
            self.assertIn(token, community)
        for token in (
            "ImmersiveStrikeEngine",
            "is_superadmin",
            "strike_store",
            "burst: bool = False",
            "timeout_member",
            "admin_actions",
        ):
            self.assertIn(token, moderation)
        for token in (
            "PlatformHealthWorker",
            "probe_telegram",
            "probe_discord",
            "🟢 Telegram",
            "🔴 Telegram",
            "🟢 Discord",
            "🔴 Discord",
        ):
            self.assertIn(token, app)
        self.assertIn("https://api.telegram.org", health)
        self.assertIn("https://discord.com/api/v10/users/@me", health)

    def test_welcome_rules_and_transient_cleanup_constants_contract(self):
        from bot_ia.interfaces.discord_community import (
            TRANSIENT_BOT_MESSAGE_SECONDS,
            WEEKLY_PURGE_SECONDS,
            WELCOME_RULES_TEXT,
        )
        self.assertGreaterEqual(TRANSIENT_BOT_MESSAGE_SECONDS, 10)
        self.assertLessEqual(TRANSIENT_BOT_MESSAGE_SECONDS, 30)
        self.assertEqual(7 * 24 * 60 * 60, WEEKLY_PURGE_SECONDS)
        self.assertIn("Sé un buen nakama", WELCOME_RULES_TEXT)

    def test_antimurphy_platform_reconnect_and_async_busy_guard(self):
        import asyncio
        from bot_ia.interfaces.platform_health import PlatformHealth, probe_with_retry
        from bot_ia.interfaces.cafe_immersion import AsyncBusyGuard

        attempts = []
        def flaky_probe():
            attempts.append(True)
            return PlatformHealth("Discord", len(attempts) >= 2, "conectado" if len(attempts) >= 2 else "sin conexión")

        result = probe_with_retry(flaky_probe, retries=2, backoff_seconds=0)
        self.assertTrue(result.ok)
        self.assertEqual(2, len(attempts))

        async def scenario():
            guard = AsyncBusyGuard()
            self.assertTrue(await guard.acquire("cami", timeout=60))
            self.assertFalse(await guard.acquire("cami", timeout=60))
            await guard.release("cami")
            self.assertTrue(await guard.acquire("cami", timeout=60))
            await guard.close()

        asyncio.run(scenario())

    def test_antimurphy_20_messages_per_second_burst_contract(self):
        from bot_ia.interfaces.discord_community import BurstGate, WelcomeGate
        gate = BurstGate(max_events=15, window_seconds=15, clock=lambda: 100.0)
        allowed = sum(gate.allow("welcome:u1") for _ in range(20))
        self.assertEqual(15, allowed)
        self.assertFalse(gate.allow("welcome:u1"))
        welcome = WelcomeGate(clock=lambda: 100.0)
        self.assertTrue(welcome.start("u2"))
        self.assertFalse(welcome.start("u2"))
        self.assertTrue(welcome.ignore_during_cooldown("u2"))

    def test_env_contract_for_discord_and_schrodinger_tokens(self):
        import os
        from bot_ia.interfaces.schrodinger import platform_env_status
        previous = {key: os.environ.get(key) for key in ("DISCORD_BOT_TOKEN", "DISCORD_CLIENT_ID", "SCHRODINGER_BOT_TOKEN")}
        try:
            os.environ["DISCORD_BOT_TOKEN"] = "discord-test"
            os.environ["DISCORD_CLIENT_ID"] = "client-test"
            os.environ["SCHRODINGER_BOT_TOKEN"] = "schrodinger-test"
            self.assertEqual(
                {"DISCORD_BOT_TOKEN": True, "DISCORD_CLIENT_ID": True, "SCHRODINGER_BOT_TOKEN": True},
                platform_env_status(),
            )
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_web_profile_persistence_contract(self):
        source = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        for token in ("WEB_PROFILE_DIR", 'os.getenv("WEB_PROFILE_DIR", "./web_profile")', "launch_persistent_context(", "profile_root"):
            self.assertIn(token, source)

    def test_antimurphy_source_contract(self):
        app = (self.ROOT / "src" / "gui" / "app.py").read_text(encoding="utf-8")
        health = (self.ROOT / "src" / "bot_ia" / "interfaces" / "platform_health.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        community = (self.ROOT / "src" / "bot_ia" / "interfaces" / "discord_community.py").read_text(encoding="utf-8")
        schrodinger = (self.ROOT / "src" / "bot_ia" / "interfaces" / "schrodinger.py").read_text(encoding="utf-8")
        self.assertIn("probe_with_retry(", app)
        self.assertIn("def probe_with_retry(", health)
        self.assertIn("AsyncBusyGuard", immersion)
        self.assertIn("asyncio.create_task", immersion)
        self.assertIn("class BurstGate", community)
        self.assertIn("REQUIRED_PLATFORM_ENV", schrodinger)

    def test_cami_guard_superadmin_content_contract(self):
        from bot_ia.interfaces.cami_guard import (
            DEFAULT_REACTIONS,
            is_superadmin,
            scan_cami_guard,
        )
        from bot_ia.interfaces.cafe_immersion import supervise_admin_publication

        clean = scan_cami_guard(
            "¡Meme de bienvenida al Café!",
            username="@tiootakuu",
            content_kind="meme",
        )
        self.assertEqual("allow_react", clean.action)
        self.assertEqual(DEFAULT_REACTIONS, clean.reactions)
        self.assertFalse(clean.alert_admin)
        self.assertTrue(clean.strike_exempt)

        image_sensitive = scan_cami_guard(
            "Nueva publicación",
            image_tags=("nsfw",),
            username="tiootakuu",
        )
        self.assertEqual("spoiler_redirect", image_sensitive.action)
        self.assertTrue(image_sensitive.spoiler)
        self.assertEqual("#cantina-18", image_sensitive.target_room)
        self.assertTrue(image_sensitive.strike_exempt)

        unsafe = supervise_admin_publication(
            "Anuncio: https://phishing.example/login",
            username="@tiootakuu",
        )
        self.assertEqual("delete_alert", unsafe.action)
        self.assertTrue(unsafe.alert_admin)
        self.assertTrue(unsafe.strike_exempt)

        ordinary = scan_cami_guard("texto normal", username="cliente")
        self.assertEqual("allow", ordinary.action)
        self.assertFalse(ordinary.strike_exempt)
        self.assertTrue(is_superadmin(username="@tiootakuu"))

    def test_cami_guard_gui_alert_contract(self):
        source = (self.ROOT / "src" / "gui" / "incidents_panel.py").read_text(encoding="utf-8")
        guard = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cami_guard.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        for token in (
            "record_cami_guard_alert",
            'kind="Cami Guard"',
            "CAMI-",
            "self.refresh()",
        ):
            self.assertIn(token, source)
        for token in (
            "SENSITIVE_IMAGE_TAGS",
            "BLOCKED_LINK_HOSTS",
            "DEFAULT_REACTIONS",
            "spoiler_redirect",
            "delete_alert",
            "alert_admin",
            "strike_exempt",
            "is_superadmin",
        ):
            self.assertIn(token, guard)
        self.assertIn("supervise_admin_publication", immersion)
        self.assertIn("superadmin_is_immune", immersion)

    def test_cami_guard_telegram_superadmin_integration_contract(self):
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        for token in (
            "supervise_admin_publication",
            "raw_tags = message.get(\"image_tags\", ())",
            "cami_decision.action not in {\"allow\", \"allow_react\"}",
            "self._client.delete_message(chat_id, message_id)",
            "cami_decision.target_room or room_key",
        ):
            self.assertIn(token, telegram)
        for token in (
            "from .cami_guard import",
            "def supervise_admin_publication(",
            "def superadmin_is_immune(",
        ):
            self.assertIn(token, immersion)

    def test_isolated_comment_threads_anti_spam_contract(self):
        from bot_ia.interfaces.cafe_immersion import DiscordCommentThreadManager

        class FakeDiscord:
            def __init__(self):
                self.calls = []

            def create_comment_thread(self, channel_id, message_id, *, name):
                self.calls.append((channel_id, message_id, name))
                return {"id": "thread-1", "name": name}

        client = FakeDiscord()
        manager = DiscordCommentThreadManager(client)
        first = manager.on_announcement(
            author_id="admin",
            superadmin_id="admin",
            channel_id="news",
            message_id="msg-1",
            is_announcement_channel=True,
        )
        duplicate = manager.on_announcement(
            author_id="admin",
            superadmin_id="admin",
            channel_id="news",
            message_id="msg-1",
            is_announcement_channel=True,
        )
        self.assertEqual({"id": "thread-1", "name": "💬 Comentarios"}, first)
        self.assertIsNone(duplicate)
        self.assertEqual([("news", "msg-1", "💬 Comentarios")], client.calls)

        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        self.assertIn('"auto_archive_duration": 1440', group)
        self.assertIn("/messages/{message_id}/threads", group)

    def test_cari_telegram_comments_and_discord_threads_contract(self):
        from bot_ia.interfaces.cafe_immersion import (
            COMMENT_REPLY_TEXT,
            DISCORD_COMMENT_THREAD_NAME,
            analyze_discord_announcement,
            analyze_telegram_comment,
        )
        from bot_ia.interfaces.group_setup import DiscordGroupSetup

        telegram_update = {
            "message": {
                "message_id": 42,
                "from": {"id": 77, "is_bot": False},
                "chat": {"id": -100123},
                "text": "¡Me encanta!",
                "reply_to_message": {"message_id": 12},
            }
        }
        decision = analyze_telegram_comment(telegram_update)
        self.assertTrue(decision.should_reply)
        self.assertEqual("-100123", decision.chat_id)
        self.assertEqual(12, decision.reply_to_message_id)
        self.assertEqual(COMMENT_REPLY_TEXT, decision.text)

        self.assertFalse(
            analyze_telegram_comment(
                {
                    "message": {
                        "message_id": 43,
                        "from": {"id": 78, "is_bot": True},
                        "chat": {"id": -100123},
                        "text": "bot",
                        "reply_to_message": {"message_id": 12},
                    }
                }
            ).should_reply
        )
        self.assertTrue(
            analyze_discord_announcement(
                author_id="999",
                superadmin_id="999",
                channel_id="123",
                is_announcement_channel=True,
            ).should_create
        )
        self.assertFalse(
            analyze_discord_announcement(
                author_id="888",
                superadmin_id="999",
                channel_id="123",
                is_announcement_channel=True,
            ).should_create
        )

        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        self.assertIn("def create_comment_thread", group)
        self.assertIn("/messages/{message_id}/threads", group)
        self.assertIn("analyze_telegram_comment", telegram)
        self.assertIn("reply_to_message_id", telegram)
        self.assertIn("COMMENT_REPLY_TEXT", immersion)
        self.assertIn(DISCORD_COMMENT_THREAD_NAME, immersion)



    def test_ecosystem_cami_sunna_and_inline_anti_murphy_contract(self):
        from bot_ia.interfaces.inline_router import InlineAbuseGuard, InlineRedirectHandler
        from bot_ia.interfaces.cafe_immersion import AsyncBusyGuard, WaitressPresenceManager, waitress_dialogue

        guard = InlineAbuseGuard(limit=3, window_seconds=60)
        self.assertIsNone(guard.check("u1", official=False, now=0))
        self.assertIsNone(guard.check("u1", official=False, now=1))
        self.assertIsNone(guard.check("u1", official=False, now=2))
        blocked = guard.check("u1", official=False, now=3)
        self.assertTrue(blocked.blocked)
        self.assertTrue(guard.is_blocked("u1"))
        self.assertIsNone(guard.check("u1", official=False, now=64))

        handler = InlineRedirectHandler(official_ids={"-100"}, cafe_url="https://t.me/cafe")
        result = handler.handle(user_id="u2", chat_id="outside", query="hola")
        self.assertEqual("☕ Ir al Café Otaku", result.button_label)
        self.assertEqual("https://t.me/cafe", result.button_url)
        self.assertIn("Oh... ¿me seguiste hasta aquí?", result.text)
        self.assertFalse(handler.handle(user_id="u3", chat_id="-100", query="hola").blocked)

        presence = WaitressPresenceManager(clock=lambda: 100.0)
        self.assertTrue(presence.acquire("Cari", "Telegram", "evt-1"))
        self.assertIn("Discord", presence.encargado_message("Cari", "Telegram"))
        self.assertFalse(presence.acquire("Cari", "Discord", "evt-2"))
        self.assertIn("Café", waitress_dialogue("Cari", chat_title="Servidor Real"))

        async def busy_contract():
            busy = AsyncBusyGuard()
            self.assertTrue(await busy.acquire("cari", timeout=60))
            self.assertTrue(await busy.busy("cari"))
            await busy.release("cari")
            self.assertFalse(await busy.busy("cari"))
            await busy.close()

        asyncio.run(busy_contract())

        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        for token in (
            "SUNNA_PRIMARY_ADMIN",
            "AUTHORIZED_BOT_TOKEN_ENV",
            "can_invite_users",
            "can_delete_messages",
            "can_restrict_members",
            "can_manage_topics",
            "configure_authorized_bots",
        ):
            self.assertIn(token, group)
        self.assertIn("InlineRedirectHandler", telegram)
        self.assertIn("parse_inline_query_update", telegram)
        self.assertIn("analyze_telegram_comment", telegram)
        self.assertIn("_sync_authorized_bot_join", telegram)
        self.assertIn("new_chat_members", telegram)
        self.assertIn("AsyncBusyGuard", immersion)

    def test_telegram_setup_read_only_orders_and_role_policy_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        for token in (
            'ORDERS_ROOM_KEY = "pedidos"',
            "READ_ONLY_ORDERS",
            '"can_send_messages": False',
            '"send_messages": False',
            "permission_overwrites",
            "SUNNA_BOT_TOKEN",
            "CARI_BOT_TOKEN",
            "CAMI_BOT_TOKEN",
            "SCHRODINGER_BOT_TOKEN",
        ):
            self.assertIn(token, group)
        # Telegram Forum Topics no tienen permisos independientes: el contrato
        # exige que esta limitación no se presente como una capacidad inexistente.
        self.assertIn("no admite permisos independientes por tema de foro", group)

    def test_cami_guard_zero_strike_and_comments_are_integrated(self):
        immersion = (self.ROOT / "src" / "bot_ia" / "interfaces" / "cafe_immersion.py").read_text(encoding="utf-8")
        telegram = (self.ROOT / "src" / "bot_ia" / "interfaces" / "telegram.py").read_text(encoding="utf-8")
        for token in (
            "supervise_admin_publication",
            "superadmin_is_immune",
            "scan_cami_guard",
            "SENSITIVE_IMAGE_TAGS",
            "DEFAULT_REACTIONS",
            "COMMENT_REPLY_TEXT",
            "DISCORD_COMMENT_THREAD_NAME",
        ):
            self.assertIn(token, immersion)
        for token in (
            "analyze_telegram_comment",
            "cami_decision",
            "is_superadmin",
            "parse_inline_query_update",
            "InlineRedirectHandler",
        ):
            self.assertIn(token, telegram)


if __name__ == "__main__":
    unittest.main()
