# -*- coding: utf-8 -*-
"""Ventana principal Dark Cozy de Café Otaku sobre el backend único de BOT-IA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import traceback
from contextlib import closing

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from bot_ia.core.application import ApplicationRequest
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
from .styles import application_qss
from .widgets import BotTile, CardFrame, PillButton, SectionHeader


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


class CafeOtakuWindow(QMainWindow):
    """UI principal que conserva el runtime y backend existentes."""

    def __init__(self, runtime: RuntimeComponents | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Café Otaku · BOT-IA")
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
            self._on_web_result
        )
        self.signals.web_failed.connect(
            self._on_web_failed
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
        self._dialogs: list[QWidget] = []
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

        self.web_button = QPushButton("🌐 Web")
        self.web_button.clicked.connect(
            lambda: self._set_page(2)
        )
        top_layout.addWidget(self.web_button)

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
            tile.clicked_bot.connect(self.select_bot)
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
            chips.addWidget(pill)
        chips.addStretch(1)

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
                f"WebQueue no disponible: {type(error).__name__}"
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

    def _quick_action(self, action_id: str) -> None:
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
            f"Detalle registrado: {reason.split(':', 1)[0]}."
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
        if process is None:
            return
        if process.poll() is None:
            return
        code = process.returncode
        self._telegram_process = None
        if code != 0:
            self._append_system(
                "Telegram terminó con un estado no exitoso. "
                "Los detalles técnicos quedan fuera de la UI."
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

        try:
            self.task_pool.waitForDone(2200)
        except Exception as error:
            self._log_error("Task pool shutdown", error)

        try:
            self.runtime.memory_store.close()
        except Exception as error:
            self._log_error("Runtime close", error)

        event.accept()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Café Otaku · BOT-IA")
    app.setStyle("Fusion")
    window = CafeOtakuWindow()
    window.select_bot("cari")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
