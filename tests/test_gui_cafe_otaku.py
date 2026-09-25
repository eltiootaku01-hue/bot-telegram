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
            self.assertEqual(60 - GACHA_COST, store.balance("u1"))
            self.assertIn("Cami", result.consolation)
            self.assertIn("R", maid_consolation("Cari", "R"))
            self.assertEqual({"21": 10, "uno": 12, "ppt": 5}, GAME_REWARDS)

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
        flow = BebidaOrderFlow()
        flow.start("user-1", "Aki")
        flow.set_character("user-1", "Aki", "aki_(anime)")
        flow.choose("user-1", "exposure", "SFW")
        flow.choose("user-1", "boldness", "Atrevido")
        order = flow.choose("user-1", "product_type", "Waifumon")
        self.assertEqual("aki_(anime)", order.character_tag)
        self.assertIn("Character tag: aki_(anime)", build_bebida_prompt(order))
        self.assertEqual(EXPOSURE_LEVELS[0], "SFW")
        self.assertIn("Atrevido", BOLDNESS_LEVELS)
        self.assertIn("Waifumon", PRODUCT_TYPES)

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


if __name__ == "__main__":
    unittest.main()
