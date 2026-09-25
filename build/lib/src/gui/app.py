from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

import keyring
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QSettings, QThread, Signal, Slot, Qt, QTimer

from src.gui.llm_pool import LLMProviderPoolWidget
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

BOTS = ("cari", "sunna", "cami", "chie", "scarlet", "chloe")
# Dynamic LLM provider pool support is managed by the Command Center.

def _secure_get(identity: str) -> str:
    try:
        return keyring.get_password("cafe-otaku.telegram", identity) or ""
    except Exception:
        return ""


def _secure_set(identity: str, token: str) -> None:
    keyring.set_password("cafe-otaku.telegram", identity, token)




class GeminiLobbyWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    @Slot()
    def run(self) -> None:
        try:
            from app.brain.dynamic_pool import DynamicLLMPool
            from app.brain.provider import BrainClient, LLMRequest
            from app.core.config import get_settings
            from app.core.identity import BotIdentity

            provider = next(
                (
                    item for item in DynamicLLMPool.configs()
                    if str(item.get("provider", "")).casefold() == "google gemini"
                ),
                None,
            )
            if provider is None:
                raise RuntimeError("No hay una instancia Google Gemini habilitada en el LLM Pool.")

            brain = BrainClient(get_settings())
            result = DynamicLLMPool.generate(
                provider,
                LLMRequest(
                    identity=BotIdentity.CARI,
                    user_text=self.text,
                    recent_context=(),
                    persona=(
                        "Sos Gemini, la IA coordinadora del Lobby Unido. "
                        "Respondé en español rioplatense, breve y natural. "
                        "No suplantes a Cari, Cami, Chie, Sunna, Chloe ni Scarlet."
                    ),
                    max_tokens=220,
                    max_user_chars=1500,
                    temperature=0.7,
                ),
                brain._post_json,
                brain._messages,
                brain._system_prompt,
            )
            cleaned = brain._clean(result)
            if not cleaned:
                raise RuntimeError("Gemini devolvió una respuesta vacía.")
            self.finished.emit(cleaned)
        except Exception as exc:
            self.failed.emit(f"Gemini no disponible: {exc}")


class LobbyEventWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, db_path: str, event_type: str, payload: dict) -> None:
        super().__init__()
        self.db_path, self.event_type, self.payload = db_path, event_type, payload

    @Slot()
    def run(self) -> None:
        try:
            parent = os.path.dirname(self.db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            event_id = uuid.uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS domain_events (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        last_error TEXT,
                        available_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        locked_at TEXT,
                        heartbeat_at TEXT,
                        completed_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO domain_events
                    (event_id, event_type, payload, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        event_id,
                        self.event_type,
                        json.dumps(self.payload, ensure_ascii=False, separators=(",", ":")),
                        now,
                        now,
                    ),
                )
                conn.commit()
            self.finished.emit({"event_id": event_id, "event_type": self.event_type})
        except (sqlite3.Error, OSError) as exc:
            self.failed.emit(f"Evento no disponible: {exc}")


class LobbyMessage:
    def __init__(self, speaker: str, text: str) -> None:
        self.speaker = speaker
        self.text = text


class HttpActionWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        method: str,
        url: str,
        token: str = "",
        payload: dict | None = None,
    ) -> None:
        super().__init__()
        self.method, self.url, self.token, self.payload = method, url, token, payload

    @Slot()
    def run(self) -> None:
        try:
            body = None
            headers = {"Accept": "application/json"}
            if self.payload is not None:
                body = json.dumps(self.payload).encode()
                headers["Content-Type"] = "application/json"
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            request = Request(
                self.url,
                data=body,
                headers=headers,
                method=self.method,
            )
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode(errors="replace")
            try:
                payload = json.loads(raw) if raw else {"status": "ok"}
            except json.JSONDecodeError:
                payload = {"status": "ok", "raw": raw[:500]}
            self.finished.emit(payload)
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            self.failed.emit(f"HTTP {exc.code}: {detail}")
        except (URLError, TimeoutError, OSError) as exc:
            self.failed.emit(f"Acción no disponible: {exc}")


class CredentialVerificationWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, credentials: dict[str, str]) -> None:
        super().__init__()
        self.credentials = credentials

    @Slot()
    def run(self) -> None:
        try:
            verified = {}
            for identity, token in self.credentials.items():
                request = Request(
                    f"https://api.telegram.org/bot{token}/getMe",
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with urlopen(request, timeout=10) as response:
                    payload = json.loads(response.read().decode(errors="replace"))
                if not payload.get("ok") or not payload.get("result"):
                    raise RuntimeError(f"{identity}: Telegram rechazó el token.")
                verified[identity] = token
            for identity, token in verified.items():
                keyring.set_password("cafe-otaku.telegram", identity, token)
            self.finished.emit({"verified": sorted(verified)})
        except Exception as exc:
            self.failed.emit(f"Verificación de credenciales fallida: {exc}")


class BootstrapWorker(HttpActionWorker):
    def __init__(self, base_url: str, token: str, chat_id: int) -> None:
        super().__init__(
            "POST",
            f"{base_url.rstrip('/')}/api/v1/system/bootstrap",
            token,
            {"chat_id": chat_id},
        )


class EventLogWorker(QObject):
    refreshed = Signal(list)
    failed = Signal(str)

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.db_path = db_path

    @Slot()
    def run(self) -> None:
        try:
            if not os.path.exists(self.db_path):
                self.refreshed.emit([])
                return
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute(
                        """
                        SELECT event_id, event_type, '' AS bot_name, status, attempts AS retry_count,
                               5 AS max_retries, last_error, updated_at
                        FROM domain_events ORDER BY updated_at DESC LIMIT 200
                        """
                    ).fetchall()
                except sqlite3.OperationalError as exc:
                    if "no such table" in str(exc).lower():
                        self.refreshed.emit([])
                        return
                    raise
            self.refreshed.emit([dict(row) for row in rows])
        except sqlite3.Error as exc:
            self.failed.emit(f"SQLite: {exc}")


class CommandCenterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Casa de Comando")
        self.resize(1200, 800)
        self._threads: list[QThread] = []
        self.settings = QSettings("CafeOtaku", "CommandCenter")
        self.bot_cards: dict[str, dict[str, QWidget]] = {}

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.bot_status: dict[str, QLabel] = {}
        self._build_presence_panel(layout)

        logs_box = QGroupBox("📜 EVENT LOGS / DLQ")
        logs_box.setObjectName("EventLogsPanel")
        logs_layout = QVBoxLayout(logs_box)
        self.logs = QTableWidget(0, 7)
        self.logs.setHorizontalHeaderLabels(
            ["Event ID", "Tipo", "Bot", "Estado", "Reintentos", "Máx.", "Último error"]
        )
        self.logs.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.logs.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        logs_layout.addWidget(self.logs)
        layout.addWidget(logs_box, 1)

        self.actions = QTabWidget()
        self.actions.setObjectName("SectionTabs")
        self.actions.addTab(self._credentials_tab(), "🚨 BOTS")
        self.actions.addTab(self._lobby_tab(), "🏠 LOBBY UNIDO")
        self.actions.addTab(self._worker_tab(), "🛠️ CHAT OBRERO")
        self.llm_pool = LLMProviderPoolWidget()
        self.llm_pool.status_changed.connect(self._llm_pool_status)
        self.llm_pool.event_requested.connect(self.refresh_events)
        self.actions.addTab(self.llm_pool, "⚡ PROVEEDORES LLM / APIs")
        self.actions.addTab(self._permissions_tab(), "🔐 PERMISOS")
        self.actions.addTab(self._bootstrap_tab(), "📥 PEDIDOS")
        self.actions.addTab(self._actions_tab(), "🌿 ANIMALS CITY")
        self.actions.addTab(self._social_tab(), "📡 REDES")
        self.actions.addTab(self._vault_tab(), "📦 BÓVEDA")
        self.actions.currentChanged.connect(self._apply_section_theme)
        layout.addWidget(self.actions)
        self._apply_section_theme(self.actions.currentIndex())
        self._refresh_presence()
        QTimer.singleShot(300, self._boot_sequence)

        self.refresh_events()

    def _build_presence_panel(self, parent_layout: QVBoxLayout) -> None:
        box = QGroupBox("Monitor de Presencia y Estado de Bots")
        outer = QVBoxLayout(box)
        grid = QGridLayout()
        for index, identity in enumerate(BOTS):
            card = QGroupBox(identity.title())
            card.setObjectName("BotCard")
            card_layout = QVBoxLayout(card)
            status = QLabel()
            status.setObjectName("BotStatus")
            chat = QLabel()
            action = QLabel("Última acción: —")
            toggle = QPushButton("Iniciar / Pausar")
            toggle.clicked.connect(lambda checked=False, bot=identity: self.toggle_bot(bot))
            card_layout.addWidget(status)
            card_layout.addWidget(chat)
            card_layout.addWidget(action)
            card_layout.addWidget(toggle)
            self.bot_status[identity] = status
            self.bot_cards[identity] = {"status": status, "chat": chat, "action": action, "toggle": toggle}
            grid.addWidget(card, index // 3, index % 3)
        outer.addLayout(grid)
        controls = QHBoxLayout()
        self.emergency_button = QPushButton("STOP GENERAL / EMERGENCY KILL SWITCH")
        self.emergency_button.setObjectName("EmergencyButton")
        self.emergency_button.clicked.connect(self.emergency_stop)
        controls.addWidget(self.emergency_button)
        self.presence_status = QLabel("Control de presencia local listo.")
        controls.addWidget(self.presence_status, 1)
        outer.addLayout(controls)
        parent_layout.addWidget(box)

    def _bot_enabled(self, identity: str) -> bool:
        return self.settings.value(f"bots/{identity}/enabled", True, type=bool)

    def _bot_permission(self, identity: str, module: str) -> bool:
        return self.settings.value(f"permissions/{identity}/{module}", True, type=bool)

    def _bot_chat_id(self, identity: str) -> str:
        return os.getenv(f"BOT_CHAT_ID_{identity.upper()}", self.settings.value("bootstrap/chat_id", "", type=str))

    def _last_action(self, identity: str) -> str:
        return self.settings.value(f"bots/{identity}/last_action", "—", type=str)

    def _set_bot_state(self, identity: str, enabled: bool, action: str | None = None) -> None:
        self.settings.setValue(f"bots/{identity}/enabled", enabled)
        if action:
            self.settings.setValue(f"bots/{identity}/last_action", action)
        token = self._token_for(identity)
        status = self.bot_cards[identity]["status"]
        status.setText("OFFLINE" if not token else ("ONLINE" if enabled else "STANDBY"))
        self.bot_cards[identity]["chat"].setText(f"Chat ID: {self._bot_chat_id(identity) or 'no asignado'}")
        self.bot_cards[identity]["action"].setText(f"Última acción: {self._last_action(identity)}")

    def _refresh_presence(self) -> None:
        for identity in BOTS:
            self._set_bot_state(identity, self._bot_enabled(identity))

    def toggle_bot(self, identity: str) -> None:
        enabled = not self._bot_enabled(identity)
        self._set_bot_state(identity, enabled, "Iniciado" if enabled else "Pausado")
        self.presence_status.setText(f"{identity.title()}: {'ONLINE' if enabled and self._token_for(identity) else 'STANDBY'}")

    def emergency_stop(self) -> None:
        for identity in BOTS:
            self._set_bot_state(identity, False, "EMERGENCY STOP")
        self.presence_status.setText("EMERGENCY STOP activo: los seis bots están en STANDBY.")

    def _set_status_from_config(self, identity: str) -> None:
        token = os.getenv(f"BOT_TOKEN_{identity.upper()}", "")
        health_url = os.getenv(f"{identity.upper()}_HEALTH_URL", "")
        if token or health_url:
            self.bot_status[identity].setText(f"{identity.title()}: CONFIGURADO")
        else:
            self.bot_status[identity].setText(f"{identity.title()}: NO CONFIGURADO")

    def _credentials_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionBots")
        layout = QVBoxLayout(tab)
        box = QGroupBox("Configuración de Credenciales (API Tokens)")
        form = QFormLayout(box)
        self.token_inputs: dict[str, QLineEdit] = {}
        for identity in BOTS:
            field = QLineEdit()
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText(f"Token de {identity.title()}")
            if keyring.get_password("cafe-otaku.telegram", identity):
                field.setPlaceholderText("Token guardado de forma segura")
            self.token_inputs[identity] = field
            form.addRow(f"{identity.title()}:", field)
        self.credentials_button = QPushButton("Guardar y Verificar Conexión")
        self.credentials_status = QLabel("Los tokens se guardan en el almacén seguro del sistema.")
        self.credentials_button.clicked.connect(self.save_and_verify_credentials)
        layout.addWidget(box)
        layout.addWidget(self.credentials_button)
        layout.addWidget(self.credentials_status)
        layout.addStretch()
        return tab

    def _llm_pool_status(self, message: str) -> None:
        self.presence_status.setText(f"LLM Pool: {message}")
        self.refresh_events()

    def _publish_lobby_event(self, event_type: str, payload: dict) -> None:
        worker = LobbyEventWorker(
            os.getenv("COMMAND_CENTER_DB_PATH", "data/command_center_events.db"),
            event_type,
            payload,
        )
        self._start_worker(worker, "finished", self._lobby_event_done, self._lobby_event_failed)

    @Slot(dict)
    def _lobby_event_done(self, payload: dict) -> None:
        self.refresh_events()

    @Slot(str)
    def _lobby_event_failed(self, message: str) -> None:
        if hasattr(self, "lobby_status"):
            self.lobby_status.setText(message)

    def _lobby_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionLobby")
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("🏠 LOBBY UNIDO · Usuario + Gemini + Cari · Cami · Chie · Sunna · Chloe · Scarlet"))

        self.lobby_transcript = QTextBrowser()
        self.lobby_transcript.setOpenExternalLinks(False)
        layout.addWidget(self.lobby_transcript, 1)

        row = QHBoxLayout()
        self.lobby_input = QLineEdit()
        self.lobby_input.setPlaceholderText("Escribí un mensaje para todo el lobby…")
        self.lobby_send = QPushButton("Enviar al Lobby")
        self.lobby_gemini = QPushButton("✨ Consultar Gemini")
        row.addWidget(self.lobby_input, 1)
        row.addWidget(self.lobby_send)
        row.addWidget(self.lobby_gemini)
        layout.addLayout(row)

        self.lobby_status = QLabel("Esperando Boot-Up Sequence…")
        layout.addWidget(self.lobby_status)
        self.lobby_send.clicked.connect(self._send_lobby_message)
        self.lobby_input.returnPressed.connect(self._send_lobby_message)
        self.lobby_gemini.clicked.connect(self._request_lobby_gemini)
        return tab

    def _append_lobby(self, speaker: str, message: str) -> None:
        self.lobby_transcript.append(f"<b>{speaker}</b>: {message}")

    def _send_lobby_message(self) -> None:
        text = self.lobby_input.text().strip()
        if not text:
            return
        self._append_lobby("Usuario", text)
        self.lobby_input.clear()
        self.lobby_status.setText("Mensaje del usuario encolado para el canal multi-agente.")
        self._publish_lobby_event(
            "LOBBY_MESSAGE",
            {"speaker": "user", "text": text, "channel": "lobby"},
        )

    def _request_lobby_gemini(self) -> None:
        text = self.lobby_input.text().strip()
        if not text:
            text = "Saludá al lobby de forma breve y natural."
        self.lobby_input.clear()
        self._append_lobby("Usuario", text)
        self._append_lobby("Gemini", "Procesando…")
        self.lobby_gemini.setEnabled(False)
        self.lobby_status.setText("Gemini está procesando en un worker separado.")
        self._publish_lobby_event(
            "LOBBY_GEMINI_REQUESTED",
            {"speaker": "gemini", "text": text, "channel": "lobby"},
        )
        self._start_worker(
            GeminiLobbyWorker(text),
            "finished",
            self._gemini_done,
            self._gemini_failed,
        )

    @Slot(str)
    def _gemini_done(self, message: str) -> None:
        self.lobby_gemini.setEnabled(True)
        self._append_lobby("Gemini", message)
        self.lobby_status.setText("Gemini respondió en el Lobby Unido.")

    @Slot(str)
    def _gemini_failed(self, message: str) -> None:
        self.lobby_gemini.setEnabled(True)
        self._append_lobby("Gemini", message)
        self.lobby_status.setText(message)

    def _boot_sequence(self) -> None:
        greetings = (
            ("Gemini", "Hola. Estoy listo para coordinar el canal y asistir cuando haga falta."),
            ("Cari", "¡Hola! Ya estoy acá. ¡Que empiece el lobby! ✨"),
            ("Cami", "Buenas. Canal inicializado. Mantengamos todo ordenado."),
            ("Chie", "¡H-hola a todos! Qué bueno que ya estemos reunidos. 🌸"),
            ("Sunna", "Hm. Ya llegué. No armen demasiado ruido."),
            ("Chloe", "¡Hola! La bóveda y los recursos quedan bajo control."),
            ("Scarlet", "Buenas. Lista para noticias, publicaciones y avisos."),
        )
        for speaker, message in greetings:
            self._append_lobby(speaker, message)
            self._publish_lobby_event(
                "LOBBY_BOOT_GREETING",
                {"speaker": speaker.casefold(), "text": message, "channel": "lobby"},
            )
        self.lobby_status.setText("Boot-Up Sequence completada: 7 participantes activos.")

    def _worker_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionWorker")
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("🛠️ CHAT OBRERO · Canal de procesamiento pesado"))

        info = QGroupBox("Backend / LLM secundario")
        info_layout = QVBoxLayout(info)
        info_layout.addWidget(QLabel(
            "Encola ingestas masivas, análisis y generación de trivias sin bloquear el Lobby."
        ))
        layout.addWidget(info)

        self.worker_task = QTextEdit()
        self.worker_task.setPlaceholderText(
            "Describe una tarea pesada: ingesta de archivos, indexación, análisis o generación de trivia…"
        )
        layout.addWidget(self.worker_task, 1)

        row = QHBoxLayout()
        self.worker_ingest = QPushButton("📥 Encolar Ingesta Masiva")
        self.worker_trivia = QPushButton("🎲 Generar Trivia")
        row.addWidget(self.worker_ingest)
        row.addWidget(self.worker_trivia)
        layout.addLayout(row)

        self.worker_status = QLabel("Obrero listo. Las tareas se procesan fuera del hilo de la GUI.")
        layout.addWidget(self.worker_status)
        self.worker_ingest.clicked.connect(self._queue_worker_ingest)
        self.worker_trivia.clicked.connect(self._queue_worker_trivia)
        return tab

    def _queue_worker_ingest(self) -> None:
        task = self.worker_task.toPlainText().strip()
        if not task:
            self.worker_status.setText("Especificá qué datos se deben ingerir.")
            return
        self.worker_status.setText("Ingesta pesada encolada para el backend secundario.")
        self._publish_lobby_event(
            "WORKER_HEAVY_INGEST_REQUESTED",
            {"task": task, "channel": "worker", "backend": "secondary_llm"},
        )

    def _queue_worker_trivia(self) -> None:
        task = self.worker_task.toPlainText().strip() or "Generar una trivia de anime a partir del catálogo disponible."
        self.worker_status.setText("Generación de trivia encolada para el backend secundario.")
        self._publish_lobby_event(
            "WORKER_TRIVIA_REQUESTED",
            {"task": task, "channel": "worker", "backend": "secondary_llm"},
        )

    def _permissions_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionPermissions")
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Permisos persistentes por bot."))
        self.permission_checks: dict[str, dict[str, QCheckBox]] = {}
        for identity in BOTS:
            box = QGroupBox(identity.title())
            row = QHBoxLayout(box)
            self.permission_checks[identity] = {}
            for module in ("gacha", "feed", "mod", "trivia"):
                check = QCheckBox(module.title())
                check.setChecked(self._bot_permission(identity, module))
                check.stateChanged.connect(lambda state, bot=identity, mod=module: self.set_permission(bot, mod, state == 2))
                self.permission_checks[identity][module] = check
                row.addWidget(check)
            layout.addWidget(box)
        layout.addStretch()
        return tab

    def set_permission(self, identity: str, module: str, enabled: bool) -> None:
        self.settings.setValue(f"permissions/{identity}/{module}", enabled)

    def _actions_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionAnimalsCity")
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("🌿 ANIMALS CITY · Juegos y eventos"))
        layout.addWidget(QLabel("Panel de minijuegos y eventos · verde selva + marrón madera"))
        self.action_cari = QPushButton("Activar minijuego de Cari")
        self.action_vault = QPushButton("Iniciar ingesta de cartas Sunna / Chloe")
        self.action_news = QPushButton("Enviar noticias con Scarlet")
        self.action_status = QLabel("Listo.")
        for button in (self.action_cari, self.action_vault, self.action_news):
            layout.addWidget(button)
        layout.addWidget(self.action_status)
        self.action_cari.clicked.connect(lambda: self.run_configured_action("cari", "COMMAND_CENTER_CARI_ACTION"))
        self.action_vault.clicked.connect(lambda: self.run_configured_action("sunna", "COMMAND_CENTER_VAULT_INGEST_ACTION"))
        self.action_news.clicked.connect(lambda: self.run_configured_action("scarlet", "COMMAND_CENTER_SCARLET_NEWS_ACTION"))
        layout.addStretch()
        return tab

    def _social_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionSocial")
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Chie / Scarlet — acciones de publicación aisladas del runtime del grupo."))
        self.feed_button = QPushButton("Publicar Feed en Redes")
        self.feed_status = QLabel("Listo.")
        self.feed_button.clicked.connect(self.publish_feed)
        layout.addWidget(self.feed_button)
        layout.addWidget(self.feed_status)
        layout.addStretch()
        return tab

    def _vault_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionVault")
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Sunna / Chloe — Bóveda y juego."))
        row = QHBoxLayout()
        self.vault_button = QPushButton("Consultar Estado de Bóveda")
        self.trivia_button = QPushButton("Iniciar Trivia")
        row.addWidget(self.vault_button)
        row.addWidget(self.trivia_button)
        layout.addLayout(row)
        self.vault_status = QLabel("Listo.")
        self.trivia_status = QLabel("Listo.")
        layout.addWidget(self.vault_status)
        layout.addWidget(self.trivia_status)
        self.vault_button.clicked.connect(self.check_vault)
        self.trivia_button.clicked.connect(self.start_trivia)
        layout.addStretch()
        return tab

    def _bootstrap_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("SectionOrders")
        layout = QVBoxLayout(tab)
        box = QGroupBox("Cami / Cari")
        form = QFormLayout(box)
        self.chat_id = QLineEdit()
        self.chat_id.setPlaceholderText("-1001234567890")
        self.bootstrap_button = QPushButton("Iniciar Auto-Bootstrap")
        self.bootstrap_button.setStyleSheet(
            "QPushButton { background:#c62828; color:white; font-weight:bold; padding:8px; }"
            "QPushButton:disabled { background:#777; }"
        )
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.bootstrap_status = QLabel("Listo.")
        form.addRow("chat_id:", self.chat_id)
        form.addRow(self.bootstrap_button)
        form.addRow("Progreso:", self.progress)
        form.addRow("Estado:", self.bootstrap_status)
        layout.addWidget(box)
        self.bootstrap_button.clicked.connect(self.start_bootstrap)
        layout.addStretch()
        return tab

    def _apply_section_theme(self, index: int) -> None:
        """Apply the visual identity of the active control-center section."""
        themes = {
            0: ("#1e1e2e", "#313244", "#89b4fa"),
            1: ("#17202a", "#25364a", "#89b4fa"),
            2: ("#1f2028", "#34353f", "#a6e3a1"),
            3: ("#10202a", "#1f3440", "#89dceb"),
            4: ("#1e1e2e", "#313244", "#cba6f7"),
            5: ("#1e1e2e", "#313244", "#f9e2af"),
            6: ("#2d5a27", "#4a3525", "#a6d189"),
            7: ("#1e1e2e", "#313244", "#74c7ec"),
            8: ("#1e1e2e", "#313244", "#f5c2e7"),
        }
        base, panel, accent = themes.get(index, ("#1e1e2e", "#313244", "#89b4fa"))
        page = self.actions.widget(index)
        if page is None:
            return

        image_path = os.getenv("COMMAND_CENTER_ANIMALS_CITY_BG", "").strip()
        if index == 6 and image_path and os.path.isfile(image_path):
            safe_path = image_path.replace(chr(92), "/").replace('"', '\\"')
            page.setStyleSheet(
                f'QWidget#SectionAnimalsCity {{ background-color:{base}; '
                f'background-image:url("{safe_path}"); background-repeat:repeat; '
                f'background-position:top left; }}'
            )
        elif index == 6:
            page.setStyleSheet(
                "QWidget#SectionAnimalsCity {"
                f"background-color:{base};"
                "background-image:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {base},stop:0.52 {panel},stop:1 {base});"
                "}"
            )
        else:
            page.setStyleSheet(f"QWidget#{page.objectName()} {{ background-color:{base}; }}")

        page.setProperty("themeAccent", accent)
        page.style().unpolish(page)
        page.style().polish(page)
        page.update()
        self.presence_status.setText(f"Sección activa: {self.actions.tabText(index)}")

    def _start_worker(self, worker: QObject, success_signal: str, callback, failure_callback) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        getattr(worker, success_signal).connect(callback, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(failure_callback, Qt.ConnectionType.QueuedConnection)
        getattr(worker, success_signal).connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        thread.start()

    def _command_center(self) -> tuple[str, str]:
        return (
            os.getenv("COMMAND_CENTER_API_URL", "http://127.0.0.1:8770").rstrip("/"),
            os.getenv("COMMAND_CENTER_TOKEN", ""),
        )

    def save_and_verify_credentials(self) -> None:
        credentials: dict[str, str] = {}
        for identity, field in self.token_inputs.items():
            token = (
                field.text().strip()
                or _secure_get(identity)
                or os.getenv(f"BOT_TOKEN_{identity.upper()}", "")
            )
            if not token:
                self.credentials_status.setText(f"Falta el token de {identity.title()}.")
                return
            credentials[identity] = token
        self.credentials_button.setEnabled(False)
        self.credentials_status.setText("Verificando los 6 tokens contra Telegram…")
        self._start_worker(
            CredentialVerificationWorker(credentials),
            "finished",
            self.credentials_done,
            self.credentials_failed,
        )

    @Slot(dict)
    def credentials_done(self, payload: dict) -> None:
        self.credentials_button.setEnabled(True)
        for identity in payload.get("verified", []):
            self.bot_status[identity].setText(f"{identity.title()}: ONLINE")
            self.bot_status[identity].setStyleSheet("color:#69f0ae; font-weight:bold;")
        self._refresh_presence()
        self.credentials_status.setText(
            "Credenciales verificadas y guardadas en el almacén seguro del sistema."
        )

    @Slot(str)
    def credentials_failed(self, message: str) -> None:
        self.credentials_button.setEnabled(True)
        self.credentials_status.setText(message)

    def _token_for(self, identity: str) -> str:
        return (
            _secure_get(identity)
            or os.getenv(f"BOT_TOKEN_{identity.upper()}", "")
        )

    def run_configured_action(self, identity: str, env_name: str) -> None:
        module = "feed" if identity == "scarlet" else "gacha"
        if not self._bot_enabled(identity):
            self.action_status.setText(f"{identity.title()} está en STANDBY.")
            return
        if not self._bot_permission(identity, module):
            self.action_status.setText(f"Permiso {module.title()} deshabilitado para {identity.title()}.")
            return
        try:
            chat_id = int(self.chat_id.text().strip())
            if chat_id == 0:
                raise ValueError
        except ValueError:
            self.action_status.setText(
                "Introduce primero un Chat ID / Supergroup ID válido en Auto-Bootstrap."
            )
            return
        command = os.getenv(env_name, "").strip()
        token = self._token_for(identity)
        if not command:
            self.action_status.setText(
                f"Configura {env_name} con el comando/evento soportado por tu runtime."
            )
            return
        if not token:
            self.action_status.setText(f"No hay credencial disponible para {identity.title()}.")
            return
        self._set_bot_state(identity, True, f"Acción manual: {env_name}")
        self.action_status.setText(f"Ejecutando acción de {identity.title()}…")
        worker = HttpActionWorker(
            "POST",
            f"https://api.telegram.org/bot{token}/sendMessage",
            payload={"chat_id": chat_id, "text": command},
        )
        self._start_worker(worker, "finished", self.action_done, self.action_failed)

    @Slot(dict)
    def action_done(self, payload: dict) -> None:
        self.action_status.setText("Acción enviada correctamente a Telegram.")

    @Slot(str)
    def action_failed(self, message: str) -> None:
        self.action_status.setText(message)

    def publish_feed(self) -> None:
        base, token = self._command_center()
        raw = os.getenv("COMMAND_CENTER_FEED_PAYLOAD_JSON", "")
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            self.feed_status.setText(
                "Configura COMMAND_CENTER_FEED_PAYLOAD_JSON con el evento del feed."
            )
            return
        self.feed_button.setEnabled(False)
        self.feed_status.setText("Publicando webhook de feed…")
        worker = HttpActionWorker(
            "POST",
            f"{base}{os.getenv('COMMAND_CENTER_FEED_WEBHOOK_PATH', '/api/v1/notifications/webhook')}",
            token,
            payload,
        )
        self._start_worker(worker, "finished", self.feed_done, self.feed_failed)

    @Slot(dict)
    def feed_done(self, payload: dict) -> None:
        self.feed_button.setEnabled(True)
        self.feed_status.setText(f"Feed enviado: {payload.get('status', 'ok')}.")
        self.refresh_events()

    @Slot(str)
    def feed_failed(self, message: str) -> None:
        self.feed_button.setEnabled(True)
        self.feed_status.setText(message)

    def check_vault(self) -> None:
        self.vault_button.setEnabled(False)
        self.vault_status.setText("Consultando Bóveda…")
        url = os.getenv("VAULT_API_URL", "http://127.0.0.1:8765").rstrip("/") + "/healthz"
        worker = HttpActionWorker("GET", url, os.getenv("VAULT_API_TOKEN", ""))
        self._start_worker(worker, "finished", self.vault_done, self.vault_failed)

    @Slot(dict)
    def vault_done(self, payload: dict) -> None:
        self.vault_button.setEnabled(True)
        self.vault_status.setText(
            f"Bóveda: {payload.get('status', 'desconocido')} ({payload.get('service', 'card-vault')})."
        )

    @Slot(str)
    def vault_failed(self, message: str) -> None:
        self.vault_button.setEnabled(True)
        self.vault_status.setText(message)

    def start_trivia(self) -> None:
        if not self._bot_enabled("sunna"):
            self.trivia_status.setText("Sunna está en STANDBY.")
            return
        if not self._bot_permission("sunna", "trivia"):
            self.trivia_status.setText("Permiso Trivia deshabilitado para Sunna.")
            return
        try:
            chat_id = int(self.chat_id.text().strip())
            if chat_id == 0:
                raise ValueError
        except ValueError:
            self.trivia_status.setText("Para Trivia, introduce un chat_id válido en Auto-Bootstrap.")
            return
        token = os.getenv("BOT_TOKEN_SUNNA", "")
        if not token:
            self.trivia_status.setText("BOT_TOKEN_SUNNA no está configurado.")
            return
        url = "https://api.telegram.org/bot" + token + "/sendMessage"
        self.trivia_button.setEnabled(False)
        self.trivia_status.setText("Iniciando /trivia con Sunna…")
        worker = HttpActionWorker(
            "POST",
            url,
            payload={"chat_id": chat_id, "text": "/trivia"},
        )
        self._start_worker(worker, "finished", self.trivia_done, self.trivia_failed)

    @Slot(dict)
    def trivia_done(self, payload: dict) -> None:
        self.trivia_button.setEnabled(True)
        self.trivia_status.setText("Trivia iniciada mediante el comando /trivia.")

    @Slot(str)
    def trivia_failed(self, message: str) -> None:
        self.trivia_button.setEnabled(True)
        self.trivia_status.setText(message)

    def start_bootstrap(self) -> None:
        try:
            chat_id = int(self.chat_id.text().strip())
            if chat_id == 0:
                raise ValueError
        except ValueError:
            self.bootstrap_status.setText("chat_id inválido.")
            return
        self.settings.setValue("bootstrap/chat_id", str(chat_id))
        self._refresh_presence()
        base, token = self._command_center()
        self.bootstrap_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.bootstrap_status.setText("Ejecutando bootstrap en Telegram…")
        worker = BootstrapWorker(base, token, chat_id)
        self._start_worker(worker, "finished", self.bootstrap_done, self.bootstrap_failed)

    @Slot(dict)
    def bootstrap_done(self, payload: dict) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.bootstrap_button.setEnabled(True)
        state = "reconciliado" if payload.get("reconciled") else "creado"
        self.bootstrap_status.setText(
            f"Bootstrap {state}: {len(payload.get('topics', []))} tópicos."
        )
        self.refresh_events()

    @Slot(str)
    def bootstrap_failed(self, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.bootstrap_button.setEnabled(True)
        self.bootstrap_status.setText(message)

    def refresh_events(self) -> None:
        worker = EventLogWorker(
            os.getenv("COMMAND_CENTER_DB_PATH", "data/command_center_events.db")
        )
        self._start_worker(worker, "refreshed", self.populate_events, self.logs_failed)

    def logs_failed(self, message: str) -> None:
        self.bootstrap_status.setText(message)

    @Slot(list)
    def populate_events(self, rows: list) -> None:
        self.logs.setRowCount(0)
        for row_data in rows:
            row = self.logs.rowCount()
            self.logs.insertRow(row)
            values = (
                row_data.get("event_id", ""),
                row_data.get("event_type", ""),
                row_data.get("bot_name", ""),
                row_data.get("status", ""),
                f"{row_data.get('retry_count', 0)}/{row_data.get('max_retries', 0)}",
                row_data.get("max_retries", 0),
                row_data.get("last_error") or "",
            )
            for col, value in enumerate(values):
                self.logs.setItem(row, col, QTableWidgetItem(str(value)))

    def closeEvent(self, event) -> None:
        for thread in list(self._threads):
            thread.quit()
            thread.wait(1000)
        super().closeEvent(event)


def _apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QWidget { background:#1e1e2e; color:#cdd6f4; font-size:13px; }
        QMainWindow { background:#1e1e2e; }
        QGroupBox { background:#1e1e2e; border:1px solid #45475a; border-radius:10px; margin-top:10px; padding:10px; }
        QGroupBox#BotCard { background:#313244; border:1px solid #45475a; border-radius:12px; }
        QLabel#BotStatus { background:#313244; border-radius:7px; padding:5px 8px; font-weight:bold; }
        QLineEdit, QTableWidget { background:#313244; color:#cdd6f4; border:1px solid #585b70; border-radius:7px; padding:6px; }
        QPushButton { background:#313244; color:#cdd6f4; border:1px solid #585b70; border-radius:8px; padding:8px 12px; }
        QPushButton:hover { background:#45475a; border-color:#89b4fa; }
        QPushButton:pressed { background:#585b70; }
        QPushButton:disabled { background:#262637; color:#6c7086; border-color:#45475a; }
        QPushButton#EmergencyButton { background:#b42318; color:white; border:2px solid #f38ba8; font-weight:bold; padding:10px; }
        QPushButton#EmergencyButton:hover { background:#dc2626; }
        QPushButton#EmergencyButton:pressed { background:#7f1d1d; }
        QTabWidget#SectionTabs::pane { border:1px solid #45475a; border-radius:10px; padding:2px; }
        QTabBar::tab { background:#313244; color:#bac2de; padding:10px 15px; border:1px solid #45475a; border-bottom:0; border-top-left-radius:8px; border-top-right-radius:8px; }
        QTabBar::tab:hover { background:#45475a; color:#ffffff; }
        QTabBar::tab:selected { background:#45475a; color:#ffffff; border-color:#89b4fa; font-weight:bold; }
        QCheckBox { spacing:7px; }
        QCheckBox::indicator { width:16px; height:16px; }
        QHeaderView::section { background:#313244; color:#cdd6f4; padding:7px; border:0; }
        QProgressBar { background:#313244; color:#cdd6f4; border:1px solid #585b70; border-radius:7px; text-align:center; }
        QProgressBar::chunk { background:#89b4fa; border-radius:6px; }
        QWidget#SectionAnimalsCity QGroupBox { background:#4a3525; border:1px solid #6f563e; }
        QWidget#SectionLLM QGroupBox { background:#1f3440; border:1px solid #365c6d; }
        QWidget#SectionLobby QGroupBox, QWidget#SectionLobby QTextBrowser { background:#17202a; border-color:#334e68; }
        QWidget#SectionWorker QGroupBox, QWidget#SectionWorker QTextEdit { background:#1f2028; border-color:#4b5563; }
        QWidget#SectionAnimalsCity QLabel { color:#f0ead8; }
        QWidget#SectionAnimalsCity QPushButton { background:#4a3525; border-color:#789461; }
        QWidget#SectionAnimalsCity QPushButton:hover { background:#5d442f; border-color:#a6d189; }
    """)

def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    _apply_dark_theme(app)
    window = CommandCenterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
