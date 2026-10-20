# -*- coding: utf-8 -*-
"""Desktop control for PC-LIMITED-09. Changing the slider only saves a preference."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QSlider, QVBoxLayout, QWidget

from bot_ia.resource_governor import (
    BUDGET_STEP_BYTES,
    MAX_BUDGET_BYTES,
    MIN_BUDGET_BYTES,
    GovernorSnapshot,
    PressureLevel,
    ResourceGovernor,
)


class ResourceGovernorPanel(QWidget):
    """Shows configured budget separately from measured process-tree consumption."""

    def __init__(self, governor: ResourceGovernor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.governor = governor
        self.setObjectName("ResourceGovernorPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("CONTROL DE RECURSOS DEL BOT")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        subtitle = QLabel(
            "El deslizador define una preferencia; no es un limitador duro de Windows. "
            "No inicia servicios ni conexiones."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("Muted")
        root.addWidget(subtitle)

        budget_box = QGroupBox("Presupuesto operativo configurado")
        budget_layout = QVBoxLayout(budget_box)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, (MAX_BUDGET_BYTES - MIN_BUDGET_BYTES) // BUDGET_STEP_BYTES)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(1)
        self.slider.setToolTip("Pasos de 0,25 GB; el presupuesto no representa el consumo medido.")
        self.slider.setValue((governor.budget_bytes - MIN_BUDGET_BYTES) // BUDGET_STEP_BYTES)
        self.budget_value = QLabel()
        self.budget_value.setObjectName("PageTitle")
        budget_layout.addWidget(self.slider)
        budget_layout.addWidget(self.budget_value)
        root.addWidget(budget_box)

        metrics_box = QGroupBox("Medición actual del árbol de procesos")
        metrics = QFormLayout(metrics_box)
        self.status_value = QLabel()
        self.status_value.setObjectName("PageTitle")
        self.profile_value = QLabel()
        self.memory_value = QLabel()
        self.private_value = QLabel()
        self.peak_value = QLabel()
        self.process_value = QLabel()
        self.paused_value = QLabel()
        self.persistence_value = QLabel()
        for label in (self.memory_value, self.private_value, self.peak_value, self.process_value, self.paused_value, self.persistence_value):
            label.setWordWrap(True)
        metrics.addRow("Estado", self.status_value)
        metrics.addRow("Perfil activo", self.profile_value)
        metrics.addRow("Working set agregado", self.memory_value)
        metrics.addRow("Memoria privada/commit", self.private_value)
        metrics.addRow("Pico de esta sesión", self.peak_value)
        metrics.addRow("Procesos medidos", self.process_value)
        metrics.addRow("Categorías no admitidas/pausadas", self.paused_value)
        metrics.addRow("Preferencia local", self.persistence_value)
        root.addWidget(metrics_box)

        self.gate_value = QLabel(
            "MODO LIMITADO POR GATE: BODY HEALTH sigue BLOCKED. "
            "Este control no activa Discord ni servicios ausentes y no altera las autoridades de WebChat."
        )
        self.gate_value.setWordWrap(True)
        self.gate_value.setObjectName("Muted")
        root.addWidget(self.gate_value)
        self.measurement_note = QLabel(
            "Nota: la suma de working sets puede contar páginas compartidas más de una vez. "
            "La memoria privada/commit es un indicador separado; ninguna cifra aquí demuestra "
            "por sí sola el cumplimiento global de 2 GB."
        )
        self.measurement_note.setWordWrap(True)
        self.measurement_note.setObjectName("Muted")
        root.addWidget(self.measurement_note)
        root.addStretch(1)

        self.slider.valueChanged.connect(self._on_budget_changed)
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

    def _on_budget_changed(self, steps: int) -> None:
        value = MIN_BUDGET_BYTES + int(steps) * BUDGET_STEP_BYTES
        self.governor.set_budget_bytes(value)
        self._render(self.governor.snapshot)

    def refresh_sample(self) -> None:
        self._render(self.governor.sample())

    def _render(self, snapshot: GovernorSnapshot) -> None:
        expected = (snapshot.budget_bytes - MIN_BUDGET_BYTES) // BUDGET_STEP_BYTES
        if self.slider.value() != expected:
            self.slider.blockSignals(True)
            self.slider.setValue(expected)
            self.slider.blockSignals(False)
        self.budget_value.setText(f"Seleccionado: {self._format_gb(snapshot.budget_bytes)}")
        self.status_value.setText(snapshot.status_label)
        self.profile_value.setText(
            {
                1_000_000_000: "1,00 GB — MODERACIÓN PRIORITARIA",
                1_250_000_000: "1,25 GB — MODERACIÓN + FUNCIONES ESENCIALES",
                1_500_000_000: "1,50 GB — TRABAJO CONTROLADO",
                1_750_000_000: "1,75 GB — ACTIVIDAD AMPLIADA",
                2_000_000_000: "2,00 GB — PRESUPUESTO MÁXIMO",
            }.get(snapshot.budget_bytes, "PERFIL SEGURO DE RECUPERACIÓN")
        )
        if snapshot.memory.valid:
            self.memory_value.setText(self._format_gb(snapshot.memory.working_set_bytes))
            self.private_value.setText(self._format_gb(snapshot.memory.private_commit_bytes) + " (commit privado)")
            self.process_value.setText(str(snapshot.memory.process_count))
            self.peak_value.setText(self._format_gb(snapshot.peak_working_set_bytes))
        else:
            self.memory_value.setText(
                "PRESUPUESTO NO VERIFICADO — "
                + (snapshot.memory.reason or "sensor no válido")
            )
            self.private_value.setText("NO DISPONIBLE")
            self.process_value.setText("NO DISPONIBLE")
            self.peak_value.setText(self._format_gb(snapshot.peak_working_set_bytes))
        self.paused_value.setText(", ".join(snapshot.paused_categories) if snapshot.paused_categories else "Ninguna por presión de memoria")
        if snapshot.configuration_recovered and not snapshot.preference_saved:
            config_text = "Preferencia inválida; perfil seguro de 1,00 GB en memoria, pero no pudo guardarse."
        elif snapshot.configuration_recovered:
            config_text = "Preferencia inválida; se recuperó el perfil seguro de 1,00 GB."
        elif not snapshot.preference_saved:
            config_text = "ERROR: no se pudo guardar la preferencia local."
        elif not snapshot.runtime_state_saved:
            config_text = "Preferencia guardada, pero no se pudo publicar el estado de ejecución; las tareas secundarias remotas quedan bloqueadas."
        else:
            config_text = "Preferencia local guardada; sin secretos."
        self.persistence_value.setText(config_text)
        if snapshot.pressure is PressureLevel.UNKNOWN:
            self.status_value.setToolTip(snapshot.memory.reason or "Muestra de memoria no válida")
        else:
            self.status_value.setToolTip(
                "Los indicadores describen el árbol observado y no aplican un límite duro de Windows."
            )
