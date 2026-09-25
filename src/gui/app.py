# -*- coding: utf-8 -*-
"""Ventana principal Dark Cozy de Café Otaku sobre el backend único de BOT-IA."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import traceback
from contextlib import closing
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from PySide6.QtCore import (
    QEvent,
    QObject,
    QRunnable,
    QThread,
    QThreadPool,
    QTimer,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter, QPixmap
from core.config import DynamicConfigManager
from .admin_provisioning import AdminProvisioner
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from bot_ia.core.application import ApplicationRequest
from bot_ia.core.web_queue import WebQueueManager
from .task_orchestrator import Priority, TaskOrchestrator
from bot_ia.core.waitress_session_manager import (
    InsufficientBalanceError,
    SessionConflictError,
    SessionExpiredError,
    TavernConfigurationError,
    TavernError,
    WaitressSessionManager,
    WaitressUnavailableError,
)
from bot_ia.runtime import RuntimeComponents, build_runtime
from .gui_bridge import WorkerSignals
from .styles import application_qss
from .widgets import BotTile, CardFrame, PillButton, SectionHeader
from .waifu_registry import (
    CardSlot,
    WaifuRecord,
    WaifuRegistry,
    crop_sprite_to_ratio,
    frame_candidates,
    generate_tcg_prompt,
    normalize_lora_tags,
    record_progress,
    slugify,
)
from .mini_games import LocalGameRouter

try:
    from qasync import QEventLoop
except ImportError:
    QEventLoop = None


ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
)
DESKTOP_USER = "desktop-user"
DESKTOP_SESSION = "desktop-session"


@dataclass(frozen=True, slots=True)
class BotProfile:
    bot_id: str
    name: str
    avatar: str
    short_role: str


BOT_PROFILES = (
    BotProfile("cari", "Cari", "🦫✨", "Capibara feliz"),
    BotProfile("cami", "Cami", "🦫👓", "Capibara seria"),
    BotProfile("sunna", "Sunna", "🐍⚪", "Serpiente blanca"),
    BotProfile("chie", "Chie", "🐭", "Ratonsito"),
    BotProfile("chloe", "Chloe", "🦇", "Murciélago"),
    BotProfile("scarlet", "Scarlet", "🧛‍♀️", "Vampiresa"),
)
BOT_MAP = {item.bot_id: item for item in BOT_PROFILES}


class GUIBridgeSignalAdapter:
    """Adapta estados del orquestador a señales Qt del puente visual."""

    def __init__(self, signals: WorkerSignals) -> None:
        self.signals = signals

    def emit_status_change(
        self,
        waitress_id: str,
        status: str,
    ) -> None:
        self.signals.status_changed.emit(
            waitress_id,
            status,
        )


class GuiSignals(QObject):
    application_finished = Signal(object)
    application_failed = Signal(str)
    notification = Signal(str, str)
    status_changed = Signal()
    web_result = Signal(str, str)
    web_failed = Signal(str, str)
    web_state = Signal(str)


class ApplicationTask(QRunnable):
    """Ejecuta BotApplication fuera del hilo de la GUI."""

    def __init__(
        self,
        signals: GuiSignals,
        application: object,
        request: ApplicationRequest,
    ) -> None:
        super().__init__()
        self.signals = signals
        self.application = application
        self.request = request
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            response = self.application.handle(self.request)
            self.signals.application_finished.emit(response)
        except Exception as error:
            self.signals.application_failed.emit(
                f"{type(error).__name__}: {error}"
            )


@dataclass(frozen=True, slots=True)
class ProviderWebSpec:
    """Configuración web de un proveedor de chat para la matriz."""

    provider_id: str
    display_name: str
    default_url: str
    new_chat_selectors: tuple[str, ...]
    input_selectors: tuple[str, ...]
    response_selectors: tuple[str, ...]


PROVIDER_WEB_SPECS = {
    "gemini": ProviderWebSpec(
        "gemini",
        "Google Gemini",
        "https://gemini.google.com/app",
        (
            "button[aria-label*='Nuevo chat']",
            "button[aria-label*='New chat']",
            "a[aria-label*='Nuevo chat']",
            "a[aria-label*='New chat']",
            "button:has-text('Nuevo chat')",
            "button:has-text('New chat')",
        ),
        (
            "div[contenteditable='true']",
            "textarea[aria-label*='prompt']",
            "rich-textarea div.ql-editor",
        ),
        (
            "model-response",
            "message-content .markdown",
            ".model-response-text",
            "div[data-test-id='conversation-turn']",
        ),
    ),
    "chatgpt": ProviderWebSpec(
        "chatgpt",
        "OpenAI ChatGPT",
        "https://chatgpt.com/",
        (
            "button[data-testid='create-new-chat-button']",
            "a[aria-label*='New chat']",
            "button[aria-label*='New chat']",
            "a[aria-label*='Nuevo chat']",
            "button[aria-label*='Nuevo chat']",
            "button:has-text('New chat')",
            "button:has-text('Nuevo chat')",
        ),
        (
            "#prompt-textarea",
            "textarea[placeholder*='Message']",
            "div[contenteditable='true']",
        ),
        (
            "[data-message-author-role='assistant']",
            "article[data-testid^='conversation-turn'] "
            "[data-message-author-role='assistant']",
            "div[data-testid^='conversation-turn']",
        ),
    ),
    "copilot": ProviderWebSpec(
        "copilot",
        "Microsoft Copilot",
        "https://copilot.microsoft.com/",
        (
            "button[aria-label*='New chat']",
            "button[aria-label*='Nuevo chat']",
            "button:has-text('New chat')",
            "button:has-text('Nuevo chat')",
        ),
        ("textarea", "div[contenteditable='true']"),
        (
            "[data-message-author-role='assistant']",
            "[data-testid*='assistant']",
            ".response-message",
            ".message-content",
        ),
    ),
    "grok_claude": ProviderWebSpec(
        "grok_claude",
        "Grok / Claude",
        "https://grok.com/",
        (
            "button[aria-label*='New chat']",
            "button[aria-label*='New conversation']",
            "button[title*='New chat']",
            "button[title*='New conversation']",
            "a[aria-label*='New chat']",
            "button:has-text('New chat')",
            "button:has-text('New conversation')",
            "button:has-text('Nuevo chat')",
        ),
        (
            "textarea",
            "div[contenteditable='true']",
        ),
        (
            "[data-message-author-role='assistant']",
            "[data-testid*='assistant']",
            "[data-content='ai-message']",
            ".message-content",
        ),
    ),
}


MATRIX_INITIALIZATION_ORDER = (
    "cari",
    "cami",
    "sunna",
    "chie",
)


@dataclass(frozen=True, slots=True)
class MatrixBotSpec:
    """Configuración aislada de cada cuadrante de la matriz."""

    bot_id: str
    display_name: str
    browser_profile: str
    row: int
    column: int
    default_system_prompt: str
    default_provider: str = "gemini"


MATRIX_BOT_SPECS = (
    MatrixBotSpec(
        "cari",
        "Cari",
        "./browser_data/cari",
        0,
        0,
        "Actúa como Cari, anfitriona del Café Otaku. "
        "Temas: bienvenida, atención, coordinación del lobby y tono cálido. "
        "Aplica esta directiva antes de ejecutar cualquier comando.",
    ),
    MatrixBotSpec(
        "sunna",
        "Sunna",
        "./browser_data/sunna",
        0,
        1,
        "Actúa como Sunna, responsable de lore y trivia del Café Otaku. "
        "Temas: continuidad, datos del universo, trivia y precisión contextual. "
        "Aplica esta directiva antes de ejecutar cualquier comando.",
    ),
    MatrixBotSpec(
        "cami",
        "Cami",
        "./browser_data/cami",
        1,
        0,
        "Actúa como Cami, moderadora del Café Otaku. "
        "Temas: orden de conversación, moderación, seguridad y coordinación. "
        "Aplica esta directiva antes de ejecutar cualquier comando.",
    ),
    MatrixBotSpec(
        "chie",
        "Chie",
        "./browser_data/chie",
        1,
        1,
        "Actúa como Chie, gestora de XP del Café Otaku. "
        "Temas: progreso, XP, recompensas y seguimiento de actividad. "
        "Aplica esta directiva antes de ejecutar cualquier comando.",
    ),
)


INITIAL_SETUP_MODE_ENV = "INITIAL_SETUP_MODE"

LIGHTWEIGHT_CHROMIUM_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--hide-crash-restore-bubble",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-sandbox",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-client-side-phishing-detection",
    "--disable-default-apps",
    "--disable-hang-monitor",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--no-zygote",
    "--renderer-process-limit=2",
)


def _initial_setup_mode() -> bool:
    value = os.getenv(INITIAL_SETUP_MODE_ENV, "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _lightweight_browser_args(*, headless: bool) -> list[str]:
    args = list(LIGHTWEIGHT_CHROMIUM_ARGS)
    if headless:
        args.insert(0, "--headless=new")
    if (
        headless
        and os.getenv("PLAYWRIGHT_DISABLE_IMAGES", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    ):
        args.append("--blink-settings=imagesEnabled=false")
    if os.getenv("PLAYWRIGHT_SINGLE_PROCESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        args.append("--single-process")
    return args


class GeminiLobbyWorker(QObject):
    """Worker síncrono de Playwright para un perfil web aislado."""

    finished = Signal(str)
    failed = Signal(str)
    ready = Signal(str)

    CONTEXT_ACK_TOKEN = "CONTEXTO_LISTO"
    TIMEOUT_MS = 30_000
    SETUP_LOGIN_TIMEOUT_MS = 300_000
    NEW_CHAT_TIMEOUT_MS = 8_000
    POLL_INTERVAL_MS = 100
    STABLE_POLLS = 2

    def __init__(
        self,
        bot_id: str,
        browser_profile: str,
        system_prompt: str,
        command: str,
        provider_id: str = "gemini",
        provider_url: str = "",
    ) -> None:
        super().__init__()
        self.bot_id = bot_id
        self.browser_profile = browser_profile
        self.system_prompt = system_prompt.strip()
        self.command = command.strip()
        self.provider_id = provider_id.strip().lower()
        self.provider_url = provider_url.strip()

    @property
    def provider(self) -> ProviderWebSpec:
        try:
            return PROVIDER_WEB_SPECS[self.provider_id]
        except KeyError as error:
            raise ValueError(
                f"{self.bot_id}: proveedor web no soportado: {self.provider_id!r}"
            ) from error

    @property
    def start_url(self) -> str:
        provider = self.provider
        if self.provider_id == "gemini":
            configured = os.getenv("BOT_IA_GEMINI_URL", "")
        elif self.provider_id == "chatgpt":
            configured = os.getenv("BOT_IA_CHATGPT_URL", "")
        elif self.provider_id == "copilot":
            configured = os.getenv("BOT_IA_COPILOT_URL", "")
        else:
            configured = (
                self.provider_url
                or os.getenv("BOT_IA_GROK_CLAUDE_URL", "")
            )
        return configured.strip() or provider.default_url

    @property
    def setup_mode(self) -> bool:
        return _initial_setup_mode()

    @property
    def headless(self) -> bool:
        return not self.setup_mode

    @property
    def browser_args(self) -> list[str]:
        return _lightweight_browser_args(headless=self.headless)

    def build_prompt(self) -> str:
        if not self.system_prompt:
            raise ValueError(
                f"{self.bot_id}: la directiva de actuación no puede estar vacía."
            )
        if not self.command:
            raise ValueError(
                f"{self.bot_id}: el comando no puede estar vacío."
            )
        return (
            "PERSONALIDAD / DIRECTIVA DE ACTUACIÓN:\n"
            f"{self.system_prompt}\n\n"
            "REGLA DE INICIALIZACIÓN:\n"
            "Comprende y aplica la personalidad y los temas anteriores antes "
            "de ejecutar el comando. Confirma que el contexto fue aceptado "
            f"incluyendo exactamente la etiqueta {self.CONTEXT_ACK_TOKEN} "
            "en tu respuesta.\n\n"
            "COMANDO DE LOBBY:\n"
            f"{self.command}"
        )

    def _wait_for_visible(
        self,
        page,
        selectors: tuple[str, ...],
        timeout_ms: int,
    ):
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            for selector in selectors:
                locator = page.locator(selector)
                try:
                    count = locator.count()
                except Exception as error:
                    _ = error
                    continue
                for index in range(count):
                    candidate = locator.nth(index)
                    try:
                        if candidate.is_visible():
                            return candidate
                    except Exception as error:
                        _ = error
            page.wait_for_timeout(self.POLL_INTERVAL_MS)
        raise TimeoutError(
            f"{self.bot_id}: no apareció un selector visible de "
            f"{self.provider.display_name}."
        )

    def _open_new_chat(self, page) -> None:
        new_chat = self._wait_for_visible(
            page,
            self.provider.new_chat_selectors,
            self.NEW_CHAT_TIMEOUT_MS,
        )
        new_chat.click()
        page.wait_for_timeout(500)
        self._wait_for_visible(
            page,
            self.provider.input_selectors,
            self.NEW_CHAT_TIMEOUT_MS,
        )

    def _read_response(
        self,
        page,
        baseline_count: int,
        baseline_text: str,
    ) -> str:
        deadline = time.monotonic() + self.TIMEOUT_MS / 1000
        previous_text = baseline_text
        stable_polls = 0
        response_selector = ", ".join(self.provider.response_selectors)

        while time.monotonic() < deadline:
            responses = page.locator(response_selector)
            count = responses.count()
            if count:
                current_text = (
                    responses.nth(count - 1).inner_text()
                ).strip()
                is_new = count > baseline_count
                changed = bool(current_text) and current_text != baseline_text
                if current_text and (is_new or changed):
                    if current_text == previous_text:
                        stable_polls += 1
                    else:
                        stable_polls = 0
                    previous_text = current_text
                    if stable_polls >= self.STABLE_POLLS:
                        return current_text
            page.wait_for_timeout(self.POLL_INTERVAL_MS)

        raise TimeoutError(
            f"{self.bot_id}: {self.provider.display_name} no produjo "
            "una respuesta estable a tiempo."
        )

    @Slot()
    def run(self) -> None:
        context = None
        playwright = None
        try:
            prompt = self.build_prompt()
            playwright = sync_playwright().start()
            context = playwright.chromium.launch_persistent_context(
                self.browser_profile,
                headless=self.headless,
                args=self.browser_args,
            )
            page = context.new_page()
            page.goto(
                self.start_url,
                wait_until="domcontentloaded",
                timeout=self.TIMEOUT_MS,
            )
            if not self.setup_mode:
                self._open_new_chat(page)

            response_selector = ", ".join(
                self.provider.response_selectors
            )
            response_locator = page.locator(response_selector)
            baseline_count = response_locator.count()
            baseline_text = ""
            if baseline_count:
                baseline_text = (
                    response_locator.nth(baseline_count - 1)
                    .inner_text()
                    .strip()
                )

            login_timeout = (
                self.SETUP_LOGIN_TIMEOUT_MS
                if self.setup_mode
                else self.TIMEOUT_MS
            )
            input_locator = self._wait_for_visible(
                page,
                self.provider.input_selectors,
                login_timeout,
            )
            input_locator.fill(prompt)
            input_locator.press("Enter")

            response_text = self._read_response(
                page,
                baseline_count,
                baseline_text,
            )
            if self.CONTEXT_ACK_TOKEN.casefold() not in response_text.casefold():
                raise RuntimeError(
                    f"{self.bot_id}: el modelo no confirmó el contexto "
                    f"con {self.CONTEXT_ACK_TOKEN}."
                )

            self.finished.emit(response_text)
            self.ready.emit(self.bot_id)
        except Exception as error:
            self.failed.emit(
                f"{self.bot_id}: {type(error).__name__}: {error}"
            )
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception as error:
                    _ = error
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception as error:
                    _ = error


class ManualBrowserSetupWorker(QObject):
    """Abre un Chromium nativo para autenticación humana y persiste el perfil."""

    finished = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    TIMEOUT_MS = 300_000
    POLL_INTERVAL_MS = 500
    MANUAL_CHROMIUM_ARGS = (
        "--disable-blink-features=AutomationControlled",
        "--hide-crash-restore-bubble",
        "--no-first-run",
    )

    def __init__(
        self,
        bot_id: str,
        browser_profile: str,
        provider_id: str = "gemini",
        provider_url: str = "",
    ) -> None:
        super().__init__()
        self.bot_id = bot_id
        self.browser_profile = browser_profile
        self.provider_id = provider_id.strip().lower()
        self.provider_url = provider_url.strip()

    @property
    def provider(self) -> ProviderWebSpec:
        try:
            return PROVIDER_WEB_SPECS[self.provider_id]
        except KeyError as error:
            raise ValueError(
                f"{self.bot_id}: proveedor web no soportado: "
                f"{self.provider_id!r}"
            ) from error

    @property
    def start_url(self) -> str:
        if self.provider_id == "gemini":
            configured = os.getenv("BOT_IA_GEMINI_URL", "")
        elif self.provider_id == "chatgpt":
            configured = os.getenv("BOT_IA_CHATGPT_URL", "")
        elif self.provider_id == "copilot":
            configured = os.getenv("BOT_IA_COPILOT_URL", "")
        else:
            configured = (
                self.provider_url
                or os.getenv("BOT_IA_GROK_CLAUDE_URL", "")
            )
        return configured.strip() or self.provider.default_url

    def _persist_state(self, context, profile_path: Path) -> None:
        state_path = profile_path / "storage_state.json"
        try:
            context.storage_state(
                path=str(state_path),
                indexed_db=True,
            )
        except TypeError:
            # Compatibilidad con Playwright anterior a indexed_db.
            context.storage_state(path=str(state_path))

    @Slot()
    def run(self) -> None:
        playwright = None
        context = None
        profile_path = Path(self.browser_profile).resolve()
        timed_out = False
        closed_by_user = False

        try:
            profile_path.mkdir(parents=True, exist_ok=True)
            playwright = sync_playwright().start()

            # IMPORTANTE: headed + no_viewport mantiene una ventana nativa
            # independiente del QWebEngineView de la GUI. No se instala
            # ningún autenticador WebAuthn virtual: Google/Windows puede
            # presentar el flujo real de passkey/security key.
            context = playwright.chromium.launch_persistent_context(
                str(profile_path),
                headless=False,
                no_viewport=True,
                args=list(self.MANUAL_CHROMIUM_ARGS),
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(
                self.start_url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            self.status.emit(
                f"{self.bot_id}: Chromium externo abierto. "
                "Completa correo, contraseña y 2FA/passkey; "
                "cierra la ventana cuando termines."
            )

            deadline = time.monotonic() + self.TIMEOUT_MS / 1000
            current_thread = QThread.currentThread()
            while (
                time.monotonic() < deadline
                and not current_thread.isInterruptionRequested()
            ):
                try:
                    pages = context.pages
                    if not pages or all(
                        current_page.is_closed() for current_page in pages
                    ):
                        closed_by_user = True
                        break
                    page.wait_for_timeout(self.POLL_INTERVAL_MS)
                except Exception:
                    closed_by_user = True
                    break
            else:
                timed_out = True

            self._persist_state(context, profile_path)

            if timed_out:
                self.finished.emit(
                    f"{self.bot_id}: tiempo de configuración agotado. "
                    "Perfil persistido y Chromium cerrado."
                )
            elif closed_by_user:
                self.finished.emit(
                    f"{self.bot_id}: configuración manual finalizada. "
                    "Perfil persistido y Chromium cerrado."
                )
            else:
                self.finished.emit(
                    f"{self.bot_id}: configuración manual finalizada."
                )
        except Exception as error:
            self.failed.emit(
                f"{self.bot_id}: {type(error).__name__}: {error}"
            )
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception as error:
                    _ = error
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception as error:
                    _ = error


class SequentialChatDispatcher(QObject):
    """Inicialización serial: Cari → Cami → Sunna → Chie."""

    finished = Signal(dict)
    failed = Signal(str)
    bot_started = Signal(str)
    bot_finished = Signal(str, str)
    bot_ready = Signal(str)
    bot_failed = Signal(str, str)

    def __init__(
        self,
        specs: tuple[MatrixBotSpec, ...] = MATRIX_BOT_SPECS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.specs = tuple(specs)
        self._spec_by_id = {spec.bot_id: spec for spec in self.specs}
        self._order = tuple(
            bot_id
            for bot_id in MATRIX_INITIALIZATION_ORDER
            if bot_id in self._spec_by_id
        )
        self._index = 0
        self._command = ""
        self._system_prompts: dict[str, str] = {}
        self._providers: dict[str, str] = {}
        self._provider_urls: dict[str, str] = {}
        self._results: dict[str, str] = {}
        self._errors: dict[str, str] = {}
        self._active_thread: QThread | None = None
        self._active_worker: GeminiLobbyWorker | None = None
        self._stopping = False
        self._chain_running = False

    @property
    def is_running(self) -> bool:
        return self._chain_running

    def start(
        self,
        command: str,
        system_prompts: dict[str, str],
        providers: dict[str, str] | None = None,
        provider_urls: dict[str, str] | None = None,
        *,
        start_bot_id: str = "cari",
    ) -> bool:
        if self.is_running or self._stopping:
            return False

        command = command.strip()
        if not command:
            self.failed.emit("El comando del Lobby no puede estar vacío.")
            return False

        if start_bot_id not in self._order:
            self.failed.emit(
                f"No existe el bot de matriz solicitado: {start_bot_id}."
            )
            return False

        self._index = self._order.index(start_bot_id)
        self._command = command
        self._system_prompts = {
            bot_id: system_prompts.get(
                bot_id,
                self._spec_by_id[bot_id].default_system_prompt,
            ).strip()
            for bot_id in self._order
        }
        raw_providers = providers or {}
        self._providers = {
            bot_id: raw_providers.get(
                bot_id,
                self._spec_by_id[bot_id].default_provider,
            ).strip().lower()
            for bot_id in self._order
        }
        raw_urls = provider_urls or {}
        self._provider_urls = {
            bot_id: raw_urls.get(bot_id, "").strip()
            for bot_id in self._order
        }
        self._results = {}
        self._errors = {}
        self._stopping = False
        self._chain_running = True
        self._start_next()
        return True

    def _start_next(self) -> None:
        if self._stopping:
            return

        if self._index >= len(self._order):
            self._chain_running = False
            self.finished.emit(
                {
                    "ok": not self._errors,
                    "command": self._command,
                    "order": list(self._order),
                    "results": dict(self._results),
                    "errors": dict(self._errors),
                }
            )
            return

        bot_id = self._order[self._index]
        spec = self._spec_by_id[bot_id]
        worker = GeminiLobbyWorker(
            bot_id,
            spec.browser_profile,
            self._system_prompts.get(
                bot_id,
                spec.default_system_prompt,
            ),
            self._command,
            self._providers.get(
                bot_id,
                spec.default_provider,
            ),
            self._provider_urls.get(bot_id, ""),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        self.bot_started.emit(bot_id)
        thread.started.connect(worker.run)
        worker.finished.connect(
            lambda response, current_bot=bot_id: self._on_bot_finished(
                current_bot,
                response,
            )
        )
        worker.ready.connect(self._on_bot_ready)
        worker.failed.connect(
            lambda error, current_bot=bot_id: self._on_bot_failed(
                current_bot,
                error,
            )
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda current_bot=bot_id, current_thread=thread, current_worker=worker:
            self._on_thread_finished(
                current_bot,
                current_thread,
                current_worker,
            )
        )

        self._active_thread = thread
        self._active_worker = worker
        thread.start()

    def _on_bot_finished(self, bot_id: str, response: str) -> None:
        self._results[bot_id] = response
        self.bot_finished.emit(bot_id, response)

    def _on_bot_ready(self, bot_id: str) -> None:
        self.bot_ready.emit(bot_id)

    def _on_bot_failed(self, bot_id: str, error: str) -> None:
        self._errors[bot_id] = error
        self.bot_failed.emit(bot_id, error)

    def _on_thread_finished(
        self,
        bot_id: str,
        thread: QThread,
        worker: GeminiLobbyWorker,
    ) -> None:
        if self._active_thread is thread:
            self._active_thread = None
        if self._active_worker is worker:
            self._active_worker = None

        if self._stopping:
            return

        if bot_id in self._errors:
            self._chain_running = False
            self.finished.emit(
                {
                    "ok": False,
                    "command": self._command,
                    "order": list(self._order),
                    "results": dict(self._results),
                    "errors": dict(self._errors),
                }
            )
            return

        self._index += 1
        QTimer.singleShot(0, self._start_next)

    def stop(self) -> None:
        self._stopping = True
        self._chain_running = False
        thread = self._active_thread
        if thread is None:
            self._active_worker = None
            return

        thread.requestInterruption()
        thread.quit()
        if thread.isRunning():
            thread.wait(1_000)
        self._active_thread = None
        self._active_worker = None


class SystemDiagnosticWorker(QObject):
    """Inspector Sentry que verifica salud web, Telegram, providers y SQLite."""

    finished = Signal(dict)
    failed = Signal(str)

    TELEGRAM_TIMEOUT_SECONDS = 8.0
    PROVIDER_TIMEOUT_SECONDS = 8.0
    BROWSER_TIMEOUT_MS = 10_000
    BROWSER_DATA_DIR = Path("./browser_data")
    GEMINI_URL = "https://gemini.google.com"
    GEMINI_INPUT_SELECTOR = "div[contenteditable='true']"

    def __init__(
        self,
        project_root: Path,
        database_path: Path,
        runtime_config: object,
    ) -> None:
        super().__init__()
        self.project_root = Path(project_root)
        self.database_path = Path(database_path)
        self.runtime_config = runtime_config

    @staticmethod
    def _provider_endpoint(
        provider_id: str,
        base_url: str,
    ) -> str | None:
        normalized = provider_id.strip().lower()
        if normalized == "ollama":
            root = (
                base_url.rstrip("/")
                if base_url
                else "http://127.0.0.1:11434"
            )
            return f"{root}/api/tags"

        defaults = {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
        }
        if normalized in defaults:
            root = base_url.rstrip("/") if base_url else defaults[normalized]
            return f"{root}/models"
        return None

    @staticmethod
    def _http_get(
        url: str,
        *,
        token: str | None = None,
        timeout_seconds: float,
    ) -> int:
        headers = {
            "User-Agent": "BOT-IA-Sentry/1.0",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status)

    def _check_gemini_web(self) -> dict[str, object]:
        browser_path = (
            self.project_root / self.BROWSER_DATA_DIR
        ).resolve()
        result: dict[str, object] = {
            "status": "warning",
            "severity": "warning",
            "path": str(browser_path),
            "session_ready": False,
            "cause": "",
            "suggestion": "",
        }

        if not browser_path.is_dir():
            result.update(
                cause="No existe el perfil persistente browser_data.",
                suggestion=(
                    "Inicia Gemini Lobby una vez para crear la "
                    "sesión persistente."
                ),
            )
            return result

        context = None
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    str(browser_path),
                    headless=True,
                    args=_lightweight_browser_args(headless=True),
                )
                page = (
                    context.pages[0]
                    if context.pages
                    else context.new_page()
                )
                page.goto(
                    self.GEMINI_URL,
                    wait_until="domcontentloaded",
                    timeout=self.BROWSER_TIMEOUT_MS,
                )
                locator = page.locator(self.GEMINI_INPUT_SELECTOR)
                ready = any(
                    locator.nth(index).is_visible()
                    for index in range(locator.count())
                )
                result.update(
                    status="ok" if ready else "warning",
                    severity="info" if ready else "warning",
                    session_ready=ready,
                    page_url=page.url,
                    cause=(
                        ""
                        if ready
                        else (
                            "Gemini cargó, pero no apareció el "
                            "editor autenticado."
                        )
                    ),
                    suggestion=(
                        ""
                        if ready
                        else (
                            "Comprueba que la sesión de Google siga "
                            "activa en browser_data."
                        )
                    ),
                )
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            locked = any(
                token in message.lower()
                for token in ("lock", "in use", "user data directory")
            )
            result.update(
                status="in_use" if locked else "error",
                severity="warning" if locked else "error",
                cause=message,
                suggestion=(
                    "Cierra otra ventana que esté usando browser_data "
                    "y repite el diagnóstico."
                    if locked
                    else (
                        "Revisa Chromium de Playwright y la sesión "
                        "persistente de Gemini."
                    )
                ),
            )
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception as error:
                    _ = error
        return result

    def _check_telegram(self) -> list[dict[str, object]]:
        keys = ["TELEGRAM_BOT_TOKEN"] + [
            f"BOT_TOKEN_{profile.bot_id.upper()}"
            for profile in BOT_PROFILES
        ]
        report: list[dict[str, object]] = []

        for key in keys:
            token = os.getenv(key, "").strip()
            if not token:
                report.append(
                    {
                        "token": key,
                        "status": "missing_credentials",
                        "severity": "error",
                        "cause": "No hay token configurado.",
                        "suggestion": (
                            f"Guarda {key} desde la gestión de "
                            "PROVEEDORES LLM / APIs y BOTS."
                        ),
                    }
                )
                continue

            try:
                status_code = self._http_get(
                    f"https://api.telegram.org/bot{token}/getMe",
                    timeout_seconds=self.TELEGRAM_TIMEOUT_SECONDS,
                )
                ok = 200 <= status_code < 300
                report.append(
                    {
                        "token": key,
                        "status": "ok" if ok else "error",
                        "severity": "info" if ok else "error",
                        "http_status": status_code,
                        "cause": (
                            ""
                            if ok
                            else "Telegram respondió con estado no exitoso."
                        ),
                        "suggestion": (
                            ""
                            if ok
                            else "Verifica el token y el estado del bot."
                        ),
                    }
                )
            except HTTPError as error:
                report.append(
                    {
                        "token": key,
                        "status": "error",
                        "severity": "error",
                        "http_status": error.code,
                        "cause": "Telegram rechazó getMe.",
                        "suggestion": (
                            "Verifica el token y los permisos del bot."
                        ),
                    }
                )
            except (URLError, OSError, TimeoutError):
                report.append(
                    {
                        "token": key,
                        "status": "error",
                        "severity": "error",
                        "cause": "Telegram no fue accesible desde esta sesión.",
                        "suggestion": (
                            "Comprueba la conectividad hacia "
                            "api.telegram.org."
                        ),
                    }
                )
        return report

    def _check_providers(self) -> list[dict[str, object]]:
        report: list[dict[str, object]] = []
        for provider in getattr(
            self.runtime_config,
            "providers",
            (),
        ):
            provider_id = getattr(provider, "provider_id", "")
            if not getattr(provider, "enabled", False):
                continue

            accounts = getattr(provider, "accounts", ()) or (None,)
            for account in accounts:
                if account is not None and not getattr(
                    account,
                    "enabled",
                    True,
                ):
                    continue

                account_id = (
                    getattr(account, "account_id", provider_id)
                    if account is not None
                    else provider_id
                )
                secret_env = (
                    getattr(account, "secret_env", "")
                    if account is not None
                    else ""
                )
                endpoint = self._provider_endpoint(
                    provider_id,
                    getattr(provider, "base_url", ""),
                )

                if endpoint is None:
                    report.append(
                        {
                            "provider": provider_id,
                            "account": account_id,
                            "status": "not_checked",
                            "severity": "warning",
                            "cause": (
                                "No existe un endpoint genérico seguro "
                                "para este provider."
                            ),
                            "suggestion": (
                                "Ejecuta una petición real desde el "
                                "flujo normal del provider."
                            ),
                        }
                    )
                    continue

                token = (
                    os.getenv(secret_env, "").strip()
                    if secret_env
                    else None
                )
                if secret_env and not token:
                    report.append(
                        {
                            "provider": provider_id,
                            "account": account_id,
                            "status": "missing_credentials",
                            "severity": "error",
                            "cause": f"No existe {secret_env}.",
                            "suggestion": (
                                "Guarda la credencial desde "
                                "PROVEEDORES LLM / APIs."
                            ),
                        }
                    )
                    continue

                try:
                    status_code = self._http_get(
                        endpoint,
                        token=(
                            token
                            if provider_id != "ollama"
                            else None
                        ),
                        timeout_seconds=self.PROVIDER_TIMEOUT_SECONDS,
                    )
                    ok = 200 <= status_code < 300
                    report.append(
                        {
                            "provider": provider_id,
                            "account": account_id,
                            "status": "ok" if ok else "error",
                            "severity": "info" if ok else "error",
                            "http_status": status_code,
                            "cause": (
                                ""
                                if ok
                                else (
                                    "El endpoint respondió con "
                                    "estado no exitoso."
                                )
                            ),
                            "suggestion": (
                                ""
                                if ok
                                else (
                                    "Revisa credenciales, URL y cuota "
                                    "del provider."
                                )
                            ),
                        }
                    )
                except HTTPError as error:
                    report.append(
                        {
                            "provider": provider_id,
                            "account": account_id,
                            "status": "error",
                            "severity": "error",
                            "http_status": error.code,
                            "cause": (
                                "El provider rechazó la consulta de salud."
                            ),
                            "suggestion": (
                                "Verifica credenciales y disponibilidad "
                                "del servicio."
                            ),
                        }
                    )
                except (URLError, OSError, TimeoutError) as error:
                    report.append(
                        {
                            "provider": provider_id,
                            "account": account_id,
                            "status": "error",
                            "severity": "error",
                            "cause": f"{type(error).__name__}: {error}",
                            "suggestion": (
                                "Comprueba red, DNS y URL del provider."
                            ),
                        }
                    )
        return report

    def _check_sqlite(self) -> dict[str, object]:
        result: dict[str, object] = {
            "status": "error",
            "severity": "error",
            "path": str(self.database_path),
            "quick_check": None,
            "cause": "",
            "suggestion": "",
        }
        if not self.database_path.is_file():
            result.update(
                cause="La base de datos de eventos no existe.",
                suggestion=(
                    "Inicializa el runtime para crear la base SQLite."
                ),
            )
            return result

        try:
            with closing(
                sqlite3.connect(
                    self.database_path,
                    timeout=2.0,
                )
            ) as connection:
                row = connection.execute(
                    "PRAGMA quick_check"
                ).fetchone()
            value = row[0] if row else None
            ok = value == "ok"
            result.update(
                status="ok" if ok else "error",
                severity="info" if ok else "error",
                quick_check=value,
                cause=(
                    ""
                    if ok
                    else "PRAGMA quick_check no devolvió ok."
                ),
                suggestion=(
                    ""
                    if ok
                    else (
                        "Detén workers activos y revisa o restaura "
                        "la copia de seguridad SQLite."
                    )
                ),
            )
        except (OSError, sqlite3.Error) as error:
            result.update(
                cause=f"{type(error).__name__}: {error}",
                suggestion=(
                    "Comprueba bloqueo, permisos y espacio disponible "
                    "del archivo SQLite."
                ),
            )
        return result

    def run(self) -> None:
        try:
            report: dict[str, object] = {
                "ok": True,
                "browser": self._check_gemini_web(),
                "telegram": self._check_telegram(),
                "providers": self._check_providers(),
                "sqlite": self._check_sqlite(),
                "errors": [],
                "suggestions": [],
            }

            sections = (
                report["browser"],
                report["telegram"],
                report["providers"],
                report["sqlite"],
            )
            for section in sections:
                items = (
                    section
                    if isinstance(section, list)
                    else [section]
                )
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("severity") == "error":
                        report["ok"] = False
                    cause = str(item.get("cause", "")).strip()
                    suggestion = str(
                        item.get("suggestion", "")
                    ).strip()
                    if cause and isinstance(
                        report["errors"],
                        list,
                    ):
                        report["errors"].append(cause)
                    if suggestion and isinstance(
                        report["suggestions"],
                        list,
                    ):
                        report["suggestions"].append(suggestion)

            report["errors"] = list(
                dict.fromkeys(report["errors"])
            )
            report["suggestions"] = list(
                dict.fromkeys(report["suggestions"])
            )
            self.finished.emit(report)
        except Exception as error:
            self.failed.emit(
                f"{type(error).__name__}: {error}"
            )


class BotExpandedDialog(QDialog):
    """Visor ampliado con proveedor, estado de sesión y contador de uso."""

    send_requested = Signal(str, str)
    manual_requested = Signal(str)
    start_requested = Signal(str)
    provider_changed = Signal(str, str)

    def __init__(self, profile: BotProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bot_id = profile.bot_id
        self.setWindowTitle(f"{profile.avatar} {profile.name} · Visor ampliado")
        self.setMinimumSize(980, 680)
        self.resize(1180, 780)
        self._usage_seconds: dict[str, int] = {}
        self._active_provider = ""
        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(1000)
        self._usage_timer.timeout.connect(self._tick_usage)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"{profile.avatar} {profile.name}")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        role = QLabel(profile.short_role)
        role.setObjectName("Muted")
        header.addWidget(role)
        header.addStretch(1)
        self.led = QLabel("🔴 Desconectado")
        self.led.setObjectName("Muted")
        header.addWidget(self.led)
        self.status = QLabel("En espera")
        self.status.setObjectName("Muted")
        header.addWidget(self.status)
        root.addLayout(header)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Proveedor web"))
        self.provider = QComboBox()
        self.provider.addItem("Google Gemini", "gemini")
        self.provider.addItem("OpenAI ChatGPT", "chatgpt")
        self.provider.addItem("Microsoft Copilot", "copilot")
        self.provider.addItem("Grok / Claude", "grok_claude")
        self.provider.currentIndexChanged.connect(self._provider_changed)
        controls.addWidget(self.provider, 1)
        self.usage = QLabel("Uso activo: 00:00:00 · proveedor")
        self.usage.setObjectName("Muted")
        controls.addWidget(self.usage)

        self.start_button = QPushButton("▶ Iniciar desde este bot")
        self.start_button.clicked.connect(lambda: self.start_requested.emit(self.bot_id))
        controls.addWidget(self.start_button)
        self.manual_button = QPushButton("🔑 Registrarse / Candado")
        self.manual_button.clicked.connect(lambda: self.manual_requested.emit(self.bot_id))
        controls.addWidget(self.manual_button)
        self.waifu_button = QPushButton("🎴 Waifu / TCG")
        self.waifu_button.clicked.connect(self._open_waifu)
        controls.addWidget(self.waifu_button)
        root.addLayout(controls)

        self.auth_hint = QLabel(
            "La sesión persistente se guarda en ./browser_data/<bot>. "
            "El LED indica que existe estado de autenticación local."
        )
        self.auth_hint.setObjectName("Muted")
        self.auth_hint.setWordWrap(True)
        root.addWidget(self.auth_hint)

        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlaceholderText("Historial completo de actividad de este bot…")
        root.addWidget(self.history, 1)

        composer = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Escribe un mensaje para este bot…")
        self.input.returnPressed.connect(self._emit_message)
        composer.addWidget(self.input, 1)
        send = QPushButton("Enviar")
        send.clicked.connect(self._emit_message)
        composer.addWidget(send)
        root.addLayout(composer)

    def _open_waifu(self) -> None:
        parent = self.parent()
        if isinstance(parent, CommandCenterWindow):
            parent._open_waifu_registry(self.bot_id)

    def _provider_changed(self, _index: int) -> None:
        provider_id = str(self.provider.currentData() or "").strip()
        if not provider_id:
            return
        self._set_active_provider(provider_id)
        self.provider_changed.emit(self.bot_id, provider_id)

    def _set_active_provider(self, provider_id: str) -> None:
        self._active_provider = provider_id
        self._refresh_usage_label()
        self._update_usage_timer()

    def _update_usage_timer(self) -> None:
        if self.led.text().startswith("🟢"):
            if not self._usage_timer.isActive():
                self._usage_timer.start()
        else:
            self._usage_timer.stop()

    def _tick_usage(self) -> None:
        if not self._active_provider or not self.led.text().startswith("🟢"):
            return
        self._usage_seconds[self._active_provider] = self._usage_seconds.get(
            self._active_provider, 0
        ) + 1
        self._refresh_usage_label()

    def _refresh_usage_label(self) -> None:
        seconds = self._usage_seconds.get(self._active_provider, 0)
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        self.usage.setText(
            f"Uso activo: {hours:02d}:{minutes:02d}:{secs:02d} · "
            f"{self._active_provider or 'proveedor'}"
        )

    def _emit_message(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.append_history("Tú", text)
        self.send_requested.emit(self.bot_id, text)

    def set_provider(self, provider_id: str) -> None:
        index = self.provider.findData(provider_id)
        if index >= 0 and index != self.provider.currentIndex():
            self.provider.blockSignals(True)
            self.provider.setCurrentIndex(index)
            self.provider.blockSignals(False)
        self._set_active_provider(provider_id)

    def set_connection_state(self, authenticated: bool, detail: str = "") -> None:
        self.led.setText(
            "🟢 Autenticado y Activo"
            if authenticated
            else "🔴 Desconectado"
        )
        if detail:
            self.status.setText(detail)
        self._update_usage_timer()

    def set_status(self, status: str) -> None:
        self.status.setText(status)

    def append_history(self, speaker: str, text: str) -> None:
        clean = str(text).strip()
        if clean:
            self.history.appendPlainText(f"{speaker}: {clean}")

    def closeEvent(self, event: object) -> None:
        self._usage_timer.stop()
        self.hide()
        event.accept()


class WaifuRegistryDialog(QDialog):
    """Panel local para registrar waifus, generar prompts y ensamblar cartas."""

    def __init__(
        self,
        registry: WaifuRegistry,
        *,
        bot_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.registry = registry
        self.bot_id = bot_id
        self.records = self.registry.load()
        self.image_path = ""
        self.assembled_path = ""
        self.card_slots = [
            CardSlot("Carta 1", "R"),
            CardSlot("Carta 2", "SR"),
            CardSlot("Cosplay UR", "UR"),
        ]
        self.selected_slot_index = 0
        self.setWindowTitle("🎴 Registro de Waifus · TCG")
        self.setMinimumSize(920, 700)
        self.resize(1080, 780)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("🎴 Registro de Waifus")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.record_count = QLabel()
        self.record_count.setObjectName("Muted")
        header.addWidget(self.record_count)
        root.addLayout(header)

        form = QGridLayout()
        form.addWidget(QLabel("Nombre"), 0, 0)
        self.name = QLineEdit()
        form.addWidget(self.name, 0, 1)
        form.addWidget(QLabel("Personalidad / Trope"), 1, 0)
        self.personality = QLineEdit()
        form.addWidget(self.personality, 1, 1)
        form.addWidget(QLabel("Apariencia"), 2, 0)
        self.appearance = QLineEdit()
        form.addWidget(self.appearance, 2, 1)
        form.addWidget(QLabel("Elemento"), 3, 0)
        self.element = QComboBox()
        self.element.addItems(
            ("Fuego", "Agua", "Tierra", "Aire", "Luz", "Oscuridad", "Neutro")
        )
        form.addWidget(self.element, 3, 1)
        form.addWidget(QLabel("Referencia Cosplay"), 4, 0)
        self.cosplay = QComboBox()
        self.cosplay.addItems(("SR", "UR"))
        form.addWidget(self.cosplay, 4, 1)
        form.addWidget(QLabel("Categoría de carta"), 5, 0)
        self.card_category = QComboBox()
        self.card_category.addItems(
            ("Waifu / TCG", "Cartas de Juego", "Póker", "UNO")
        )
        form.addWidget(self.card_category, 5, 1)
        form.addWidget(QLabel("Etiquetas LoRA"), 6, 0)
        self.lora_tags = QLineEdit()
        self.lora_tags.setPlaceholderText("[LORA_NAME], [STYLE_TAG]")
        form.addWidget(self.lora_tags, 6, 1)
        form.addWidget(QLabel("Slot de carta"), 7, 0)
        self.card_slot = QComboBox()
        self.card_slot.addItems(
            ("Carta 1 · R", "Carta 2 · SR", "Cosplay UR · UR")
        )
        self.card_slot.currentIndexChanged.connect(self._select_slot)
        form.addWidget(self.card_slot, 7, 1)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.generate_button = QPushButton("Generar Prompt")
        self.generate_button.clicked.connect(self._generate)
        actions.addWidget(self.generate_button)
        self.upload_button = QPushButton("+ Subir Imagen")
        self.upload_button.clicked.connect(self._upload)
        actions.addWidget(self.upload_button)
        self.assemble_button = QPushButton("🃏 Ensamblar Carta")
        self.assemble_button.clicked.connect(self._assemble)
        actions.addWidget(self.assemble_button)
        self.save_button = QPushButton("💾 Registrar / Guardar")
        self.save_button.clicked.connect(self._save)
        actions.addWidget(self.save_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText(
            "El prompt TCG optimizado aparecerá aquí..."
        )
        self.prompt.setMinimumHeight(170)
        root.addWidget(self.prompt)

        self.image_label = QLabel(
            "Sin sprite. Usa «+ Subir Imagen» después de generar el prompt."
        )
        self.image_label.setObjectName("Muted")
        self.image_label.setMinimumHeight(90)
        self.image_label.setWordWrap(True)
        root.addWidget(self.image_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.status = QLabel("Listo. Todo el registro funciona localmente.")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.records_view = QPlainTextEdit()
        self.records_view.setReadOnly(True)
        self.records_view.setPlaceholderText("Registro guardado...")
        root.addWidget(self.records_view, 1)

        self.slot_status = QPlainTextEdit()
        self.slot_status.setReadOnly(True)
        self.slot_status.setMaximumHeight(100)
        self.slot_status.setPlaceholderText("Tracker de cartas...")
        root.addWidget(self.slot_status)

        self._refresh_records()
        self._refresh_slot_status()

    def _select_slot(self, index: int) -> None:
        self.selected_slot_index = max(0, min(index, len(self.card_slots) - 1))
        slot = self.card_slots[self.selected_slot_index]
        self.image_path = slot.image_path
        self.assembled_path = slot.assembled_path
        self.progress.setValue(slot.progress)
        if self.image_path:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                self.image_label.setPixmap(
                    pixmap.scaled(
                        220,
                        220,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self.image_label.setText("")
        self._refresh_slot_status()

    def _refresh_slot_status(self) -> None:
        lines = []
        for slot in self.card_slots:
            state = "COMPLETA" if slot.complete else "PENDIENTE"
            lines.append(
                f"{slot.name} [{slot.rarity}] · {slot.progress}% · {state}"
            )
        self.slot_status.setPlainText("\n".join(lines))
        self.progress.setValue(
            record_progress(
                WaifuRecord(
                    name=self.name.text().strip(),
                    personality=self.personality.text().strip(),
                    appearance=self.appearance.text().strip(),
                    element=str(self.element.currentText()).strip(),
                    cosplay_reference=str(self.cosplay.currentText()).strip(),
                    card_slots=self.card_slots,
                )
            )
        )

    def _current_record(self) -> WaifuRecord:
        return WaifuRecord(
            name=self.name.text().strip(),
            personality=self.personality.text().strip(),
            appearance=self.appearance.text().strip(),
            element=str(self.element.currentText()).strip(),
            cosplay_reference=str(self.cosplay.currentText()).strip(),
            card_category=str(self.card_category.currentText()).strip(),
            lora_tags=normalize_lora_tags(self.lora_tags.text()),
            prompt=self.prompt.toPlainText().strip(),
            image_path=self.image_path,
            assembled_path=self.assembled_path,
            progress=self.progress.value(),
            card_slots=self.card_slots,
        )

    def _generate(self) -> None:
        record = self._current_record()
        if not record.name:
            self.status.setText("Escribe un nombre antes de generar el prompt.")
            return
        record.prompt = generate_tcg_prompt(record)
        self.prompt.setPlainText(record.prompt)
        self.progress.setValue(max(self.progress.value(), 25))
        self.status.setText(
            "Prompt TCG generado: sprite aislado sobre fondo blanco, "
            "sin marco ni texto para facilitar la composición."
        )

    def _upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar sprite de waifu",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp);;Todos los archivos (*)",
        )
        if not path:
            return
        self.image_path = str(Path(path).resolve())
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            preview = pixmap.scaled(
                220,
                220,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_label.setPixmap(preview)
            self.image_label.setText("")
        else:
            self.image_label.setText(f"Imagen seleccionada: {self.image_path}")
        slot = self.card_slots[self.selected_slot_index]
        slot.image_path = self.image_path
        slot.complete = False
        self.progress.setValue(max(self.progress.value(), 50))
        self._refresh_slot_status()
        self.status.setText(
            f"Sprite cargado para {slot.name}. Ya puede ensamblarse en una carta."
        )

    def _save(self) -> None:
        record = self._current_record()
        record.prompt = (
            self.prompt.toPlainText().strip()
            or generate_tcg_prompt(record)
        )
        existing = next(
            (
                item
                for item in self.records
                if item.name.casefold() == record.name.casefold()
            ),
            None,
        )
        if existing is None:
            self.records.append(record)
        else:
            existing.personality = record.personality
            existing.appearance = record.appearance
            existing.element = record.element
            existing.cosplay_reference = record.cosplay_reference
            existing.card_category = record.card_category
            existing.lora_tags = record.lora_tags
            existing.prompt = record.prompt
            existing.image_path = record.image_path or existing.image_path
            existing.assembled_path = (
                record.assembled_path or existing.assembled_path
            )
            existing.card_slots = record.card_slots
            existing.progress = record.progress
        self.registry.save(self.records)
        self._refresh_records()
        self.status.setText("Waifu registrada en config/waifu_registry.json.")

    def _assemble(self) -> None:
        slot = self.card_slots[self.selected_slot_index]
        if not self.image_path:
            self.status.setText(
                f"Primero usa «+ Subir Imagen» para {slot.name}."
            )
            return

        sprite = QPixmap(self.image_path)
        if sprite.isNull():
            self.status.setText("No se pudo leer el sprite seleccionado.")
            return

        # Auto-Crop & Fit: detecta contenido, centra y conserva proporción.
        target_ratio = 1.0 if "Póker" in self.card_category.currentText() else 3 / 4
        cropped = crop_sprite_to_ratio(
            sprite.toImage(),
            ratio=target_ratio,
        )
        if cropped.isNull():
            self.status.setText("No se pudo calcular el Auto-Crop del sprite.")
            return
        sprite = QPixmap.fromImage(cropped)

        rarity = slot.rarity
        element = str(self.element.currentText()).strip()
        name = self.name.text().strip() or "Waifu"
        frame_path = next(
            (path for path in frame_candidates(
                self.registry.root, rarity, element
            ) if path.is_file()),
            None,
        )
        if frame_path is None:
            self.status.setText(
                f"No existe un marco {rarity} en assets/tcg_frames."
            )
            return

        out_dir = self.registry.root / "artifacts" / "tcg_cards"
        out_dir.mkdir(parents=True, exist_ok=True)
        output = out_dir / (
            f"{slugify(name)}_{slugify(slot.name)}_"
            f"{slugify(element)}_{rarity}.png"
        )

        canvas = QPixmap(768, 1024)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        try:
            fitted = sprite.scaled(
                690,
                790,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            x = (768 - fitted.width()) // 2
            painter.drawPixmap(x, 150, fitted)

            frame = QPixmap(str(frame_path))
            if frame.isNull():
                self.status.setText(
                    f"No se pudo cargar el marco: {frame_path.name}"
                )
                return
            painter.drawPixmap(0, 0, frame.scaled(
                768, 1024, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            ))

            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Georgia", 28, QFont.Bold))
            painter.drawText(42, 62, name)

            painter.setFont(QFont("Georgia", 18, QFont.Bold))
            painter.drawText(42, 94, f"{rarity} · {element}")

            painter.setFont(QFont("Georgia", 14))
            painter.drawText(42, 990, "BOT-IA · TCG LOCAL")
        finally:
            painter.end()

        if not canvas.save(str(output), "PNG"):
            self.status.setText("No se pudo guardar la carta ensamblada.")
            return

        slot.assembled_path = str(output)
        slot.complete = True
        self.assembled_path = str(output)
        self.progress.setValue(100)
        self._refresh_slot_status()
        self.status.setText(
            f"{slot.name} ensamblada con marco {rarity}: {output}"
        )
        self._save()

    def _refresh_records(self) -> None:
        self.record_count.setText(f"{len(self.records)} registro(s)")
        lines = []
        for item in self.records:
            lines.append(
                f"• {item.name} · {item.element} · {item.cosplay_reference} · "
                f"{item.progress}%"
            )
            if item.assembled_path:
                lines.append(f"  Carta: {item.assembled_path}")
        self.records_view.setPlainText("\n".join(lines))


class CommandCenterWindow(QMainWindow):
    """UI principal que conserva el runtime y backend existentes."""

    def __init__(self, runtime: RuntimeComponents | None = None) -> None:
        load_dotenv(ROOT / ".env", override=False)
        super().__init__()
        self.setWindowTitle("Casa de Comando · BOT-IA")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)

        self.runtime = runtime or build_runtime(ROOT)
        self.application = self.runtime.build_application(
            default_universe_id=os.getenv(
                "BOT_IA_UNIVERSE",
                "one_neko_punch",
            ),
            provider_id=os.getenv(
                "BOT_IA_PROVIDER",
                "openai",
            ),
        )
        self.default_universe = os.getenv(
            "BOT_IA_UNIVERSE",
            "one_neko_punch",
        )
        self.provider_id = os.getenv(
            "BOT_IA_PROVIDER",
            "openai",
        )

        self.signals = GuiSignals()
        self.bridge_signals = WorkerSignals()
        self.bridge_signal_adapter = GUIBridgeSignalAdapter(
            self.bridge_signals
        )
        self.bridge_signals.status_changed.connect(
            self._on_async_status_changed
        )
        self.bridge_signals.message_received.connect(
            self._on_async_message_received
        )
        self.signals.application_finished.connect(
            self._on_application_finished
        )
        self.signals.application_failed.connect(
            self._on_application_failed
        )
        self.signals.notification.connect(
            self._on_tavern_notification
        )
        self.signals.status_changed.connect(
            self.refresh_state
        )
        self.signals.web_result.connect(
            self._on_web_state
        )
        self.signals.web_failed.connect(
            self._on_web_state
        )
        self.signals.web_state.connect(
            self._on_web_state
        )

        self.task_pool = QThreadPool(self)
        self.task_pool.setMaxThreadCount(3)
        self._pending_tasks = 0
        self._closing = False
        self._last_execution = None
        self._tavern_ticket_ids: set[str] = set()
        self._web_ticket_ids: dict[str, str] = {}
        self._web_ticket_sequence = 0
        self._selected_bot_id = "cari"
        self._web_queue = None
        self._tavern: WaitressSessionManager | None = None
        self._telegram_process: subprocess.Popen[str] | None = None
        self._web_chat_process: subprocess.Popen[str] | None = None
        self._async_orchestrator: TaskOrchestrator | None = None
        self._async_web_queue: WebQueueManager | None = None
        self._dialogs: list[QWidget] = []
        self.config_manager = DynamicConfigManager(
            ROOT,
            runtime=self.runtime,
        )
        self._config_dialog_fields: dict[str, dict[str, QLineEdit]] = {}
        self._diagnostic_thread: QThread | None = None
        self._diagnostic_worker: SystemDiagnosticWorker | None = None
        self._manual_setup_thread: QThread | None = None
        self._manual_setup_worker: ManualBrowserSetupWorker | None = None
        self._bot_credentials = {
            f"BOT_TOKEN_{profile.bot_id.upper()}": os.getenv(
                f"BOT_TOKEN_{profile.bot_id.upper()}", ""
            ).strip()
            for profile in BOT_PROFILES
        }
        self._matrix_dispatcher = SequentialChatDispatcher(parent=self)
        self._matrix_widgets: dict[str, dict[str, object]] = {}
        self._expanded_bot_dialogs: dict[str, BotExpandedDialog] = {}
        self.waifu_registry = WaifuRegistry(ROOT)
        self._waifu_dialog: WaifuRegistryDialog | None = None
        self._mini_game_router = LocalGameRouter()
        self._mini_games_dialog: QDialog | None = None
        self._matrix_chain_running = False
        self._matrix_chain_button: QPushButton | None = None
        self._matrix_chain_summary: QLabel | None = None
        self._matrix_dispatcher.bot_started.connect(
            self._on_matrix_bot_started
        )
        self._matrix_dispatcher.bot_finished.connect(
            self._on_matrix_bot_finished
        )
        self._matrix_dispatcher.bot_failed.connect(
            self._on_matrix_bot_failed
        )
        self._matrix_dispatcher.finished.connect(
            self._on_matrix_chain_finished
        )
        self._matrix_dispatcher.failed.connect(
            self._on_matrix_chain_failed
        )
        self._telegram_poll_timer = QTimer(self)
        self._telegram_poll_timer.setInterval(1000)
        self._telegram_poll_timer.timeout.connect(
            self._refresh_telegram_process
        )

        self._configure_window()
        self._build_layout()
        self._wire_backend()
        self._load_web_page()
        self.refresh_state()
        self._telegram_poll_timer.start()

        self._append_system(
            "Bienvenido al Café Otaku. El chat central usa el mismo "
            "BotApplication, memoria, evidencia y providers que el resto "
            "del sistema."
        )

    # ------------------------------------------------------------------
    # Ventana y layout
    # ------------------------------------------------------------------

    def _activate_admin_mode(self, checked: bool = True) -> None:
        """Activa el modo admin y aprovisiona estructuras locales de forma idempotente."""
        if not checked:
            self._admin_mode = False
            self.statusBar().showMessage("Modo Administrador desactivado.", 5000)
            return

        try:
            result = self.admin_provisioner.activate(self.config_manager)
            self._admin_mode = True
            self.admin_button.setChecked(True)
            self.statusBar().showMessage(
                "Modo Administrador activado: Paneles y temas estructurados correctamente.",
                10000,
            )
            self._append_system(
                "Modo Administrador activado: Paneles y temas estructurados correctamente. "
                f"Paneles={len(result['panels'])} · Temas={len(result['themes'])}."
            )
            self.refresh_state()
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            self._admin_mode = False
            self.admin_button.setChecked(False)
            self.statusBar().showMessage(
                f"No se pudo aprovisionar el modo Administrador: {type(error).__name__}.",
                10000,
            )
            self._append_system(
                f"Error de aprovisionamiento administrador: {type(error).__name__}: {error}"
            )

    def _configure_window(self) -> None:
        self.setStyleSheet(application_qss())
        self.setStatusBar(QStatusBar(self))
        self.statusBar().setObjectName("FooterBar")

    def _build_layout(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 10)
        root_layout.setSpacing(10)

        top = QFrame()
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 12)

        brand = QLabel("☕ Café Otaku")
        brand.setObjectName("BrandTitle")
        top_layout.addWidget(brand)

        self.page_title = QLabel("Lobby")
        self.page_title.setObjectName("PageTitle")
        top_layout.addWidget(self.page_title)
        top_layout.addStretch(1)

        self.universe_label = QLabel()
        self.universe_label.setObjectName("Muted")
        top_layout.addWidget(self.universe_label)

        self.operations_button = QPushButton("⚙ Panel")
        self.operations_button.clicked.connect(
            lambda: self._set_page(1)
        )
        top_layout.addWidget(self.operations_button)

        self.local_web_button = QPushButton("🌐 Chat local")
        self.local_web_button.clicked.connect(self.start_web_chat)
        top_layout.addWidget(self.local_web_button)

        self.web_button = QPushButton("🌐 Web")
        self.web_button.clicked.connect(
            lambda: self._set_page(2)
        )
        top_layout.addWidget(self.web_button)

        self.admin_button = QPushButton("👑 Soy Admin")
        self.admin_button.setCheckable(True)
        self.admin_button.setToolTip(
            "Activa el aprovisionamiento local de paneles, temas y variables base."
        )
        self.admin_button.clicked.connect(self._activate_admin_mode)
        top_layout.addWidget(self.admin_button)

        self.diagnostic_button = QPushButton("🔍 Diagnóstico")
        self.diagnostic_button.clicked.connect(
            self._show_diagnostic_dialog
        )
        top_layout.addWidget(self.diagnostic_button)

        self.manual_login_button = QPushButton(
            "🔑 Iniciar Sesión Manual"
        )
        self.manual_login_button.setToolTip(
            "Activa INITIAL_SETUP_MODE para que la próxima cadena "
            "abra Chromium visible y permita completar el inicio de sesión."
        )
        self.manual_login_button.clicked.connect(
            self._enable_manual_setup_mode
        )
        top_layout.addWidget(self.manual_login_button)

        root_layout.addWidget(top)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        splitter.addWidget(self._build_sidebar())

        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(8, 0, 8, 0)
        middle_layout.addWidget(self._build_chat_card(), 1)
        splitter.addWidget(middle)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._build_web_card(), 1)
        splitter.addWidget(right)

        splitter.setSizes((250, 720, 430))
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)

        title = QLabel("Meseras & mascotas")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Estado real de la Taberna cuando existe en SQLite."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(5)

        self.bot_tiles: dict[str, BotTile] = {}
        for profile in BOT_PROFILES:
            tile = BotTile(
                profile.bot_id,
                profile.avatar,
                profile.name,
                profile.short_role,
            )
            tile.clicked_bot.connect(self._on_bot_tile_clicked)
            layout.addWidget(tile)
            self.bot_tiles[profile.bot_id] = tile

        layout.addStretch(1)

        selected_card = CardFrame()
        selected_layout = QVBoxLayout(selected_card)
        selected_layout.setContentsMargins(12, 12, 12, 12)
        self.selected_label = QLabel()
        self.selected_label.setObjectName("PageTitle")
        self.selected_role = QLabel()
        self.selected_role.setObjectName("Muted")
        self.selected_status = QLabel()
        self.selected_status.setWordWrap(True)
        selected_layout.addWidget(self.selected_label)
        selected_layout.addWidget(self.selected_role)
        selected_layout.addSpacing(5)
        selected_layout.addWidget(self.selected_status)

        actions = QHBoxLayout()
        self.start_chat_button = QPushButton("☕ Charla 3 min")
        self.start_chat_button.clicked.connect(self._start_selected_tavern_session)
        actions.addWidget(self.start_chat_button)
        self.force_rest_button = QPushButton("💤 Forzar descanso")
        self.force_rest_button.clicked.connect(self._force_selected_rest)
        actions.addWidget(self.force_rest_button)
        selected_layout.addLayout(actions)

        layout.addWidget(selected_card)

        self.waifu_sidebar_button = QPushButton("🎴 Registro de Waifus")
        self.waifu_sidebar_button.setToolTip(
            "Registrar waifus, generar prompts TCG y ensamblar cartas localmente."
        )
        self.waifu_sidebar_button.clicked.connect(self._open_waifu_registry)
        layout.addWidget(self.waifu_sidebar_button)

        self.mini_games_sidebar_button = QPushButton("🎮 Mini-Juegos")
        self.mini_games_sidebar_button.setToolTip(
            "PPT y 21/Blackjack local; las respuestas no pasan por WebQueue."
        )
        self.mini_games_sidebar_button.clicked.connect(self._open_mini_games)
        layout.addWidget(self.mini_games_sidebar_button)

        return panel

    def _build_chat_card(self) -> QWidget:
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.chat_title = QLabel("Lobby general")
        self.chat_title.setObjectName("PageTitle")
        header.addWidget(self.chat_title)
        header.addStretch(1)

        self.chat_mode = QComboBox()
        self.chat_mode.addItems(
            (
                "Lobby general · BotApplication",
                "Taberna · SQLite + WebQueue",
                "Web persona · WebQueue",
            )
        )
        self.chat_mode.currentIndexChanged.connect(
            self._on_chat_mode_changed
        )
        header.addWidget(self.chat_mode)
        layout.addLayout(header)

        matrix_header = QHBoxLayout()
        matrix_title = QLabel("🧩 Matriz 2×2 · 4 sesiones aisladas")
        matrix_title.setObjectName("PageTitle")
        matrix_header.addWidget(matrix_title)
        matrix_header.addStretch(1)

        self._matrix_chain_button = QPushButton(
            "⛓ Ejecutar cadena 4 bots"
        )
        self._matrix_chain_button.clicked.connect(
            lambda: self._start_matrix_chain("cari")
        )
        matrix_header.addWidget(self._matrix_chain_button)

        self.lobby_manual_login_button = QPushButton(
            "🔑 Iniciar Sesión Manual"
        )
        self.lobby_manual_login_button.setToolTip(
            "Activa INITIAL_SETUP_MODE para que la próxima cadena "
            "abra Chromium visible y permita completar el inicio de sesión."
        )
        self.lobby_manual_login_button.clicked.connect(
            self._enable_manual_setup_mode
        )
        matrix_header.addWidget(self.lobby_manual_login_button)

        layout.addLayout(matrix_header)

        self._matrix_chain_summary = QLabel(
            "Matriz: Cari · Sunna · Cami · Chie · "
            "inicialización secuencial: Cari → Cami → Sunna → Chie."
        )
        self._matrix_chain_summary.setObjectName("Muted")
        self._matrix_chain_summary.setWordWrap(True)
        layout.addWidget(self._matrix_chain_summary)

        matrix = QWidget()
        matrix_grid = QGridLayout(matrix)
        matrix_grid.setContentsMargins(0, 0, 0, 0)
        matrix_grid.setSpacing(8)

        for spec in MATRIX_BOT_SPECS:
            panel = CardFrame()
            panel.setObjectName(f"MatrixBot_{spec.bot_id}")
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(8, 8, 8, 8)
            panel_layout.setSpacing(5)

            title_row = QHBoxLayout()
            title = QLabel(
                f"{BOT_MAP[spec.bot_id].avatar} {spec.display_name}"
            )
            title.setObjectName("PageTitle")
            title_row.addWidget(title)
            title_row.addStretch(1)

            status = QLabel("En espera")
            status.setObjectName("Muted")
            title_row.addWidget(status)
            panel_layout.addLayout(title_row)

            profile_label = QLabel(
                f"Sesión persistente · {spec.browser_profile}"
            )
            profile_label.setObjectName("Muted")
            profile_label.setWordWrap(True)
            panel_layout.addWidget(profile_label)

            provider_row = QHBoxLayout()
            provider_row.addWidget(QLabel("Proveedor web"))
            provider = QComboBox()
            provider.addItem("Google Gemini", "gemini")
            provider.addItem("OpenAI ChatGPT", "chatgpt")
            provider.addItem("Microsoft Copilot", "copilot")
            provider.addItem("Grok / Claude", "grok_claude")
            provider.setCurrentIndex(
                max(
                    0,
                    provider.findData(spec.default_provider),
                )
            )
            provider_row.addWidget(provider, 1)
            panel_layout.addLayout(provider_row)

            provider_url = QLineEdit()
            provider_url.setPlaceholderText(
                "URL personalizada para Grok / Claude"
            )
            provider_url.setText(
                os.getenv(
                    "BOT_IA_GROK_CLAUDE_URL",
                    "",
                ).strip()
            )
            provider_url.setVisible(spec.default_provider == "grok_claude")
            provider.currentIndexChanged.connect(
                lambda index, field=provider_url:
                field.setVisible(
                    provider.itemData(index) == "grok_claude"
                )
            )
            panel_layout.addWidget(provider_url)

            system_prompt = QPlainTextEdit(spec.default_system_prompt)
            system_prompt.setPlaceholderText(
                "System Prompt / Directiva de Actuación"
            )
            system_prompt.setMinimumHeight(48)
            system_prompt.setMaximumHeight(78)
            panel_layout.addWidget(system_prompt)

            log = QPlainTextEdit()
            log.setReadOnly(True)
            log.setPlaceholderText("Estado y log del bot…")
            log.setMinimumHeight(56)
            log.setMaximumHeight(110)
            panel_layout.addWidget(log, 1)

            start_button = QPushButton("▶ Iniciar desde este bot")
            start_button.clicked.connect(
                lambda _checked=False, bot_id=spec.bot_id:
                self._start_matrix_chain(bot_id)
            )
            panel_layout.addWidget(start_button)

            expand_button = QPushButton("🔍 Ampliar")
            expand_button.clicked.connect(
                lambda _checked=False, bot_id=spec.bot_id:
                self._open_bot_expanded(bot_id)
            )
            panel_layout.addWidget(expand_button)

            self._matrix_widgets[spec.bot_id] = {
                "panel": panel,
                "status": status,
                "system_prompt": system_prompt,
                "log": log,
                "provider": provider,
                "provider_url": provider_url,
                "start_button": start_button,
                "expand_button": expand_button,
            }
            matrix_grid.addWidget(
                panel,
                spec.row,
                spec.column,
            )

        layout.addWidget(matrix)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.chat_body = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_body)
        self.chat_layout.setContentsMargins(6, 6, 6, 6)
        self.chat_layout.setSpacing(9)
        self.chat_layout.addStretch(1)
        self.chat_scroll.setWidget(self.chat_body)
        layout.addWidget(self.chat_scroll, 1)

        composer = QFrame()
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(0, 2, 0, 0)
        composer_layout.setSpacing(8)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "Escribe aquí. Ctrl+Enter para enviar."
        )
        self.input.setMinimumHeight(76)
        self.input.setMaximumHeight(150)
        self.input.installEventFilter(self)
        composer_layout.addWidget(self.input)

        chips = QHBoxLayout()
        chips.setSpacing(7)
        for text, action_id in (
            ("🍫 Pedir Chocolatada", "chocolatada"),
            ("📦 Inventario / Cartas", "inventory"),
            ("💤 Estado de Descanso", "rest"),
            ("🎲 Mesa de Poker / Gacha", "duel"),
        ):
            pill = PillButton(text, action_id)
            pill.clicked.connect(
                lambda _checked=False, action=action_id: self._quick_action(
                    action
                )
            )
            if not hasattr(self, "quick_action_buttons"):
                self.quick_action_buttons = {}
            self.quick_action_buttons[action_id] = pill
            chips.addWidget(pill)
        chips.addStretch(1)

        self.lobby_gemini = QPushButton("✨ Preguntar a Gemini")
        self.lobby_gemini.setObjectName("lobby_gemini")
        self.lobby_gemini.clicked.connect(self._request_lobby_gemini)
        chips.addWidget(self.lobby_gemini)

        self.send_button = QPushButton("Enviar")
        self.send_button.setObjectName("AccentButton")
        self.send_button.setMinimumWidth(100)
        self.send_button.clicked.connect(self.send_message)
        chips.addWidget(self.send_button)
        composer_layout.addLayout(chips)

        security = QLabel(
            "API externa: sólo la habilita la lógica de autorización del request. "
            "La GUI no inventa canon ni muestra logs técnicos."
        )
        security.setObjectName("Muted")
        security.setWordWrap(True)
        composer_layout.addWidget(security)

        layout.addWidget(composer)

        return card

    def _build_web_card(self) -> QWidget:
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QHBoxLayout()
        label = QLabel("WebQueue · navegador")
        label.setObjectName("PageTitle")
        header.addWidget(label)
        header.addStretch(1)

        self.web_url = QLineEdit(
            os.getenv("BOT_IA_WEB_CHAT_URL", "").strip()
        )
        self.web_url.setPlaceholderText(
            "https://tu-chat-web.example/"
        )
        self.web_url.setMinimumWidth(220)
        header.addWidget(self.web_url)

        open_button = QPushButton("Abrir")
        open_button.clicked.connect(self._navigate_web)
        header.addWidget(open_button)

        layout.addLayout(header)

        self.web_hint = QLabel(
            "Configura BOT_IA_WEB_CHAT_URL o pega una URL compatible con "
            "WebChatQueueManager. El navegador queda visible para depuración "
            "funcional, mientras la pantalla principal mantiene el estilo limpio."
        )
        self.web_hint.setObjectName("Muted")
        self.web_hint.setWordWrap(True)
        layout.addWidget(self.web_hint)

        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        layout.addWidget(self.web_view, 1)

        return card

    # ------------------------------------------------------------------
    # Backend
    # ------------------------------------------------------------------

    def _wire_backend(self) -> None:
        try:
            from services.web_queue import WebChatQueueManager

            self._web_queue = WebChatQueueManager(
                self.web_view,
                parent=self,
            )
            self._web_queue.ticket_processed.connect(
                self._on_web_ticket_processed
            )
            self._web_queue.ticket_failed.connect(
                self._on_web_ticket_failed
            )
            self._web_queue.ticket_started.connect(
                self._on_web_ticket_started
            )
            self._web_queue.ticket_finished.connect(
                self._on_web_ticket_finished
            )
            self._web_queue.queue_error.connect(
                self._on_web_queue_error
            )
        except Exception as error:
            self._web_queue = None
            self._log_error("WebQueue initialization", error)
            self._on_web_state(
                "WebQueue no disponible. Revisa el estado del servicio."
            )

        self._tavern = self.runtime.build_tavern_manager(
            web_queue_manager=self._web_queue,
            message_sender=self._tavern_message_sender,
        )

    def _load_web_page(self) -> None:
        url_text = self.web_url.text().strip()
        if not url_text:
            self.web_view.setHtml(
                """
                <html><body style="background:#0f1117;color:#c8cbd4;
                font-family:Segoe UI,sans-serif;padding:32px">
                <h2>Café Otaku · WebQueue</h2>
                <p>Configura una URL de chat web compatible para usar la
                automatización de navegador.</p>
                </body></html>
                """
            )
            return
        self._navigate_web()

    def _navigate_web(self) -> None:
        raw = self.web_url.text().strip()
        url = QUrl(raw)
        if url.scheme() not in {"http", "https"} or not url.host():
            self._append_system(
                "La URL del navegador debe usar http:// o https:// y tener host."
            )
            return
        self.web_view.setUrl(url)
        if self._web_queue is not None:
            self._web_queue.initialize_protocol()

    def _tavern_message_sender(self, _chat_id: str, text: str) -> object:
        self.signals.notification.emit(
            _chat_id,
            text,
        )
        return None

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def _on_bot_tile_clicked(self, bot_id: str) -> None:
        self.select_bot(bot_id)
        self._open_bot_expanded(bot_id)

    def _open_bot_expanded(self, bot_id: str) -> None:
        profile = BOT_MAP.get(bot_id)
        if profile is None:
            return

        dialog = self._expanded_bot_dialogs.get(bot_id)
        if dialog is None:
            dialog = BotExpandedDialog(profile, self)
            dialog.send_requested.connect(
                self._send_expanded_bot_message
            )
            dialog.manual_requested.connect(
                self._start_manual_setup_for_bot
            )
            dialog.start_requested.connect(
                self._start_matrix_chain
            )
            dialog.provider_changed.connect(
                self._on_expanded_provider_changed
            )
            self._expanded_bot_dialogs[bot_id] = dialog

        widgets = self._matrix_widgets.get(bot_id, {})
        provider = widgets.get("provider")
        if isinstance(provider, QComboBox):
            provider_id = str(provider.currentData()).strip()
            dialog.set_provider(provider_id)
            authenticated, detail = self._browser_auth_state(
                bot_id,
                provider_id,
            )
            dialog.set_connection_state(authenticated, detail)

        status = widgets.get("status")
        if isinstance(status, QLabel):
            dialog.set_status(status.text())

        log = widgets.get("log")
        if isinstance(log, QPlainTextEdit):
            dialog.history.setPlainText(log.toPlainText())

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @staticmethod
    def _browser_auth_state(bot_id: str, provider_id: str) -> tuple[bool, str]:
        state_path = ROOT / "browser_data" / bot_id / "storage_state.json"
        if not state_path.is_file():
            return False, "Sin estado de autenticación guardado."
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, "Estado de autenticación inválido."
        cookies = payload.get("cookies", [])
        origins = payload.get("origins", [])
        if not isinstance(cookies, list):
            cookies = []
        if not isinstance(origins, list):
            origins = []
        if not cookies and not origins:
            return False, f"Sin sesión guardada para {provider_id}."
        return True, f"{provider_id}: sesión persistente disponible."

    def _on_expanded_provider_changed(self, bot_id: str, provider_id: str) -> None:
        widgets = self._matrix_widgets.get(bot_id, {})
        provider = widgets.get("provider")
        if isinstance(provider, QComboBox):
            index = provider.findData(provider_id)
            if index >= 0:
                provider.blockSignals(True)
                provider.setCurrentIndex(index)
                provider.blockSignals(False)
        provider_url = widgets.get("provider_url")
        if isinstance(provider_url, QLineEdit):
            provider_url.setVisible(provider_id == "grok_claude")
        self._sync_expanded_bot(bot_id)

    def _sync_expanded_bot(self, bot_id: str) -> None:
        dialog = self._expanded_bot_dialogs.get(bot_id)
        widgets = self._matrix_widgets.get(bot_id, {})
        if dialog is None:
            return
        status = widgets.get("status")
        log = widgets.get("log")
        provider = widgets.get("provider")
        if isinstance(status, QLabel):
            dialog.set_status(status.text())
        if isinstance(provider, QComboBox):
            provider_id = str(provider.currentData()).strip()
            dialog.set_provider(provider_id)
            authenticated, detail = self._browser_auth_state(
                bot_id,
                provider_id,
            )
            dialog.set_connection_state(authenticated, detail)
        if isinstance(log, QPlainTextEdit):
            dialog.history.setPlainText(log.toPlainText())

    def _open_mini_games(self) -> None:
        if self._mini_games_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("🎮 Mini-Juegos · Taberna local")
            dialog.setMinimumSize(520, 360)
            layout = QVBoxLayout(dialog)
            title = QLabel("🎮 Mini-Juegos locales")
            title.setObjectName("PageTitle")
            layout.addWidget(title)
            info = QLabel(
                "PPT: escribe «piedra», «papel» o «tijera». "
                "21: «21 nuevo», «carta» y «plantarse». "
                "UNO queda registrado como catálogo de cartas."
            )
            info.setWordWrap(True)
            info.setObjectName("Muted")
            layout.addWidget(info)
            for label, command in (
                ("🪨 Piedra", "piedra"),
                ("📄 Papel", "papel"),
                ("✂️ Tijera", "tijera"),
                ("🃏 21 nuevo", "21 nuevo"),
                ("🎴 UNO", "UNO"),
            ):
                button = QPushButton(label)
                button.clicked.connect(
                    lambda _checked=False, value=command: self._start_local_game_command(value)
                )
                layout.addWidget(button)
            close = QPushButton("Cerrar")
            close.clicked.connect(dialog.hide)
            layout.addWidget(close)
            self._mini_games_dialog = dialog
        self.select_bot(self._selected_bot_id)
        self._mini_games_dialog.show()
        self._mini_games_dialog.raise_()
        self._mini_games_dialog.activateWindow()

    def _start_local_game_command(self, command: str) -> None:
        self.chat_mode.setCurrentIndex(1)
        self.input.setPlainText(command)
        self.input.setFocus()
        self._append_system(
            "Mini-juego local seleccionado. La resolución usa LocalGameRouter; WebQueue omitido."
        )

    def _open_waifu_registry(self, bot_id: str | None = None) -> None:
        selected = bot_id or self._selected_bot_id
        if selected in BOT_MAP:
            self.select_bot(selected)
        if self._waifu_dialog is None:
            self._waifu_dialog = WaifuRegistryDialog(
                self.waifu_registry,
                bot_id=selected,
                parent=self,
            )
        self._waifu_dialog.bot_id = selected
        self._waifu_dialog.show()
        self._waifu_dialog.raise_()
        self._waifu_dialog.activateWindow()

    def _try_local_bot_response(self, message: str) -> bool:
        bot_id = self._selected_bot_id
        if bot_id not in {"cari", "cami"}:
            return False
        normalized = " ".join(message.casefold().strip().split())
        if not normalized or len(normalized) > 180:
            return False

        profile = BOT_MAP[bot_id]
        response = ""
        if normalized in {
            "hola",
            "holi",
            "hello",
            "buenas",
            "buenos dias",
            "buenas tardes",
        }:
            response = (
                "¡Hola! Soy Cari. Estoy disponible localmente para consultas "
                "simples del Café Otaku."
                if bot_id == "cari"
                else
                "Hola. Soy Cami. Puedo resolver consultas simples localmente "
                "sin abrir una sesión web."
            )
        elif any(
            token in normalized
            for token in ("estado", "estas ahi", "estás ahí", "disponible")
        ):
            response = (
                f"{profile.name}: estado local OK. "
                "No fue necesario invocar WebQueue."
            )
        elif any(
            token in normalized
            for token in ("ayuda", "que puedes hacer", "qué puedes hacer")
        ):
            response = (
                f"{profile.name}: puedo atender saludos, estado, ayuda y "
                "acciones locales sencillas sin consumir una sesión web."
            )
        elif any(
            token in normalized
            for token in ("waifu", "carta tcg", "prompt tcg")
        ):
            response = (
                f"{profile.name}: el Registro de Waifus está disponible en "
                "«🎴 Registro de Waifus»."
            )
        else:
            return False

        self._append_message(profile.name, response, "bot")
        dialog = self._expanded_bot_dialogs.get(bot_id)
        if dialog is not None:
            dialog.append_history(profile.name, response)
            dialog.append_history("Sistema", "Respuesta local; WebQueue omitido.")
        self._append_system(
            f"{profile.name}: respuesta local; WebQueue omitido."
        )
        self.send_button.setEnabled(True)
        return True

    def _try_local_game_response(self, message: str) -> bool:
        bot_id = self._selected_bot_id
        response = self._mini_game_router.route(
            message,
            DESKTOP_USER,
            bot_id,
        )
        if response is None:
            return False
        profile = BOT_MAP[bot_id]
        self._append_message(profile.name, response, "bot")
        dialog = self._expanded_bot_dialogs.get(bot_id)
        if dialog is not None:
            dialog.append_history(profile.name, response)
            dialog.append_history("Sistema", "Mini-juego local; WebQueue omitido.")
        self._append_system(
            f"{profile.name}: mini-juego local; WebQueue omitido."
        )
        self.send_button.setEnabled(True)
        return True

    def _send_expanded_bot_message(
        self,
        bot_id: str,
        message: str,
    ) -> None:
        if bot_id not in BOT_MAP:
            return
        self.select_bot(bot_id)
        if self._try_local_game_response(message):
            return
        if self._try_local_bot_response(message):
            return
        self._send_web_persona(message)
        dialog = self._expanded_bot_dialogs.get(bot_id)
        if dialog is not None:
            dialog.append_history("Sistema", "Mensaje enviado a WebQueue.")

    def _start_manual_setup_for_bot(self, bot_id: str) -> None:
        if bot_id not in BOT_MAP:
            return
        self.select_bot(bot_id)
        dialog = self._expanded_bot_dialogs.get(bot_id)
        provider_id = (
            str(dialog.provider.currentData()).strip()
            if dialog is not None
            else "gemini"
        )
        self._enable_manual_setup_mode(bot_id, provider_id=provider_id)

    def select_bot(self, bot_id: str) -> None:
        if bot_id not in BOT_MAP:
            return
        self._selected_bot_id = bot_id
        for current_id, tile in self.bot_tiles.items():
            tile.set_selected(current_id == bot_id)
        profile = BOT_MAP[bot_id]
        self.selected_label.setText(
            f"{profile.avatar} {profile.name}"
        )
        self.selected_role.setText(profile.short_role)
        self._update_selected_status()
        self.chat_title.setText(
            f"{profile.avatar} {profile.name}"
        )
        if self.chat_mode.currentIndex() == 0:
            self.chat_mode.setCurrentIndex(
                1 if self._is_registered_tavern_bot(bot_id) else 2
            )

    def _is_registered_tavern_bot(self, bot_id: str) -> bool:
        if self._tavern is None:
            return False
        try:
            return any(
                item.waitress_id == bot_id
                for item in self._tavern.list_turns()
            )
        except Exception as error:
            self._log_error("Tavern roster check", error)
            return False

    def _on_chat_mode_changed(self, index: int) -> None:
        titles = (
            "Lobby general",
            "Taberna · conversación con la mesera",
            f"Web · {BOT_MAP[self._selected_bot_id].name}",
        )
        self.chat_title.setText(titles[index])

    def eventFilter(self, watched: QObject, event: object) -> bool:
        if (
            watched is self.input
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.KeyPress
            and event.key() in {Qt.Key_Return, Qt.Key_Enter}
            and event.modifiers() & Qt.ControlModifier
        ):
            self.send_message()
            return True
        return super().eventFilter(watched, event)

    def send_message(self) -> None:
        message = self.input.toPlainText().strip()
        if not message or self._closing:
            return
        self.input.clear()
        self._append_message("Tú", message, "user")
        self.send_button.setEnabled(False)

        mode = self.chat_mode.currentIndex()
        if mode == 0:
            request = ApplicationRequest(
                DESKTOP_USER,
                DESKTOP_SESSION,
                message,
                allow_external_api=False,
            )
            self._pending_tasks += 1
            self.task_pool.start(
                ApplicationTask(
                    self.signals,
                    self.application,
                    request,
                )
            )
            return

        if mode == 1:
            self._send_tavern(message)
            return

        self._send_web_persona(message)

    def _send_tavern(self, message: str) -> None:
        if self._try_local_game_response(message):
            self.refresh_state()
            return

        if self._tavern is None:
            self._append_system(
                "La Taberna no pudo inicializarse. El runtime sigue protegido."
            )
            self.send_button.setEnabled(True)
            return
        try:
            session = self._tavern.get_active_session(DESKTOP_USER)
            if session is None:
                session = self._tavern.start_standard_session(
                    DESKTOP_USER,
                    self._selected_bot_id,
                )
                self._append_system(
                    f"Sesión de 3 minutos iniciada con "
                    f"{BOT_MAP[self._selected_bot_id].name}."
                )
            ticket_id = self._tavern.queue_user_message(
                DESKTOP_USER,
                message,
            )
            self._tavern_ticket_ids.add(ticket_id)
        except (
            WaitressUnavailableError,
            SessionConflictError,
            SessionExpiredError,
            InsufficientBalanceError,
            TavernConfigurationError,
            TavernError,
            ValueError,
        ) as error:
            self._append_system(
                self._friendly_tavern_error(error)
            )
        finally:
            self.send_button.setEnabled(True)
            self.refresh_state()

    def _send_web_persona(self, message: str) -> None:
        if self._try_local_bot_response(message):
            return
        if self._web_queue is None:
            self._append_system(
                "WebQueue no está disponible en esta sesión."
            )
            self.send_button.setEnabled(True)
            return
        self._web_ticket_sequence += 1
        ticket_id = f"gui-{self._web_ticket_sequence}-{datetime.now().strftime('%H%M%S%f')}"
        self._web_ticket_ids[ticket_id] = self._selected_bot_id
        try:
            self._web_queue.enqueue_bot_message(
                BOT_MAP[self._selected_bot_id].name,
                ticket_id,
                "chat",
                message,
                user=DESKTOP_USER,
                channel="/cafe",
            )
            self.send_button.setEnabled(False)
        except (ValueError, RuntimeError) as error:
            self._web_ticket_ids.pop(ticket_id, None)
            self._append_system(
                f"No pude encolar el mensaje web: {type(error).__name__}."
            )
            self.send_button.setEnabled(True)

    def set_async_engine(
        self,
        orchestrator: TaskOrchestrator,
        web_queue: WebQueueManager,
    ) -> None:
        self._async_orchestrator = orchestrator
        self._async_web_queue = web_queue

    async def shutdown_async_engine(self) -> None:
        orchestrator = self._async_orchestrator
        web_queue = self._async_web_queue
        self._async_orchestrator = None
        self._async_web_queue = None

        if orchestrator is not None:
            try:
                await orchestrator.stop_worker()
            except Exception as error:
                self._log_error("Async orchestrator shutdown", error)

        if web_queue is not None:
            try:
                await web_queue.close_browser_pool()
            except Exception as error:
                self._log_error("Playwright shutdown", error)

    def _schedule_async_quick_action(self, action_id: str) -> None:
        orchestrator = self._async_orchestrator
        if orchestrator is None:
            return

        async def callback(response_text: str) -> None:
            profile = BOT_MAP[self._selected_bot_id]
            self.bridge_signals.message_received.emit(
                profile.bot_id,
                response_text,
            )

        priority = (
            Priority.HIGH
            if action_id == "chocolatada"
            else Priority.MEDIUM
        )
        payload = {
            "is_local_action": action_id == "chocolatada",
            "template_response": (
                "¡Marchando una chocolatada caliente con extra espuma! "
                "🍫✨"
            ),
            "prompt": "Genera una pregunta rápida de trivia sobre anime.",
        }

        try:
            asyncio.create_task(
                orchestrator.enqueue_task(
                    waitress_id=(
                        "cari"
                        if action_id == "chocolatada"
                        else "sunna"
                    ),
                    priority=priority,
                    payload=payload,
                    callback=callback,
                )
            )
        except RuntimeError as error:
            self._log_error("Async quick action", error)
            self._append_system(
                "El motor asíncrono no está disponible en esta sesión."
            )

    @Slot(str, str)
    def _on_async_status_changed(
        self,
        waitress_id: str,
        status: str,
    ) -> None:
        tile = self.bot_tiles.get(waitress_id)
        if tile is None:
            return

        normalized = status.casefold()
        if "online" in normalized:
            state = "online"
        elif "procesando" in normalized:
            state = "warn"
        elif "fallback" in normalized or "reintentando" in normalized:
            state = "warn"
        else:
            state = "warn"

        tile.set_status(status, state)
        self._update_selected_status()
        self._update_footer()

    @Slot(str, str)
    def _on_async_message_received(
        self,
        waitress_id: str,
        response_text: str,
    ) -> None:
        profile = BOT_MAP.get(waitress_id)
        speaker = profile.name if profile is not None else waitress_id
        self._append_message(
            speaker,
            response_text,
            "bot",
        )
        self.refresh_state()

    def _quick_action(self, action_id: str) -> None:
        if (
            action_id in {"chocolatada", "trivia"}
            and self._async_orchestrator is not None
        ):
            self._schedule_async_quick_action(action_id)
            return

        if action_id == "chocolatada":
            self.input.setPlainText(
                "Quiero pedir una chocolatada en el Café Otaku."
            )
            self.send_message()
            return

        if self._tavern is None:
            self._append_system("La Taberna no está disponible.")
            return

        if action_id == "inventory":
            try:
                snapshot = self._tavern.inventory(DESKTOP_USER)
                cards = ", ".join(
                    f"{name} [{rarity}] x{quantity}"
                    for name, rarity, quantity in snapshot.cards
                ) or "sin cartas"
                drinks = ", ".join(
                    f"{name} x{quantity}"
                    for name, quantity in snapshot.drinks
                ) or "sin bebidas"
                self._append_system(
                    f"🍫 Chocolates: {snapshot.chocolates_balance} · "
                    f"🎟️ Usos gratis: {snapshot.daily_free_uses}\n"
                    f"🃏 {cards}\n🍹 {drinks}"
                )
            except TavernError as error:
                self._append_system(self._friendly_tavern_error(error))
            return

        if action_id == "rest":
            self._append_system(self._format_rest_state())
            self.refresh_state()
            return

        if action_id == "duel":
            try:
                reply = self._tavern.charge_duel(
                    DESKTOP_USER,
                    opponent="mama_mia",
                )
                self._append_system(
                    "🎲 El backend actual soporta duelo con coste de "
                    "10 chocolates; no se ha inventado un sistema gacha."
                    f"\n\n{reply.text}"
                )
            except TavernError as error:
                self._append_system(self._friendly_tavern_error(error))

    def _start_matrix_chain(self, start_bot_id: str = "cari") -> None:
        if self._closing or self._matrix_dispatcher.is_running:
            return

        command = self.input.toPlainText().strip()
        if not command:
            self._append_system(
                "Escribe un comando en el Lobby antes de iniciar la matriz."
            )
            return

        system_prompts = {
            bot_id: str(
                widgets["system_prompt"].toPlainText()
            ).strip()
            for bot_id, widgets in self._matrix_widgets.items()
        }
        providers = {
            bot_id: str(
                widgets["provider"].currentData()
            ).strip().lower()
            for bot_id, widgets in self._matrix_widgets.items()
        }
        provider_urls = {
            bot_id: str(
                widgets["provider_url"].text()
            ).strip()
            for bot_id, widgets in self._matrix_widgets.items()
        }

        for bot_id, widgets in self._matrix_widgets.items():
            widgets["status"].setText(
                "En cola"
                if self._matrix_index(bot_id) >= self._matrix_index(start_bot_id)
                else "No incluido"
            )
            widgets["log"].clear()

        self._matrix_chain_running = True
        self._set_matrix_controls(False)
        self._matrix_dispatcher.start(
            command,
            system_prompts,
            providers,
            provider_urls,
            start_bot_id=start_bot_id,
        )

    def _matrix_index(self, bot_id: str) -> int:
        for index, spec in enumerate(MATRIX_BOT_SPECS):
            if spec.bot_id == bot_id:
                return index
        return len(MATRIX_BOT_SPECS)

    def _set_matrix_controls(self, enabled: bool) -> None:
        if self._matrix_chain_button is not None:
            self._matrix_chain_button.setEnabled(enabled)
        self.lobby_gemini.setEnabled(enabled)
        for widgets in self._matrix_widgets.values():
            button = widgets.get("start_button")
            if isinstance(button, QPushButton):
                button.setEnabled(enabled)

    @Slot(str)
    def _on_matrix_bot_started(self, bot_id: str) -> None:
        widgets = self._matrix_widgets.get(bot_id)
        if widgets is None:
            return
        widgets["status"].setText("⏳ Inicializando personalidad…")
        log = widgets["log"]
        log.appendPlainText(
            f"Proveedor seleccionado: {widgets['provider'].currentText()}"
        )
        log.appendPlainText(
            "Perfil aislado abierto; solicitando un chat nuevo…"
        )
        self._sync_expanded_bot(bot_id)


    @Slot(str, str)
    def _on_matrix_bot_finished(
        self,
        bot_id: str,
        response: str,
    ) -> None:
        widgets = self._matrix_widgets.get(bot_id)
        if widgets is None:
            return
        widgets["status"].setText("🟡 Contexto recibido")
        widgets["log"].appendPlainText(
            response.strip() or "Respuesta vacía."
        )
        profile = BOT_MAP.get(bot_id)
        speaker = profile.name if profile is not None else bot_id
        self._append_message(
            speaker,
            response,
            "bot",
        )
        self._sync_expanded_bot(bot_id)

    @Slot(str)
    def _on_matrix_bot_ready(self, bot_id: str) -> None:
        widgets = self._matrix_widgets.get(bot_id)
        if widgets is None:
            return
        widgets["status"].setText("✅ Listo / Chat creado")
        widgets["log"].appendPlainText(
            "CONTEXTO_LISTO confirmado. Se habilita el siguiente turno."
        )
        self._sync_expanded_bot(bot_id)

    @Slot(str, str)
    def _on_matrix_bot_failed(
        self,
        bot_id: str,
        error: str,
    ) -> None:
        widgets = self._matrix_widgets.get(bot_id)
        if widgets is None:
            return
        widgets["status"].setText("❌ Error")
        widgets["log"].appendPlainText(error)
        self._sync_expanded_bot(bot_id)

    @Slot(dict)
    def _on_matrix_chain_finished(
        self,
        report: dict,
    ) -> None:
        self._matrix_chain_running = False
        self._set_matrix_controls(True)
        ok = bool(report.get("ok", False))
        if self._matrix_chain_summary is not None:
            self._matrix_chain_summary.setText(
                "✅ Cadena 4 bots completada."
                if ok
                else "⚠ Cadena completada con uno o más errores."
            )

    @Slot(str)
    def _on_matrix_chain_failed(self, error: str) -> None:
        self._matrix_chain_running = False
        self._set_matrix_controls(True)
        if self._matrix_chain_summary is not None:
            self._matrix_chain_summary.setText(
                f"❌ No se pudo iniciar la cadena: {error}"
            )

    def _enable_manual_setup_mode(
        self,
        bot_id: str | None = None,
        *,
        provider_id: str = "",
        provider_url: str = "",
    ) -> None:
        """Lanza el Chromium nativo de configuración para el perfil seleccionado."""
        if self._manual_setup_thread is not None:
            self._append_system(
                "🔑 Ya hay una sesión de inicio manual en curso."
            )
            return

        requested_bot_id = bot_id or self._selected_bot_id
        target_id = (
            requested_bot_id
            if requested_bot_id in {
                spec.bot_id for spec in MATRIX_BOT_SPECS
            }
            else MATRIX_INITIALIZATION_ORDER[0]
        )
        spec = next(
            (
                item for item in MATRIX_BOT_SPECS
                if item.bot_id == target_id
            ),
            None,
        )
        widgets = self._matrix_widgets.get(target_id, {})
        provider = widgets.get("provider")
        provider_url_field = widgets.get("provider_url")
        selected_provider_id = (
            str(provider.currentData()).strip().lower()
            if isinstance(provider, QComboBox)
            else ""
        )
        provider_id = (
            provider_id.strip().lower()
            or selected_provider_id
            or (
                spec.default_provider
                if spec is not None
                else "gemini"
            )
        )
        selected_provider_url = (
            str(provider_url_field.text()).strip()
            if isinstance(provider_url_field, QLineEdit)
            else ""
        )
        provider_url = provider_url.strip() or selected_provider_url
        browser_profile = (
            spec.browser_profile
            if spec is not None
            else f"./browser_data/{target_id}"
        )
        display_name = (
            spec.display_name
            if spec is not None
            else BOT_MAP[target_id].name
        )

        try:
            self.config_manager.set_values(
                {INITIAL_SETUP_MODE_ENV: "true"}
            )
            os.environ[INITIAL_SETUP_MODE_ENV] = "true"

            worker = ManualBrowserSetupWorker(
                target_id,
                browser_profile,
                provider_id,
                provider_url,
            )
            thread = QThread(self)
            worker.moveToThread(thread)
            self._manual_setup_thread = thread
            self._manual_setup_worker = worker

            thread.started.connect(worker.run)
            worker.status.connect(self._on_manual_setup_status)
            worker.finished.connect(self._on_manual_setup_finished)
            worker.failed.connect(self._on_manual_setup_failed)
            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(self._clear_manual_setup_worker)

            self._set_matrix_controls(False)
            for button in (
                getattr(self, "manual_login_button", None),
                getattr(self, "lobby_manual_login_button", None),
            ):
                if isinstance(button, QPushButton):
                    button.setText("🔑 Chromium Manual: ACTIVO")
                    button.setEnabled(False)

            expanded = self._expanded_bot_dialogs.get(target_id)
            if expanded is not None:
                expanded.set_status("🔑 Chromium manual abierto")

            self._append_system(
                f"🔑 Abriendo Chromium nativo para {display_name}. "
                "La autenticación se realiza directamente en esa ventana; "
                "no se usa el visor WebQueue."
            )
            thread.start()
        except Exception as error:
            self._log_error("Manual browser setup", error)
            self._finish_manual_setup_mode()
            self._append_system(
                "No se pudo iniciar el Chromium externo de configuración."
            )

    @Slot(str)
    def _on_manual_setup_status(self, text: str) -> None:
        self._append_system(f"🔑 {text}")
        for dialog in self._expanded_bot_dialogs.values():
            if dialog.isVisible():
                dialog.set_status("Configuración manual finalizada")

    @Slot(str)
    def _on_manual_setup_finished(self, text: str) -> None:
        self._finish_manual_setup_mode()
        self._append_system(f"🔑 {text}")
        for bot_id, dialog in self._expanded_bot_dialogs.items():
            provider_id = str(dialog.provider.currentData()).strip()
            authenticated, detail = self._browser_auth_state(
                bot_id,
                provider_id,
            )
            dialog.set_connection_state(authenticated, detail)

    @Slot(str)
    def _on_manual_setup_failed(self, error: str) -> None:
        self._finish_manual_setup_mode()
        self._log_line(f"Manual browser setup: {error}")
        self._append_system(
            f"❌ Inicio de sesión manual: {error}"
        )

    def _finish_manual_setup_mode(self) -> None:
        os.environ[INITIAL_SETUP_MODE_ENV] = "false"
        try:
            self.config_manager.set_values(
                {INITIAL_SETUP_MODE_ENV: "false"}
            )
        except Exception as error:
            self._log_error(
                "Manual browser setup mode reset",
                error,
            )

        self._set_matrix_controls(True)
        for button in (
            getattr(self, "manual_login_button", None),
            getattr(self, "lobby_manual_login_button", None),
        ):
            if isinstance(button, QPushButton):
                button.setText("🔑 Iniciar Sesión Manual")
                button.setEnabled(True)
                button.setToolTip(
                    "Abre Chromium nativo fuera de la GUI para "
                    "configurar el perfil seleccionado."
                )

        if self._matrix_chain_summary is not None:
            self._matrix_chain_summary.setText(
                "Modo manual finalizado. INITIAL_SETUP_MODE=false; "
                "el uso diario vuelve al Chromium headless."
            )

    def _clear_manual_setup_worker(self) -> None:
        self._manual_setup_thread = None
        self._manual_setup_worker = None

    def _request_lobby_gemini(self) -> None:
        self._start_matrix_chain("cari")

    @Slot(str)
    def _gemini_done(self, response: str) -> None:
        """Compatibilidad con el antiguo punto de entrada del Lobby."""
        self._append_message("Gemini", response, "bot")
        self.lobby_gemini.setEnabled(True)

    @Slot(str)
    def _gemini_failed(self, error: str) -> None:
        """Compatibilidad con el antiguo punto de entrada del Lobby."""
        self._append_system(
            f"❌ Gemini Lobby no pudo completar la consulta: {error}"
        )
        self.lobby_gemini.setEnabled(True)

    def _save_dynamic_configuration(
        self,
        values: dict[str, str],
    ) -> bool:
        try:
            self.config_manager.set_values(values)
        except Exception as error:
            self._log_error("Configuration save", error)
            self._append_system(
                "No se pudo guardar la configuración en .env."
            )
            return False

        for key, value in values.items():
            if key.startswith("BOT_TOKEN_"):
                self._bot_credentials[key] = value

        previous_application = self.application
        previous_provider = self.provider_id
        previous_universe = self.default_universe

        self.provider_id = os.getenv(
            "BOT_IA_PROVIDER",
            "openai",
        ).strip() or "openai"
        self.default_universe = os.getenv(
            "BOT_IA_UNIVERSE",
            "one_neko_punch",
        ).strip() or "one_neko_punch"

        try:
            self.application = self.runtime.build_application(
                default_universe_id=self.default_universe,
                provider_id=self.provider_id,
            )
        except Exception as error:
            self.application = previous_application
            self.provider_id = previous_provider
            self.default_universe = previous_universe
            self._log_error("Runtime hot reload", error)
            self._append_system(
                "La configuración quedó guardada, pero el runtime "
                "no pudo reconstruir la aplicación con esos valores."
            )
            self._refresh_config_dialog_fields()
            return False

        self._refresh_config_dialog_fields()
        self.refresh_state()
        self._append_system(
            "✅ Configuración guardada en .env y aplicada en caliente."
        )
        return True

    def save_and_verify_credentials(
        self,
        fields: dict[str, QLineEdit],
        provider_fields: dict[str, QLineEdit] | None = None,
    ) -> bool:
        """Persiste BOTS y, opcionalmente, providers desde el panel de configuración."""
        values: dict[str, str] = {}

        for bot_id, field in fields.items():
            values[f"BOT_TOKEN_{bot_id.upper()}"] = (
                field.text().strip()
            )

        if provider_fields is not None:
            values.update(
                {
                    key: field.text().strip()
                    for key, field in provider_fields.items()
                }
            )

        return self._save_dynamic_configuration(values)

    def _show_bots_credentials_dialog(self) -> None:
        self._show_dynamic_config_dialog()

    def _show_dynamic_config_dialog(self) -> None:
        dialog = QWidget()
        dialog.setWindowTitle(
            "Casa de Comando · PROVEEDORES LLM / APIs + BOTS"
        )
        dialog.setMinimumSize(900, 720)
        dialog.setAttribute(Qt.WA_DeleteOnClose)

        outer = QVBoxLayout(dialog)
        outer.addWidget(
            SectionHeader(
                "PROVEEDORES LLM / APIs",
                "Los cambios se guardan en .env y se aplican inmediatamente al runtime."
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        provider_fields: dict[str, QLineEdit] = {}
        provider_keys = (
            "BOT_IA_PROVIDER",
            "INITIAL_SETUP_MODE",
            "OPENAI_API_KEY",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "COZE_API_TOKEN",
            "COZE_BOT_ID",
            "GEMINI_API_KEY",
            "BOT_IA_GEMINI_URL",
            "BOT_IA_CHATGPT_URL",
            "BOT_IA_GROK_CLAUDE_URL",
            "OLLAMA_BASE_URL",
            "TELEGRAM_BOT_TOKEN",
        )
        provider_grid = QGridLayout()
        for row, key in enumerate(provider_keys):
            provider_grid.addWidget(
                QLabel(key),
                row,
                0,
            )
            field = QLineEdit(
                self.config_manager.get(
                    key,
                    os.getenv(key, ""),
                )
            )
            if "API_KEY" in key or "TOKEN" in key:
                field.setEchoMode(QLineEdit.Password)
            field.setPlaceholderText(key)
            provider_grid.addWidget(field, row, 1)
            provider_fields[key] = field

        content_layout.addLayout(provider_grid)
        content_layout.addSpacing(14)
        content_layout.addWidget(
            SectionHeader(
                "BOTS",
                "Tokens persistentes de Cari, Cami, Sunna, Chie, Chloe y Scarlet."
            )
        )

        bot_fields: dict[str, QLineEdit] = {}
        bot_grid = QGridLayout()
        for row, profile in enumerate(BOT_PROFILES):
            key = f"BOT_TOKEN_{profile.bot_id.upper()}"
            bot_grid.addWidget(
                QLabel(f"{profile.avatar} {profile.name}"),
                row,
                0,
            )
            field = QLineEdit(
                self.config_manager.get(
                    key,
                    os.getenv(key, ""),
                )
            )
            field.setEchoMode(QLineEdit.Password)
            field.setPlaceholderText(key)
            bot_grid.addWidget(field, row, 1)
            bot_fields[profile.bot_id] = field

        content_layout.addLayout(bot_grid)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._config_dialog_fields = {
            "providers": provider_fields,
            "bots": bot_fields,
        }

        buttons = QHBoxLayout()
        save = QPushButton("💾 Guardar")
        save.clicked.connect(
            lambda: self.save_and_verify_credentials(
                bot_fields,
                provider_fields,
            )
        )
        buttons.addWidget(save)

        reset = QPushButton("🔄 Restablecer Configuración de Fábrica")
        reset.clicked.connect(
            lambda: self._reset_configuration_factory(dialog)
        )
        buttons.addWidget(reset)

        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.close)
        buttons.addWidget(close)
        outer.addLayout(buttons)

        self._dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda _obj=None: self._discard_dialog(dialog)
        )
        dialog.show()

    def _refresh_config_dialog_fields(self) -> None:
        for section in self._config_dialog_fields.values():
            for key, field in section.items():
                value = self.config_manager.get(
                    key,
                    os.getenv(key, ""),
                )
                field.blockSignals(True)
                field.setText(value)
                field.blockSignals(False)

    def _reset_configuration_factory(self, dialog: QWidget) -> None:
        answer = QMessageBox.question(
            dialog,
            "Confirmar restablecimiento",
            "Se reemplazará .env por .env.example y se restaurarán "
            "los valores de fábrica. ¿Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.config_manager.reset_to_factory()
            self.provider_id = os.getenv(
                "BOT_IA_PROVIDER",
                "openai",
            ).strip() or "openai"
            self.default_universe = os.getenv(
                "BOT_IA_UNIVERSE",
                "one_neko_punch",
            ).strip() or "one_neko_punch"
            self.application = self.runtime.build_application(
                default_universe_id=self.default_universe,
                provider_id=self.provider_id,
            )
            self._bot_credentials = {
                f"BOT_TOKEN_{profile.bot_id.upper()}": os.getenv(
                    f"BOT_TOKEN_{profile.bot_id.upper()}",
                    "",
                ).strip()
                for profile in BOT_PROFILES
            }
            self._refresh_config_dialog_fields()
            self.manual_login_button.setEnabled(
                _initial_setup_mode() is False
            )
            self.refresh_state()
            self._append_system(
                "🔄 Configuración de fábrica restaurada desde .env.example."
            )
        except Exception as error:
            self._log_error("Factory reset", error)
            self._append_system(
                "No se pudo restablecer la configuración de fábrica."
            )

    def _show_diagnostic_dialog(self) -> None:
        dialog = QWidget()
        dialog.setWindowTitle(
            "🔍 DIAGNÓSTICO Y ANÁLISIS · Sentry"
        )
        dialog.setMinimumSize(1000, 720)

        layout = QVBoxLayout(dialog)
        layout.addWidget(
            SectionHeader(
                "Inspector interno Sentry",
                "Comprueba Gemini Web, Telegram, providers activos y la integridad de SQLite sin mostrar secretos."
            )
        )

        report_view = QPlainTextEdit()
        report_view.setReadOnly(True)
        report_view.setPlainText(
            "Pulsa «Ejecutar diagnóstico» para iniciar la inspección."
        )
        layout.addWidget(report_view, 1)

        run_button = QPushButton("🔍 Ejecutar diagnóstico")
        run_button.clicked.connect(
            lambda: self._start_system_diagnostic(
                report_view,
                run_button,
            )
        )
        layout.addWidget(run_button, 0, Qt.AlignRight)

        self._dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda _obj=None: self._discard_dialog(dialog)
        )
        dialog.show()

    def _start_system_diagnostic(
        self,
        report_view: QPlainTextEdit,
        run_button: QPushButton,
    ) -> None:
        if (
            self._diagnostic_thread is not None
            and self._diagnostic_thread.isRunning()
        ):
            return

        run_button.setEnabled(False)
        run_button.setText("⏳ Analizando…")
        self.config_manager.load()

        worker = SystemDiagnosticWorker(
            ROOT,
            self.runtime.memory_store.path,
            self.runtime.config,
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        worker.finished.connect(
            lambda report: self._diagnostic_done(
                report,
                report_view,
                run_button,
            )
        )
        worker.failed.connect(
            lambda error: self._diagnostic_failed(
                error,
                report_view,
                run_button,
            )
        )
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._cleanup_diagnostic_thread(
                thread,
                worker,
            )
        )

        self._diagnostic_thread = thread
        self._diagnostic_worker = worker
        thread.start()

    @Slot(dict)
    def _diagnostic_done(
        self,
        report: dict,
        report_view: QPlainTextEdit,
        run_button: QPushButton,
    ) -> None:
        report_view.setPlainText(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
        )
        run_button.setEnabled(True)
        run_button.setText("🔍 Ejecutar diagnóstico")

    @Slot(str)
    def _diagnostic_failed(
        self,
        error: str,
        report_view: QPlainTextEdit,
        run_button: QPushButton,
    ) -> None:
        report_view.setPlainText(
            json.dumps(
                {
                    "ok": False,
                    "errors": [error],
                    "suggestions": [
                        "Repite el diagnóstico y revisa work/gui.log."
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        run_button.setEnabled(True)
        run_button.setText("🔍 Ejecutar diagnóstico")

    def _cleanup_diagnostic_thread(
        self,
        thread: QThread,
        worker: SystemDiagnosticWorker,
    ) -> None:
        if self._diagnostic_thread is thread:
            self._diagnostic_thread = None
        if self._diagnostic_worker is worker:
            self._diagnostic_worker = None

    def _append_message(self, speaker: str, text: str, role: str) -> None:
        bubble = QLabel(f"<b>{speaker}</b><br>{self._escape(text)}")
        bubble.setWordWrap(True)
        bubble.setTextFormat(Qt.RichText)
        bubble.setObjectName(
            "BubbleUser" if role == "user" else "BubbleBot"
        )
        bubble.setMaximumWidth(680)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            row.addStretch(1)
        row.addWidget(bubble)
        if role != "user":
            row.addStretch(1)

        wrapper = QWidget()
        wrapper.setLayout(row)
        self.chat_layout.insertWidget(
            self.chat_layout.count() - 1,
            wrapper,
        )
        QTimer.singleShot(
            0,
            lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            ),
        )

    def _append_system(self, text: str) -> None:
        label = QLabel(self._escape(text))
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        label.setObjectName("BubbleSystem")
        label.setMaximumWidth(720)
        self.chat_layout.insertWidget(
            self.chat_layout.count() - 1,
            label,
        )

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

    @staticmethod
    def _friendly_tavern_error(error: Exception) -> str:
        mapping = {
            WaitressUnavailableError: "La mesera seleccionada no está disponible en este momento.",
            SessionConflictError: "Ya existe otra sesión activa. Termina esa charla antes de abrir otra.",
            SessionExpiredError: "La sesión de la Taberna expiró. Inicia una nueva charla.",
            InsufficientBalanceError: "No hay saldo o recurso suficiente para esta operación.",
            TavernConfigurationError: "La Taberna no está completamente configurada para esta operación.",
        }
        for error_type, message in mapping.items():
            if isinstance(error, error_type):
                return message
        return "La operación de la Taberna no pudo completarse de forma segura."

    # ------------------------------------------------------------------
    # Resultados y WebQueue
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_application_finished(self, response: object) -> None:
        self._pending_tasks = max(0, self._pending_tasks - 1)
        self._last_execution = getattr(response, "execution", None)
        text = getattr(response, "text", "") or "Sin respuesta."
        if getattr(
            getattr(response, "decision", None),
            "external_api_authorized",
            False,
        ):
            text = (
                "🔎 Propuesta externa · no canon\n\n"
                + text
            )
        self._append_message("IA-chan", text, "bot")
        self.send_button.setEnabled(self._pending_tasks == 0)
        self.refresh_state()

    @Slot(str)
    def _on_application_failed(self, reason: str) -> None:
        self._pending_tasks = max(0, self._pending_tasks - 1)
        self._append_system(
            "No pude procesar la consulta de forma segura. "
            "El detalle técnico quedó registrado localmente."
        )
        self.send_button.setEnabled(self._pending_tasks == 0)
        self._log_line(f"Application error: {reason}")
        self.refresh_state()

    @Slot(str, str)
    def _on_web_ticket_started(self, ticket_id: str, bot_name: str) -> None:
        self._append_system(
            f"🌐 {bot_name} está atendiendo el ticket web."
        )
        self.refresh_state()

    @Slot(str, str)
    def _on_web_ticket_processed(self, ticket_id: str, response: str) -> None:
        if ticket_id in self._tavern_ticket_ids:
            return
        bot_id = self._web_ticket_ids.get(ticket_id, self._selected_bot_id)
        self._append_message(
            BOT_MAP.get(bot_id, BotProfile(bot_id, bot_id, "🤖", "Web")).name,
            response,
            "bot",
        )
        self.send_button.setEnabled(True)
        self.refresh_state()

    @Slot(str, str)
    def _on_web_ticket_failed(self, ticket_id: str, reason: str) -> None:
        if ticket_id not in self._tavern_ticket_ids:
            self._append_system(
                "El chat web no pudo completar el mensaje. "
                "La cola lo marcó como fallo controlado."
            )
        self._web_ticket_ids.pop(ticket_id, None)
        self.refresh_state()

    @Slot(str, str)
    def _on_web_ticket_finished(self, ticket_id: str, _bot_name: str) -> None:
        self._tavern_ticket_ids.discard(ticket_id)
        self._web_ticket_ids.pop(ticket_id, None)
        self.send_button.setEnabled(self._pending_tasks == 0)
        self.refresh_state()

    @Slot(str, str)
    def _on_web_queue_error(self, ticket_id: str, reason: str) -> None:
        if ticket_id == "__shutdown__":
            return
        self._log_line(f"WebQueue {ticket_id}: {reason}")
        self._on_web_state("WebQueue con evento controlado de resiliencia.")

    @Slot(str)
    def _on_web_state(self, text: str) -> None:
        self.web_hint.setText(text)

    def _on_tavern_notification(self, _chat_id: str, text: str) -> None:
        self._append_message("☕ Taberna", text, "bot")
        self.refresh_state()

    def refresh_state(self) -> None:
        if self._closing:
            return
        self.universe_label.setText(
            f"Novela: {self.default_universe.replace('_', ' ').title()} · "
            f"Provider: {self.provider_id}"
        )
        self._update_bot_tiles()
        self._update_selected_status()
        self._update_footer()

    def _update_bot_tiles(self) -> None:
        turns = {}
        if self._tavern is not None:
            try:
                turns = {
                    item.waitress_id: item
                    for item in self._tavern.list_turns()
                }
            except Exception as error:
                self._log_error("Tavern status refresh", error)

        for profile in BOT_PROFILES:
            tile = self.bot_tiles[profile.bot_id]
            turn = turns.get(profile.bot_id)
            if turn is None:
                tile.set_status("Fuera de Taberna · Web", "warn")
                continue
            if turn.is_resting or not turn.on_shift:
                state = "warn"
                if turn.is_resting:
                    text = "Descansando"
                    remaining = self._safe_rest_remaining(profile.bot_id)
                    if remaining:
                        text += f" · {remaining}s"
                else:
                    text = "Fuera de turno"
            elif turn.is_busy:
                state = "online"
                text = "Atendiendo"
            else:
                state = "online"
                text = "Disponible"
            tile.set_status(text, state)

    def _safe_rest_remaining(self, waitress_id: str) -> int:
        if self._tavern is None:
            return 0
        try:
            return self._tavern.rest_seconds_remaining(waitress_id)
        except Exception:
            return 0

    def _start_selected_tavern_session(self) -> None:
        if self._tavern is None:
            self._append_system("La Taberna no está disponible.")
            return
        try:
            session = self._tavern.get_active_session(DESKTOP_USER)
            if session is None:
                session = self._tavern.start_standard_session(
                    DESKTOP_USER,
                    self._selected_bot_id,
                )
                self._append_system(
                    f"☕ Charla iniciada con "
                    f"{BOT_MAP[self._selected_bot_id].name}. "
                    "Puedes escribir en el modo Taberna."
                )
            self.chat_mode.setCurrentIndex(1)
            self.refresh_state()
        except (
            WaitressUnavailableError,
            SessionConflictError,
            InsufficientBalanceError,
            TavernConfigurationError,
            TavernError,
        ) as error:
            self._append_system(self._friendly_tavern_error(error))

    def _force_selected_rest(self) -> None:
        if self._tavern is None:
            self._append_system("La Taberna no está disponible.")
            return
        profile = BOT_MAP[self._selected_bot_id]
        try:
            self._tavern.force_rest(profile.bot_id)
            self._append_system(
                f"💤 {profile.name} quedó marcada como descansando en SQLite."
            )
            self.refresh_state()
        except (
            WaitressUnavailableError,
            SessionConflictError,
            TavernError,
            ValueError,
        ) as error:
            self._append_system(self._friendly_tavern_error(error))

    def _update_selected_status(self) -> None:
        profile = BOT_MAP[self._selected_bot_id]
        if self._tavern is None:
            self.selected_status.setText(
                "Taberna no disponible; WebQueue puede seguir funcionando."
            )
            return
        try:
            turn = next(
                item
                for item in self._tavern.list_turns()
                if item.waitress_id == profile.bot_id
            )
        except StopIteration:
            self.selected_status.setText(
                "Este personaje no está registrado como mesera en la "
                "base SQLite actual. La conversación individual usa WebQueue."
            )
            return
        remaining = self._safe_rest_remaining(profile.bot_id)
        status = turn.status
        if turn.is_resting:
            status += f" · descanso persistido, {remaining}s restantes"
        self.selected_status.setText(
            f"SQLite · {status} · turno activo: {'sí' if turn.on_shift else 'no'}"
        )

    def _format_rest_state(self) -> str:
        if self._tavern is None:
            return "No hay conexión con la Taberna."
        lines = ["💤 ESTADO DE DESCANSO"]
        try:
            for item in self._tavern.list_turns():
                remaining = self._safe_rest_remaining(item.waitress_id)
                lines.append(
                    f"• {item.display_name}: {item.status} · "
                    f"{remaining}s desde el último ticket"
                )
        except Exception as error:
            self._log_error("Rest status", error)
            return "No pude leer el estado de descanso de SQLite."
        return "\n".join(lines)

    def _update_footer(self) -> None:
        memory_path = self.runtime.memory_store.path
        outbox_state = self._outbox_health(memory_path)
        web_state = (
            "activo"
            if self._web_queue is not None
            else "no disponible"
        )
        self.statusBar().showMessage(
            f"Backend: online · Outbox: {outbox_state} · "
            f"WebQueue: {web_state}"
        )

    @staticmethod
    def _outbox_health(database_path: Path) -> str:
        if not database_path.is_file():
            return "sin DB"
        try:
            with closing(
                sqlite3.connect(database_path, timeout=2.0)
            ) as connection:
                row = connection.execute(
                    "SELECT COUNT(*) FROM telegram_outbox "
                    "WHERE status='PENDING'"
                ).fetchone()
            return f"ready · {int(row[0])} pendientes"
        except (OSError, sqlite3.Error):
            return "error"

    # ------------------------------------------------------------------
    # Paneles de administración
    # ------------------------------------------------------------------

    def _set_page(self, index: int) -> None:
        # El diseño mantiene el chat como protagonista. Los paneles laterales
        # reutilizan el stack del web card para no duplicar backend.
        if index == 1:
            self._show_operations_dialog()
        elif index == 2:
            self._show_web_dialog()

    def _show_operations_dialog(self) -> None:
        dialog = QWidget()
        dialog.setWindowTitle("Café Otaku · Operaciones")
        dialog.setMinimumSize(900, 680)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            SectionHeader(
                "Operaciones y administración",
                "Sólo aparecen acciones respaldadas por el backend actual. "
                "No se simulan APIs de grupos o X/Twitter que todavía no existen.",
            )
        )

        grid = QGridLayout()
        layout.addLayout(grid)

        project_card = CardFrame()
        project_layout = QVBoxLayout(project_card)
        project_layout.addWidget(QLabel("📚 Proyectos / novelas"))
        project_input = QLineEdit()
        project_input.setPlaceholderText("Nombre de nueva novela")
        project_layout.addWidget(project_input)
        create_button = QPushButton("Crear novela")
        create_button.clicked.connect(
            lambda: self._create_project_from_ui(project_input, dialog)
        )
        project_layout.addWidget(create_button)
        grid.addWidget(project_card, 0, 0)

        telegram_card = CardFrame()
        telegram_layout = QVBoxLayout(telegram_card)
        telegram_layout.addWidget(QLabel("📡 Telegram"))
        telegram_layout.addWidget(
            QLabel(
                "Inicia el worker separado. El punto de entrada de producción "
                "inyecta TelegramOutboxStore automáticamente."
            )
        )
        telegram_button = QPushButton(self._telegram_button_text())
        telegram_button.clicked.connect(
            lambda: self.start_telegram(telegram_button)
        )
        telegram_layout.addWidget(telegram_button)
        grid.addWidget(telegram_card, 0, 1)

        web_chat_card = CardFrame()
        web_chat_layout = QVBoxLayout(web_chat_card)
        web_chat_layout.addWidget(QLabel("🌐 Chat web local"))
        web_chat_layout.addWidget(
            QLabel(
                "Arranca la API HTML/JSON local de WebChat. Usa el mismo "
                "runtime, memoria, evidencia y provider configurado."
            )
        )
        web_chat_button = QPushButton(self._web_chat_button_text())
        web_chat_button.clicked.connect(
            lambda: self.start_web_chat(web_chat_button)
        )
        web_chat_layout.addWidget(web_chat_button)
        grid.addWidget(web_chat_card, 0, 2)

        provider_card = CardFrame()
        provider_layout = QVBoxLayout(provider_card)
        provider_layout.addWidget(QLabel("🤖 Providers"))
        health = getattr(self.runtime.provider_manager, "_health", {})
        if not health:
            provider_layout.addWidget(
                QLabel("Todavía no hay métricas de provider en memoria.")
            )
        else:
            for (provider, account), record in sorted(health.items()):
                provider_layout.addWidget(
                    QLabel(
                        f"{provider}/{account} · "
                        f"{getattr(record.state, 'value', record.state)} · "
                        f"requests={record.total_requests}"
                    )
                )
        grid.addWidget(provider_card, 1, 0)

        bots_card = CardFrame()
        bots_layout = QVBoxLayout(bots_card)
        bots_layout.addWidget(QLabel("🤖 BOTS · credenciales"))
        bots_layout.addWidget(
            QLabel(
                "Administra los tokens de Cari, Cami, Sunna, Chie, Chloe y Scarlet. "
                "Se cargan desde .env al iniciar la aplicación."
            )
        )
        bots_button = QPushButton("Abrir gestión de BOTS")
        bots_button.clicked.connect(self._show_bots_credentials_dialog)
        bots_layout.addWidget(bots_button)
        grid.addWidget(bots_card, 1, 2)

        config_card = CardFrame()
        config_layout = QVBoxLayout(config_card)
        config_layout.addWidget(
            QLabel("⚙ PROVEEDORES LLM / APIs")
        )
        config_layout.addWidget(
            QLabel(
                "Guarda claves, tokens y selección de provider en .env "
                "con aplicación inmediata al runtime."
            )
        )
        config_button = QPushButton("Abrir configuración")
        config_button.clicked.connect(
            self._show_dynamic_config_dialog
        )
        config_layout.addWidget(config_button)
        grid.addWidget(config_card, 2, 1)

        diagnostic_card = CardFrame()
        diagnostic_layout = QVBoxLayout(diagnostic_card)
        diagnostic_layout.addWidget(
            QLabel("🔍 DIAGNÓSTICO Y ANÁLISIS")
        )
        diagnostic_layout.addWidget(
            QLabel(
                "Sentry inspecciona Gemini Web, Telegram, providers "
                "y la integridad SQLite."
            )
        )
        diagnostic_button = QPushButton("Ejecutar Sentry")
        diagnostic_button.clicked.connect(
            self._show_diagnostic_dialog
        )
        diagnostic_layout.addWidget(diagnostic_button)
        grid.addWidget(diagnostic_card, 2, 2)

        network_card = CardFrame()
        network_layout = QVBoxLayout(network_card)
        network_layout.addWidget(QLabel("🗺️ Redes y canales"))
        network_layout.addWidget(
            QLabel(
                "No existe actualmente una API de mapeo X/Twitter ↔ Telegram "
                "en el backend. El panel no presenta botones ficticios."
            )
        )
        grid.addWidget(network_card, 1, 1)

        admin_card = CardFrame()
        admin_layout = QVBoxLayout(admin_card)
        admin_layout.addWidget(QLabel("🛡 Orquestación"))
        admin_layout.addWidget(
            QLabel(
                "El backend actual expone la orquestación mediante "
                "TelegramProjectsAdapter y WebChatQueueManager. La creación "
                "de grupos/admins de Telegram no está implementada por la API "
                "actual, por lo que no se emula."
            )
        )
        grid.addWidget(admin_card, 2, 0)

        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.close)
        layout.addWidget(close, 0, Qt.AlignRight)

        self._dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda _obj=None: self._discard_dialog(dialog)
        )
        dialog.show()

    def _discard_dialog(self, dialog: QWidget) -> None:
        try:
            self._dialogs.remove(dialog)
        except ValueError:
            return

    def _create_project_from_ui(
        self,
        field: QLineEdit,
        dialog: QWidget,
    ) -> None:
        name = field.text().strip()
        if not name:
            return
        try:
            record = self.runtime.create_novel(
                name,
                application=self.application,
            )
            self._append_system(
                f"✅ Novela creada y conectada: {record.display_name} "
                f"({record.project_id})."
            )
            field.clear()
            dialog.close()
            self.refresh_state()
        except Exception as error:
            self._log_error("Create project", error)
            QMessageBox.warning(
                dialog,
                "Café Otaku",
                "No se pudo crear la novela de forma segura.",
            )

    def _show_web_dialog(self) -> None:
        dialog = QWidget()
        dialog.setWindowTitle("Café Otaku · WebQueue")
        dialog.setMinimumSize(900, 700)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            SectionHeader(
                "Automatización web",
                "La vista compartida usa el mismo WebChatQueueManager, "
                "MutationObserver, circuit breaker y protocolo anti-zombie.",
            )
        )
        url = QLineEdit(self.web_url.text())
        layout.addWidget(url)
        open_button = QPushButton("Cargar en navegador principal")
        open_button.clicked.connect(
            lambda: self._copy_web_url(url.text(), dialog)
        )
        layout.addWidget(open_button)
        detail = QLabel(
            "Las respuestas web se muestran en el chat central. "
            "El navegador sólo actúa como superficie de automatización."
        )
        detail.setObjectName("Muted")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.close)
        layout.addWidget(close, 0, Qt.AlignRight)
        dialog.show()

    def _copy_web_url(self, raw: str, dialog: QWidget) -> None:
        self.web_url.setText(raw.strip())
        self._navigate_web()
        dialog.close()

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    def _telegram_button_text(self) -> str:
        if (
            self._telegram_process is not None
            and self._telegram_process.poll() is None
        ):
            return "● Telegram activo"
        return "▶ Iniciar Telegram"

    def _web_chat_button_text(self) -> str:
        if (
            self._web_chat_process is not None
            and self._web_chat_process.poll() is None
        ):
            return "● Chat local activo"
        return "▶ Iniciar Chat local"

    def start_web_chat(self, button: QPushButton | None = None) -> None:
        process = self._web_chat_process
        if process is not None and process.poll() is None:
            if button is not None:
                button.setText("● Chat local activo")
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--web-chat-worker"]
        else:
            command = [
                sys.executable,
                "-m",
                "desktop_entry",
                "--web-chat-worker",
            ]
        try:
            self._web_chat_process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if button is not None:
                button.setText("● Chat local iniciando…")
            host = os.getenv("BOT_IA_HOST", "127.0.0.1")
            port = os.getenv("BOT_IA_PORT", "8787")
            browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
            self._append_system(
                f"Chat web local iniciado en http://{browser_host}:{port}/."
            )
            try:
                import webbrowser

                webbrowser.open(
                    f"http://{browser_host}:{port}/"
                )
            except OSError:
                pass
        except (OSError, ValueError) as error:
            self._log_error("Web chat launch", error)
            self._append_system(
                "No se pudo iniciar el Chat Web local."
            )

    def start_telegram(self, button: QPushButton | None = None) -> None:
        process = self._telegram_process
        if process is not None and process.poll() is None:
            if button is not None:
                button.setText("● Telegram activo")
            return

        if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
            self._append_system(
                "Telegram no está configurado. Añade TELEGRAM_BOT_TOKEN "
                "en tu configuración local."
            )
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--telegram-worker"]
        else:
            command = [
                sys.executable,
                "-m",
                "bot_ia",
                "--mode",
                "telegram",
            ]
        try:
            self._telegram_process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if button is not None:
                button.setText("● Telegram iniciando…")
            self._append_system(
                "Telegram inició en proceso separado. "
                "La UI principal sigue disponible."
            )
        except (OSError, ValueError) as error:
            self._log_error("Telegram launch", error)
            self._append_system(
                "No se pudo iniciar Telegram desde esta sesión."
            )

    def _refresh_telegram_process(self) -> None:
        process = self._telegram_process
        if process is not None and process.poll() is not None:
            code = process.returncode
            self._telegram_process = None
            if code != 0:
                self._append_system(
                    "Telegram terminó con un estado no exitoso. "
                    "Los detalles técnicos quedan fuera de la UI."
                )

        process = self._web_chat_process
        if process is not None and process.poll() is not None:
            code = process.returncode
            self._web_chat_process = None
            if code != 0:
                self._append_system(
                    "El Chat Web local terminó con un estado no exitoso."
                )

        self.local_web_button.setText(
            self._web_chat_button_text()
        )
        self.refresh_state()

    # ------------------------------------------------------------------
    # Cierre y logging
    # ------------------------------------------------------------------

    def _log_error(self, context: str, error: Exception) -> None:
        self._log_line(
            f"{context}: {type(error).__name__}: {error}\n"
            + traceback.format_exc()
        )

    @staticmethod
    def _log_line(message: str) -> None:
        log_path = ROOT / "work" / "gui.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(message.rstrip() + "\n")
        except OSError:
            return

    def closeEvent(self, event) -> None:  # noqa: N802
        for dialog in tuple(self._expanded_bot_dialogs.values()):
            dialog.hide()
            dialog.deleteLater()
        self._expanded_bot_dialogs.clear()
        if self._waifu_dialog is not None:
            self._waifu_dialog.close()
            self._waifu_dialog.deleteLater()
            self._waifu_dialog = None

        if self._closing:
            event.accept()
            return
        self._closing = True
        self._telegram_poll_timer.stop()

        if (
            self._telegram_process is not None
            and self._telegram_process.poll() is None
        ):
            self._telegram_process.terminate()

        if (
            self._web_chat_process is not None
            and self._web_chat_process.poll() is None
        ):
            self._web_chat_process.terminate()

        if self._tavern is not None:
            try:
                self._tavern.shutdown()
            except Exception as error:
                self._log_error("Tavern shutdown", error)

        if self._web_queue is not None:
            try:
                self._web_queue.shutdown()
                thread = getattr(self._web_queue, "_thread", None)
                if thread is not None and thread.isRunning():
                    thread.wait(2200)
            except Exception as error:
                self._log_error("WebQueue shutdown", error)

        if (
            self._diagnostic_thread is not None
            and self._diagnostic_thread.isRunning()
        ):
            self._diagnostic_thread.requestInterruption()
            self._diagnostic_thread.quit()
            self._diagnostic_thread.wait(1000)

        if self._matrix_dispatcher.is_running:
            self._matrix_dispatcher.stop()

        if self._manual_setup_thread is not None:
            self._manual_setup_thread.requestInterruption()
            self._manual_setup_thread.quit()
            if self._manual_setup_thread.isRunning():
                self._manual_setup_thread.wait(1_500)
            self._manual_setup_thread = None
            self._manual_setup_worker = None

        try:
            self.task_pool.waitForDone(2200)
        except Exception as error:
            self._log_error("Task pool shutdown", error)

        try:
            self.runtime.memory_store.close()
        except Exception as error:
            self._log_error("Runtime close", error)

        event.accept()


CafeOtakuWindow = CommandCenterWindow


async def _async_main(app: QApplication) -> int:
    quit_event = asyncio.Event()
    app.aboutToQuit.connect(quit_event.set)

    window = CommandCenterWindow()
    window.select_bot("cari")
    window.show()

    web_queue = WebQueueManager()
    orchestrator = TaskOrchestrator(
        web_worker_callback=web_queue.process_task,
        gui_signal_emitter=window.bridge_signal_adapter,
    )

    try:
        await web_queue.init_browser_pool()
    except Exception as error:
        window._log_error("Playwright startup", error)
        window._append_system(
            "El motor Playwright no pudo iniciar. "
            "La interfaz principal continúa disponible."
        )
    else:
        window.set_async_engine(orchestrator, web_queue)
        asyncio.create_task(orchestrator.start_worker())

    await quit_event.wait()
    await window.shutdown_async_engine()
    return 0


def _qt_main(app: QApplication) -> int:
    window = CommandCenterWindow()
    window.select_bot("cari")
    window.show()
    return app.exec()


def main() -> int:
    load_dotenv(ROOT / ".env", override=False)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Café Otaku · BOT-IA")
    app.setStyle("Fusion")

    if (
        QEventLoop is not None
        and sys.version_info < (3, 14)
    ):
        return asyncio.run(
            _async_main(app),
            loop_factory=QEventLoop,
        )

    return _qt_main(app)


if __name__ == "__main__":
    raise SystemExit(main())
