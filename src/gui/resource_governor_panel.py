# -*- coding: utf-8 -*-
"""Interactive bot command centre and rotary resource-budget control."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QDial,
    QVBoxLayout,
    QWidget,
)

from bot_ia.resource_governor import (
    BUDGET_STEP_BYTES,
    MAX_BUDGET_BYTES,
    MIN_BUDGET_BYTES,
    GovernorSnapshot,
    PressureLevel,
    ResourceGovernor,
    TaskPriority,
)


PROFILE_DESCRIPTIONS = {
    "cari": "Anfitriona · bienvenida y coordinación del lobby",
    "cami": "Moderación · orden, seguridad y coordinación",
    "sunna": "Lore y trivia · continuidad y precisión contextual",
    "chie": "Progreso · XP, recompensas y actividad",
    "chloe": "Perfil de personaje · murciélago",
    "scarlet": "Perfil de personaje · vampiresa",
}

BOT_ACTION_POLICY = {
    "select": TaskPriority.P1_CRITICAL,
    "chat": TaskPriority.P2_ORDINARY,
    "expand": TaskPriority.P2_ORDINARY,
    "matrix": TaskPriority.P4_BACKGROUND,
    "games": TaskPriority.P3_GAMES,
    "waifu": TaskPriority.P2_ORDINARY,
    "order": TaskPriority.P2_ORDINARY,
    "moderation": TaskPriority.P0_MODERATION,
}


class ResourceGovernorPanel(QWidget):
    """One-screen bot dashboard with a rotary budget control and live task admission."""

    def __init__(
        self,
        governor: ResourceGovernor,
        parent: QWidget | None = None,
        *,
        profiles: tuple[Any, ...] | list[Any] = (),
        matrix_bot_ids: tuple[str, ...] | list[str] = (),
    ) -> None:
        super().__init__(parent)
        self.governor = governor
        self.window_ref = parent
        self.profiles = tuple(profiles)
        self.matrix_bot_ids = frozenset(matrix_bot_ids)
        self.bot_cards: dict[str, dict[str, Any]] = {}
        self.setObjectName("ResourceGovernorPanel")
        self.setMinimumWidth(960)
        self.setStyleSheet("""
            QFrame#ResourceDashboardCard {
                background-color: #132238;
                border: 1px solid #294761;
                border-radius: 12px;
            }
            QFrame#ResourceBotCard {
                background-color: #17283d;
                border: 1px solid #2b4a64;
                border-radius: 11px;
            }
            QFrame#ResourceBotCard[botTier="moderation"] {
                border: 1px solid #28b89a;
            }
            QFrame#ResourceBotCard[botTier="matrix"] {
                border: 1px solid #377cac;
            }
            QFrame#MemoryDialCard {
                background-color: #10253b;
                border: 1px solid #2681a7;
                border-radius: 14px;
            }
            QLabel#ResourceStatus {
                color: #e9f4ff;
                font-weight: 700;
                padding: 5px 8px;
                border-radius: 6px;
                background-color: #203c54;
            }
            QPushButton#ResourcePrimaryAction {
                background-color: #145b73;
                border: 1px solid #2b91b5;
                border-radius: 7px;
                padding: 7px;
                font-weight: 600;
            }
            QPushButton#ResourcePrimaryAction:disabled {
                color: #7a8996;
                background-color: #263441;
                border-color: #3b4954;
            }
            QPushButton#ResourceSecondaryAction {
                background-color: #213449;
                border: 1px solid #3b5a73;
                border-radius: 7px;
                padding: 6px;
            }
            QPushButton#ResourceSecondaryAction:disabled {
                color: #7a8996;
                background-color: #263441;
                border-color: #3b4954;
            }
            QDial {
                background-color: #0a1b2e;
            }
            QGroupBox {
                border: 1px solid #2c4a61;
                border-radius: 9px;
                margin-top: 10px;
                padding-top: 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("CENTRO DE CONTROL DE BOTS")
        title.setObjectName("PageTitle")
        heading.addWidget(title)
        subtitle = QLabel(
            "Acciones disponibles por perfil y presupuesto global de memoria. "
            "Las acciones se habilitan o pausan según la política actual."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("Muted")
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)

        self.profile_count_label = QLabel(
            f"{len(self.profiles)} PERFILES · {len(self.matrix_bot_ids)} EN MATRIZ"
        )
        self.profile_count_label.setObjectName("ResourceStatus")
        header.addWidget(self.profile_count_label, 0, Qt.AlignTop)
        root.addLayout(header)

        workspace = QHBoxLayout()
        workspace.setSpacing(10)

        bot_area = QWidget()
        bot_area.setObjectName("BotCardsArea")
        self.bot_grid = QGridLayout(bot_area)
        self.bot_grid.setContentsMargins(0, 0, 0, 0)
        self.bot_grid.setSpacing(9)
        self.bot_grid.setColumnStretch(0, 1)
        self.bot_grid.setColumnStretch(1, 1)
        self.bot_grid.setColumnStretch(2, 1)
        for index, profile in enumerate(self.profiles):
            card = self._build_bot_card(profile)
            self.bot_grid.addWidget(card["frame"], index // 3, index % 3)
            self.bot_cards[profile.bot_id] = card

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(bot_area)
        workspace.addWidget(scroll, 1)

        memory_card = QFrame()
        memory_card.setObjectName("MemoryDialCard")
        memory_card.setMinimumWidth(300)
        memory_card.setMaximumWidth(345)
        memory_layout = QVBoxLayout(memory_card)
        memory_layout.setContentsMargins(14, 14, 14, 14)
        memory_layout.setSpacing(8)

        memory_title = QLabel("CONTROL DE MEMORIA")
        memory_title.setObjectName("PageTitle")
        memory_title.setAlignment(Qt.AlignCenter)
        memory_layout.addWidget(memory_title)

        self.memory_dial = QDial()
        self.memory_dial.setObjectName("MemoryBudgetDial")
        self.memory_dial.setRange(
            0, (MAX_BUDGET_BYTES - MIN_BUDGET_BYTES) // BUDGET_STEP_BYTES
        )
        self.memory_dial.setSingleStep(1)
        self.memory_dial.setPageStep(1)
        self.memory_dial.setNotchesVisible(True)
        self.memory_dial.setWrapping(False)
        self.memory_dial.setTracking(True)
        self.memory_dial.setFixedSize(205, 205)
        self.memory_dial.setToolTip(
            "Gira el mando para cambiar el presupuesto operativo de 1,00 a 2,00 GB."
        )
        self.memory_dial.setValue(
            (governor.budget_bytes - MIN_BUDGET_BYTES) // BUDGET_STEP_BYTES
        )
        dial_row = QHBoxLayout()
        dial_row.addStretch(1)
        dial_row.addWidget(self.memory_dial)
        dial_row.addStretch(1)
        memory_layout.addLayout(dial_row)

        endpoints = QHBoxLayout()
        endpoints.addWidget(QLabel("1,00 GB"))
        endpoints.addStretch(1)
        endpoints.addWidget(QLabel("2,00 GB"))
        memory_layout.addLayout(endpoints)

        self.budget_value = QLabel()
        self.budget_value.setObjectName("PageTitle")
        self.budget_value.setAlignment(Qt.AlignCenter)
        memory_layout.addWidget(self.budget_value)

        self.status_value = QLabel("PRESUPUESTO NO VERIFICADO")
        self.status_value.setObjectName("ResourceStatus")
        self.status_value.setWordWrap(True)
        self.status_value.setAlignment(Qt.AlignCenter)
        memory_layout.addWidget(self.status_value)

        self.profile_value = QLabel()
        self.profile_value.setWordWrap(True)
        self.profile_value.setAlignment(Qt.AlignCenter)
        memory_layout.addWidget(self.profile_value)

        metrics_box = QGroupBox("Medición del árbol de procesos")
        metrics = QFormLayout(metrics_box)
        self.memory_value = QLabel("NO DISPONIBLE")
        self.private_value = QLabel("NO DISPONIBLE")
        self.peak_value = QLabel("NO DISPONIBLE")
        self.process_value = QLabel("NO DISPONIBLE")
        for label in (
            self.memory_value,
            self.private_value,
            self.peak_value,
            self.process_value,
        ):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        metrics.addRow("Working set", self.memory_value)
        metrics.addRow("Commit privado", self.private_value)
        metrics.addRow("Pico observado", self.peak_value)
        metrics.addRow("Procesos incluidos", self.process_value)
        memory_layout.addWidget(metrics_box)

        self.paused_value = QLabel()
        self.paused_value.setWordWrap(True)
        memory_layout.addWidget(self.paused_value)

        presets = QGroupBox("Perfiles rápidos")
        preset_grid = QGridLayout(presets)
        self.safe_button = QPushButton("🛡 Moderación\n1,00 GB")
        self.controlled_button = QPushButton("⚖ Trabajo\n1,50 GB")
        self.max_button = QPushButton("⚡ Máximo\n2,00 GB")
        for button in (
            self.safe_button,
            self.controlled_button,
            self.max_button,
        ):
            button.setObjectName("ResourceSecondaryAction")
            button.setMinimumHeight(48)
        preset_grid.addWidget(self.safe_button, 0, 0)
        preset_grid.addWidget(self.controlled_button, 0, 1)
        preset_grid.addWidget(self.max_button, 1, 0, 1, 2)
        memory_layout.addWidget(presets)
        memory_layout.addStretch(1)

        workspace.addWidget(memory_card)
        root.addLayout(workspace, 1)

        global_actions = QFrame()
        global_actions.setObjectName("ResourceDashboardCard")
        action_layout = QHBoxLayout(global_actions)
        action_layout.setContentsMargins(10, 9, 10, 9)
        action_layout.setSpacing(8)
        global_title = QLabel("ACCIONES GLOBALES")
        global_title.setObjectName("PageTitle")
        action_layout.addWidget(global_title)
        action_layout.addStretch(1)

        self.moderation_button = QPushButton("🛡 Panel de moderación")
        self.moderation_button.setObjectName("ResourcePrimaryAction")
        self.moderation_button.setToolTip(
            "Abre el panel existente de incidencias; no activa servicios nuevos."
        )
        action_layout.addWidget(self.moderation_button)

        self.refresh_button = QPushButton("↻ Actualizar medición")
        self.refresh_button.setObjectName("ResourceSecondaryAction")
        action_layout.addWidget(self.refresh_button)

        self.measurement_note = QLabel(
            "La suma de working sets puede contar páginas compartidas más de una vez. "
            "El mando regula admisión de tareas; no aplica un límite duro de Windows."
        )
        self.measurement_note.setWordWrap(True)
        self.measurement_note.setObjectName("Muted")
        root.addWidget(global_actions)
        root.addWidget(self.measurement_note)

        self.gate_value = QLabel(
            "MODO LIMITADO POR GATE · Body Health sigue BLOCKED. "
            "No se activa Discord ni se alteran QWebEngine, TaskEngine, "
            "TaskScheduler, WebQueue o la autoridad física de WebChat."
        )
        self.gate_value.setWordWrap(True)
        self.gate_value.setObjectName("Muted")
        root.addWidget(self.gate_value)

        self.memory_dial.valueChanged.connect(self._on_dial_changed)
        self.safe_button.clicked.connect(lambda: self._set_budget(MIN_BUDGET_BYTES))
        self.controlled_button.clicked.connect(lambda: self._set_budget(1_500_000_000))
        self.max_button.clicked.connect(lambda: self._set_budget(MAX_BUDGET_BYTES))
        self.moderation_button.clicked.connect(self._open_moderation)
        self.refresh_button.clicked.connect(self.refresh_sample)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_sample)
        self.refresh_sample()
        self.timer.start()

    @staticmethod
    def _format_gb(value: int | None) -> str:
        if value is None:
            return "NO DISPONIBLE"
        return f"{value / 1_000_000_000:.2f} GB".replace(".", ",")

    def _build_bot_card(self, profile: Any) -> dict[str, Any]:
        bot_id = profile.bot_id
        in_matrix = bot_id in self.matrix_bot_ids
        tier = "moderation" if bot_id == "cami" else "matrix" if in_matrix else "profile"

        frame = QFrame()
        frame.setObjectName("ResourceBotCard")
        frame.setProperty("botTier", tier)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        heading = QHBoxLayout()
        avatar = QLabel(profile.avatar)
        avatar.setStyleSheet("font-size: 24px;")
        heading.addWidget(avatar)
        name_column = QVBoxLayout()
        name = QLabel(profile.name)
        name.setObjectName("PageTitle")
        role = QLabel(PROFILE_DESCRIPTIONS.get(bot_id, profile.short_role))
        role.setWordWrap(True)
        role.setObjectName("Muted")
        name_column.addWidget(name)
        name_column.addWidget(role)
        heading.addLayout(name_column, 1)
        priority = QLabel(
            "P0/P1" if bot_id == "cami" else "MATRIZ" if in_matrix else "PERFIL"
        )
        priority.setObjectName("ResourceStatus")
        heading.addWidget(priority, 0, Qt.AlignTop)
        layout.addLayout(heading)

        action_state = QLabel()
        action_state.setWordWrap(True)
        action_state.setObjectName("Muted")
        layout.addWidget(action_state)

        primary_row = QHBoxLayout()
        select = QPushButton("Seleccionar")
        select.setObjectName("ResourcePrimaryAction")
        chat = QPushButton("☕ Charla")
        chat.setObjectName("ResourceSecondaryAction")
        primary_row.addWidget(select, 1)
        primary_row.addWidget(chat, 1)
        layout.addLayout(primary_row)

        secondary_row = QHBoxLayout()
        rest = QPushButton("💤 Descanso")
        rest.setObjectName("ResourceSecondaryAction")
        detail = QPushButton("Abrir ficha")
        detail.setObjectName("ResourceSecondaryAction")
        secondary_row.addWidget(rest, 1)
        if in_matrix:
            secondary_row.addWidget(detail, 1)
        layout.addLayout(secondary_row)

        extra_row = QHBoxLayout()
        extra: dict[str, QPushButton] = {}
        if bot_id in self.matrix_bot_ids:
            matrix = QPushButton("▶ Iniciar desde aquí")
            matrix.setObjectName("ResourceSecondaryAction")
            matrix.setToolTip(
                "Usa el texto preparado en el Lobby y respeta la secuencia autorizada."
            )
            extra["matrix"] = matrix
            extra_row.addWidget(matrix, 1)
        if bot_id == "cami":
            moderation = QPushButton("🛡 Moderación")
            moderation.setObjectName("ResourceSecondaryAction")
            extra["moderation"] = moderation
            extra_row.addWidget(moderation, 1)
        elif bot_id == "chie":
            games = QPushButton("🎮 Juegos")
            games.setObjectName("ResourceSecondaryAction")
            extra["games"] = games
            extra_row.addWidget(games, 1)
        elif bot_id == "cari":
            waifu = QPushButton("🎴 Waifus / TCG")
            waifu.setObjectName("ResourceSecondaryAction")
            extra["waifu"] = waifu
            extra_row.addWidget(waifu, 1)
        elif bot_id in {"chloe", "scarlet"}:
            order = QPushButton("🥤 Nuevo pedido")
            order.setObjectName("ResourceSecondaryAction")
            extra["order"] = order
            extra_row.addWidget(order, 1)
        if extra:
            layout.addLayout(extra_row)

        select.clicked.connect(
            lambda _checked=False, selected_id=bot_id: self._select_bot(selected_id)
        )
        chat.clicked.connect(
            lambda _checked=False, selected_id=bot_id: self._start_chat(selected_id)
        )
        rest.clicked.connect(
            lambda _checked=False, selected_id=bot_id: self._force_rest(selected_id)
        )
        if in_matrix:
            detail.clicked.connect(
                lambda _checked=False, selected_id=bot_id: self._open_bot_detail(selected_id)
            )
            extra["matrix"].clicked.connect(
                lambda _checked=False, selected_id=bot_id: self._start_matrix_chain(selected_id)
            )
        if "moderation" in extra:
            extra["moderation"].clicked.connect(self._open_moderation)
        if "games" in extra:
            extra["games"].clicked.connect(self._open_games)
        if "waifu" in extra:
            extra["waifu"].clicked.connect(
                lambda _checked=False, selected_id=bot_id: self._open_waifu(selected_id)
            )
        if "order" in extra:
            extra["order"].clicked.connect(
                lambda _checked=False, selected_id=bot_id: self._open_order(selected_id)
            )

        return {
            "frame": frame,
            "action_state": action_state,
            "select": select,
            "chat": chat,
            "rest": rest,
            "detail": detail if in_matrix else None,
            "extra": extra,
            "bot_id": bot_id,
            "in_matrix": in_matrix,
        }

    def _report(self, message: str) -> None:
        window = self.window_ref
        append = getattr(window, "_append_system", None)
        if callable(append):
            append(message)

    def _select_bot(self, bot_id: str) -> None:
        select = getattr(self.window_ref, "select_bot", None)
        if callable(select):
            select(bot_id)
            self._report(f"Perfil seleccionado: {bot_id}. No se inició ningún servicio.")
        self.refresh_bot_actions()

    def _registered_bot_ids(self) -> set[str]:
        tavern = getattr(self.window_ref, "_tavern", None)
        if tavern is None:
            return set()
        try:
            return {
                str(item.waitress_id)
                for item in tavern.list_turns()
                if getattr(item, "waitress_id", None)
            }
        except (OSError, ValueError, TypeError, RuntimeError):
            return set()

    def _admit(self, priority: TaskPriority, label: str) -> bool:
        if self.governor.allows(priority):
            return True
        reason = self.governor.denial_reason(priority)
        self._report(f"⏸ {label}: {reason}. P0/P1 se conserva.")
        QMessageBox.information(self, "Acción pausada por memoria", reason)
        return False

    def _start_chat(self, bot_id: str) -> None:
        if not self._admit(TaskPriority.P2_ORDINARY, f"Charla con {bot_id}"):
            return
        window = self.window_ref
        select = getattr(window, "select_bot", None)
        start = getattr(window, "_start_selected_tavern_session", None)
        if callable(select):
            select(bot_id)
        if bot_id not in self._registered_bot_ids():
            self._report(
                f"{bot_id}: no consta registrado como mesera en la SQLite visible; "
                "no se inició una charla de Taberna."
            )
            QMessageBox.information(
                self,
                "Perfil no registrado",
                "Este perfil no aparece en el registro SQLite actual. "
                "No se ha iniciado una sesión. Puedes usar Seleccionar o Abrir ficha "
                "cuando el perfil admita la matriz web.",
            )
            return
        if callable(start):
            start()

    def _force_rest(self, bot_id: str) -> None:
        window = self.window_ref
        select = getattr(window, "select_bot", None)
        rest = getattr(window, "_force_selected_rest", None)
        if callable(select):
            select(bot_id)
        if bot_id not in self._registered_bot_ids():
            self._report(f"{bot_id}: descanso no aplicado; el perfil no está registrado en la Taberna SQLite.")
            QMessageBox.information(
                self,
                "Perfil no registrado",
                "Solo se puede forzar descanso en personajes registrados en la Taberna.",
            )
            return
        if callable(rest):
            rest()

    def _open_bot_detail(self, bot_id: str) -> None:
        if not self._admit(TaskPriority.P2_ORDINARY, f"Abrir ficha de {bot_id}"):
            return
        select = getattr(self.window_ref, "select_bot", None)
        show = getattr(self.window_ref, "_open_bot_expanded", None)
        if callable(select):
            select(bot_id)
        if callable(show):
            show(bot_id)

    def _start_matrix_chain(self, bot_id: str) -> None:
        if bot_id not in self.matrix_bot_ids:
            return
        if not self._admit(TaskPriority.P4_BACKGROUND, f"Cadena de matriz desde {bot_id}"):
            return
        select = getattr(self.window_ref, "select_bot", None)
        start = getattr(self.window_ref, "_start_matrix_chain", None)
        if callable(select):
            select(bot_id)
        if callable(start):
            start(bot_id)

    def _open_moderation(self) -> None:
        window = self.window_ref
        tabs = getattr(window, "main_tabs", None)
        panel = getattr(window, "incidents_panel", None)
        if tabs is not None and panel is not None:
            tabs.setCurrentWidget(panel)
        self._report("Panel existente de Incidencias & Moderación abierto; no se han activado servicios nuevos.")

    def _open_games(self) -> None:
        if not self._admit(TaskPriority.P3_GAMES, "Mini-juegos"):
            return
        select = getattr(self.window_ref, "select_bot", None)
        open_games = getattr(self.window_ref, "_open_mini_games", None)
        if callable(select):
            select("chie")
        if callable(open_games):
            open_games()

    def _open_waifu(self, bot_id: str) -> None:
        if not self._admit(TaskPriority.P2_ORDINARY, "Registro Waifus / TCG"):
            return
        select = getattr(self.window_ref, "select_bot", None)
        open_waifu = getattr(self.window_ref, "_open_waifu_registry", None)
        if callable(select):
            select(bot_id)
        if callable(open_waifu):
            open_waifu(bot_id)

    def _open_order(self, bot_id: str) -> None:
        if not self._admit(TaskPriority.P2_ORDINARY, "Nuevo pedido"):
            return
        select = getattr(self.window_ref, "select_bot", None)
        open_order = getattr(self.window_ref, "_open_bebida_order", None)
        if callable(select):
            select(bot_id)
        if callable(open_order):
            open_order()

    def _set_budget(self, value: int) -> None:
        self.governor.set_budget_bytes(value)
        self.refresh_sample()

    def _on_dial_changed(self, step: int) -> None:
        value = MIN_BUDGET_BYTES + int(step) * BUDGET_STEP_BYTES
        self._set_budget(value)

    def _sync_dial(self, budget_bytes: int) -> None:
        step = (budget_bytes - MIN_BUDGET_BYTES) // BUDGET_STEP_BYTES
        if self.memory_dial.value() != step:
            self.memory_dial.blockSignals(True)
            self.memory_dial.setValue(step)
            self.memory_dial.blockSignals(False)

    def refresh_sample(self) -> None:
        snapshot = self.governor.sample()
        self._render(snapshot)
        self.refresh_bot_actions()

    def refresh_bot_actions(self) -> None:
        window = self.window_ref
        registered = self._registered_bot_ids()
        tavern_available = getattr(window, "_tavern", None) is not None
        p2 = self.governor.allows(TaskPriority.P2_ORDINARY)
        p3 = self.governor.allows(TaskPriority.P3_GAMES)
        p4 = self.governor.allows(TaskPriority.P4_BACKGROUND)
        for bot_id, card in self.bot_cards.items():
            card["select"].setEnabled(True)
            card["chat"].setEnabled(p2 and tavern_available and bot_id in registered)
            card["chat"].setToolTip(
                "Inicia la charla si el personaje está registrado en SQLite y P2 está admitido."
                if card["chat"].isEnabled()
                else "Pausado por memoria, Taberna no disponible o perfil no registrado."
            )
            card["rest"].setEnabled(tavern_available and bot_id in registered)
            card["rest"].setToolTip(
                "Aplica el descanso persistido en SQLite."
                if card["rest"].isEnabled()
                else "Requiere que el personaje figure en el registro de la Taberna."
            )
            if card["detail"] is not None:
                card["detail"].setEnabled(p2)
                card["detail"].setToolTip("Abre el visor del perfil; las tareas que inicie siguen sujetas a gates.")
            extras = card["extra"]
            if "matrix" in extras:
                extras["matrix"].setEnabled(p4)
                extras["matrix"].setToolTip(
                    "Inicia trabajo P4 secuencial desde el Lobby; nunca eleva la concurrencia autorizada."
                )
            if "moderation" in extras:
                extras["moderation"].setEnabled(True)
            if "games" in extras:
                extras["games"].setEnabled(p3)
            if "waifu" in extras:
                extras["waifu"].setEnabled(p2)
            if "order" in extras:
                extras["order"].setEnabled(p2)

            if not p2:
                summary = "P2 pausado · selección y controles críticos siguen disponibles"
            elif "matrix" in extras and not p4:
                summary = "P4 en pausa · conversación ordinaria admitida"
            elif "games" in extras and not p3:
                summary = "P3 en pausa · funciones ordinarias admitidas"
            else:
                summary = "Acciones sujetas al presupuesto global"
            card["action_state"].setText(summary)

    def _render(self, snapshot: GovernorSnapshot) -> None:
        self._sync_dial(snapshot.budget_bytes)
        self.budget_value.setText(
            f"{self._format_gb(snapshot.budget_bytes)} · presupuesto seleccionado"
        )
        self.status_value.setText(snapshot.status_label)
        self.profile_value.setText(
            {
                1_000_000_000: "MODERACIÓN PRIORITARIA",
                1_250_000_000: "MODERACIÓN + FUNCIONES ESENCIALES",
                1_500_000_000: "TRABAJO CONTROLADO",
                1_750_000_000: "ACTIVIDAD AMPLIADA",
                2_000_000_000: "PRESUPUESTO MÁXIMO",
            }.get(snapshot.budget_bytes, "PERFIL SEGURO")
        )
        if snapshot.memory.valid:
            self.memory_value.setText(self._format_gb(snapshot.memory.working_set_bytes))
            self.private_value.setText(self._format_gb(snapshot.memory.private_commit_bytes))
            self.process_value.setText(
                str(snapshot.memory.process_count)
                if snapshot.memory.process_count is not None
                else "NO DISPONIBLE"
            )
            self.peak_value.setText(self._format_gb(snapshot.peak_working_set_bytes))
        else:
            reason = snapshot.memory.reason or "Sensor no válido."
            self.memory_value.setText("PRESUPUESTO NO VERIFICADO")
            self.private_value.setText("NO DISPONIBLE")
            self.process_value.setText("NO DISPONIBLE")
            self.peak_value.setText(self._format_gb(snapshot.peak_working_set_bytes))
            self.memory_value.setToolTip(reason)
        paused = ", ".join(snapshot.paused_categories) if snapshot.paused_categories else "Ninguna por presión medida"
        self.paused_value.setText(f"Orden de reducción: {paused}")
        if not snapshot.preference_saved:
            self.status_value.setToolTip("No se pudo persistir la preferencia local.")
        elif not snapshot.runtime_state_saved:
            self.status_value.setToolTip(
                "No se publicó la muestra actual; la política distribuida permanece cerrada para tareas secundarias."
            )
        else:
            self.status_value.setToolTip(
                "Presupuesto seleccionado y medición real son valores distintos. "
                "No es un límite duro del sistema operativo."
            )
        if snapshot.pressure is PressureLevel.UNKNOWN or not snapshot.memory.valid:
            self.status_value.setText("PRESUPUESTO NO VERIFICADO")

    def closeEvent(self, event: object) -> None:
        self.timer.stop()
        super().closeEvent(event)
