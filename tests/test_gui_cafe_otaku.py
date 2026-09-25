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

    def test_order_confirmation_and_complaint_refund_contract(self):
        from tempfile import TemporaryDirectory
        from bot_ia.interfaces.cafe_economy import CafeWalletStore
        from bot_ia.interfaces.order_support import (
            ComplaintStore,
            OrderConfirmation,
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
        from bot_ia.interfaces.cafe_orders import (
            RESOLUTIONS,
            RENDER_STYLES,
            BebidaOrder,
            build_bebida_prompt,
            build_bebida_summary,
        )
        from bot_ia.interfaces.order_support import OrderConfirmation

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

    def test_group_setup_complaints_topics_contract(self):
        group = (self.ROOT / "src" / "bot_ia" / "interfaces" / "group_setup.py").read_text(encoding="utf-8")
        self.assertIn('"#pedidos-admin"', group)
        self.assertIn('"pedidos_admin"', group)
        self.assertIn('"#atencion-y-quejas"', group)
        self.assertIn('"atencion_quejas"', group)
        self.assertIn('"#pedidos"', group)



if __name__ == "__main__":
    unittest.main()
