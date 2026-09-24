# -*- coding: utf-8 -*-
"""Puente visual Dark Cozy para señales del motor de Café Otaku."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .styles import application_qss


CATPPUCCIN_MOCHA_QSS = """
QMainWindow, QWidget {
    background-color: #11111b;
    color: #cdd6f4;
}
QFrame#BridgeSidebar {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 12px;
}
QFrame#WaitressCard {
    background-color: #1e1e2e;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 8px;
}
QFrame#WaitressCard:hover {
    background-color: #2a2a3d;
}
QLabel#BridgeTitle {
    color: #cba6f7;
    font-size: 13px;
    font-weight: 700;
}
QLabel#WaitressName {
    color: #cdd6f4;
    font-weight: 700;
}
QLabel#WaitressRole {
    color: #a6adc8;
    font-size: 10px;
}
QLabel#WaitressStatus[state="online"] { color: #a6e3a1; }
QLabel#WaitressStatus[state="processing"] { color: #f9e2af; }
QLabel#WaitressStatus[state="fallback"] { color: #fab387; }
QLabel#WaitressStatus[state="offline"] { color: #f38ba8; }
QLabel#BridgeLog {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 15px;
}
QPushButton#BridgeAction {
    background-color: #313244;
    color: #f5e0dc;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 10px 13px;
}
QPushButton#BridgeAction:hover { background-color: #45475a; }
"""


WAITRESS_PROFILES = (
    ("cari", "Cari", "Anfitriona", "🦫✨"),
    ("cami", "Cami", "Moderación", "🦫👓"),
    ("sunna", "Sunna", "Lore & Trivia", "🐍⚪"),
    ("chie", "Chie", "Gestor XP", "🐭"),
    ("chloe", "Chloe", "Bóveda", "🦇"),
    ("scarlet", "Scarlet", "Publicista", "🧛‍♀️"),
)


class WorkerSignals(QObject):
    status_changed = Signal(str, str)
    message_received = Signal(str, str)


class WaitressCard(QFrame):
    def __init__(
        self,
        waitress_id: str,
        name: str,
        role: str,
        avatar_icon: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.waitress_id = waitress_id
        self.setObjectName("WaitressCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(9)

        self.lbl_avatar = QLabel(avatar_icon)
        self.lbl_avatar.setStyleSheet("font-size: 20px;")
        self.lbl_avatar.setFixedWidth(34)
        self.lbl_avatar.setAlignment(Qt.AlignCenter)

        info = QVBoxLayout()
        info.setSpacing(1)

        self.lbl_name = QLabel(name)
        self.lbl_name.setObjectName("WaitressName")
        self.lbl_role = QLabel(role)
        self.lbl_role.setObjectName("WaitressRole")
        self.lbl_status = QLabel("Online")
        self.lbl_status.setObjectName("WaitressStatus")
        self._apply_status_style("Online")

        info.addWidget(self.lbl_name)
        info.addWidget(self.lbl_role)
        info.addWidget(self.lbl_status)
        layout.addWidget(self.lbl_avatar)
        layout.addLayout(info, 1)

    @Slot(str)
    def update_status(self, status: str) -> None:
        self.lbl_status.setText(status)
        self._apply_status_style(status)

    def _apply_status_style(self, status: str) -> None:
        normalized = status.casefold()
        if "online" in normalized:
            state = "online"
        elif "procesando" in normalized:
            state = "processing"
        elif "fallback" in normalized or "reintentando" in normalized:
            state = "fallback"
        else:
            state = "offline"

        self.lbl_status.setProperty("state", state)
        style = self.lbl_status.style()
        if style is not None:
            style.unpolish(self.lbl_status)
            style.polish(self.lbl_status)


class DarkCozyWindow(QMainWindow):
    """Puente visual sin runtime propio ni segunda entrada de aplicación."""

    def __init__(
        self,
        signals: WorkerSignals,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(signals, WorkerSignals):
            raise TypeError("signals debe ser una instancia de WorkerSignals")

        self.signals = signals
        self.cards: dict[str, WaitressCard] = {}
        self._message_count = 0

        self.setWindowTitle("Taberna Control Panel · Dark Cozy")
        self.resize(900, 600)
        self.setMinimumSize(760, 500)
        self.setStyleSheet(application_qss() + CATPPUCCIN_MOCHA_QSS)

        root = QWidget()
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        sidebar = QFrame()
        sidebar.setObjectName("BridgeSidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("PERSONAJES DE TABERNA")
        title.setObjectName("BridgeTitle")
        sidebar_layout.addWidget(title)

        subtitle = QLabel("Estado publicado por el motor asíncrono.")
        subtitle.setStyleSheet("color: #a6adc8; font-size: 10px;")
        subtitle.setWordWrap(True)
        sidebar_layout.addWidget(subtitle)

        for profile in WAITRESS_PROFILES:
            card = WaitressCard(*profile)
            self.cards[card.waitress_id] = card
            sidebar_layout.addWidget(card)
        sidebar_layout.addStretch(1)

        content = QFrame()
        content.setObjectName("BridgeSidebar")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)

        actions = QHBoxLayout()
        self.btn_chocolatada = QPushButton("🍫 Pedir Chocolatada")
        self.btn_chocolatada.setObjectName("BridgeAction")
        self.btn_trivia = QPushButton("🎲 Trivia Rápida")
        self.btn_trivia.setObjectName("BridgeAction")
        actions.addWidget(self.btn_chocolatada)
        actions.addWidget(self.btn_trivia)
        actions.addStretch(1)

        self.txt_logs = QLabel("Sistema iniciado correctamente en entorno local.")
        self.txt_logs.setObjectName("BridgeLog")
        self.txt_logs.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.txt_logs.setWordWrap(True)

        content_layout.addLayout(actions)
        content_layout.addWidget(self.txt_logs, 1)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.signals.status_changed.connect(self.on_status_changed)
        self.signals.message_received.connect(self.on_message_received)

        self.btn_chocolatada.clicked.connect(
            lambda: self._emit_local_message("cafe", "Pedir Chocolatada")
        )
        self.btn_trivia.clicked.connect(
            lambda: self._emit_local_message("trivia", "Trivia Rápida")
        )

    @Slot(str, str)
    def on_status_changed(self, waitress_id: str, status: str) -> None:
        card = self.cards.get(waitress_id)
        if card is not None:
            card.update_status(status)

    @Slot(str, str)
    def on_message_received(self, waitress_id: str, message: str) -> None:
        self._message_count += 1
        source = waitress_id.strip() or "sistema"
        text = message.strip() or "(mensaje vacío)"
        self.txt_logs.setText(f"[{self._message_count}] {source}: {text}")

    def _emit_local_message(self, action_id: str, label: str) -> None:
        self.signals.message_received.emit(
            action_id,
            f"Acción solicitada: {label}",
        )
