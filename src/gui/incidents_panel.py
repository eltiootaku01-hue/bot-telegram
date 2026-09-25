# -*- coding: utf-8 -*-
"""Panel de incidencias, historial y acciones administrativas de BOT-IA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bot_ia.interfaces.cafe_economy import CafeWalletStore
from bot_ia.interfaces.order_support import ComplaintStore
from .waifu_registry import WaifuRegistry


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    incident_id: str
    kind: str
    user_id: str
    rule_or_error: str
    detail: str
    created_at: str
    forgiveness_count: int = 0
    trust_level: str = "unknown"
    registered_at: str = ""


class IncidentStore:
    """Registro local extensible para errores y strikes; reclamos viven en ComplaintStore."""

    def __init__(self, root: Path) -> None:
        self.path = Path(root) / "config" / "incidents.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_cami_guard_alert(
        self,
        *,
        user_id: str,
        reason: str,
        detail: str,
    ) -> IncidentRecord:
        """Persiste una alerta preventiva para que aparezca en el panel."""
        now = datetime.now(timezone.utc).isoformat()
        record = IncidentRecord(
            incident_id=f"CAMI-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            kind="Cami Guard",
            user_id=str(user_id),
            rule_or_error=str(reason),
            detail=str(detail),
            created_at=now,
            registered_at=now,
        )
        try:
            payload = json.loads(self.incidents.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        items = payload.get("incidents")
        if not isinstance(items, list):
            items = []
        items.append({
            "incident_id": record.incident_id,
            "kind": record.kind,
            "user_id": record.user_id,
            "rule_or_error": record.rule_or_error,
            "detail": record.detail,
            "created_at": record.created_at,
            "forgiveness_count": record.forgiveness_count,
            "trust_level": record.trust_level,
            "registered_at": record.registered_at,
        })
        payload["incidents"] = items
        self.incidents.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.refresh()
        return record

    def list(self) -> list[IncidentRecord]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = payload.get("incidents", []) if isinstance(payload, dict) else []
        return [
            IncidentRecord(
                incident_id=str(item.get("incident_id", "")),
                kind=str(item.get("kind", "Error")),
                user_id=str(item.get("user_id", "")),
                rule_or_error=str(item.get("rule_or_error", "")),
                detail=str(item.get("detail", "")),
                created_at=str(item.get("created_at", "")),
                forgiveness_count=max(0, int(item.get("forgiveness_count", 0))),
                trust_level=str(item.get("trust_level", "unknown")),
                registered_at=str(item.get("registered_at", "")),
            )
            for item in items
            if isinstance(item, dict)
        ]


class IncidentsPanel(QWidget):
    """Tabla + historial completo + acciones sin bloquear el event loop."""

    HEADERS = ("ID", "Tipo", "Usuario", "Fecha", "Regla / Error", "Estado")

    def __init__(
        self,
        root: Path,
        *,
        wallet: CafeWalletStore,
        registry: WaifuRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.root = Path(root)
        self.wallet = wallet
        self.registry = registry
        self.complaints = ComplaintStore(self.root)
        self.incidents = IncidentStore(self.root)
        self._current = None

        layout = QVBoxLayout(self)
        title = QLabel("🛡 Incidencias & Moderación")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Errores, reembolsos, quejas y aislamientos. Selecciona una fila para ver el historial."
        )
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._show_selected)
        layout.addWidget(self.table, 2)

        detail = QWidget()
        form = QFormLayout(detail)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setMinimumHeight(170)
        form.addRow("Historial completo", self.history)
        layout.addWidget(detail, 1)

        actions = QHBoxLayout()
        self.forgive_button = QPushButton("✅ Perdonar")
        self.refund_button = QPushButton("💸 Aceptar Reembolso")
        self.reject_button = QPushButton("❌ Rechazar / Ban Permanent")
        self.forgive_button.clicked.connect(self._forgive)
        self.refund_button.clicked.connect(self._refund)
        self.reject_button.clicked.connect(self._reject)
        for button in (self.forgive_button, self.refund_button, self.reject_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        rows: list[tuple[str, str, str, str, str, str, object]] = []
        for item in self.incidents.list():
            rows.append((
                item.incident_id, item.kind, item.user_id, item.created_at,
                item.rule_or_error, "Aislamiento / Incidente", item,
            ))
        try:
            payload = json.loads(self.complaints.path.read_text(encoding="utf-8"))
            for item in payload.get("complaints", []):
                if isinstance(item, dict):
                    rows.append((
                        str(item.get("complaint_id", "")), "Queja / Reembolso",
                        str(item.get("user_id", "")), str(item.get("created_at", "")),
                        str(item.get("text", "")),
                        str(item.get("status", "OPEN")), item,
                    ))
        except (OSError, json.JSONDecodeError):
            pass
        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values[:6]):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
            self.table.item(row, 0).setData(Qt.UserRole, values[6])
        self.table.resizeColumnsToContents()

    def _selected(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).data(Qt.UserRole) if row >= 0 else None

    def _show_selected(self) -> None:
        item = self._selected()
        self._current = item
        if item is None:
            self.history.clear()
            return
        if isinstance(item, IncidentRecord):
            self.history.setPlainText(
                f"ID único: {item.incident_id}\n"
                f"Usuario: {item.user_id}\n"
                f"Perdones previos: {item.forgiveness_count}\n"
                f"Nivel de confianza: {item.trust_level}\n"
                f"Fecha de registro en el bot: {item.registered_at or item.created_at}\n"
                f"Fecha del incidente: {item.created_at}\n"
                f"Regla/error roto: {item.rule_or_error}\n"
                f"Detalle exacto: {item.detail}"
            )
        else:
            self.history.setPlainText(
                f"ID único: {item.get('complaint_id', '')}\n"
                f"Usuario: {item.get('user_id', '')}\n"
                f"Perdones previos: {item.get('forgiveness_count', 0)}\n"
                f"Nivel de confianza: {item.get('trust_level', 'unknown')}\n"
                f"Fecha de registro en el bot: {item.get('registered_at', item.get('created_at', ''))}\n"
                f"Fecha del reclamo: {item.get('created_at', '')}\n"
                f"Regla/error roto: {item.get('rule_or_error', 'Reclamo')}\n"
                f"Registro exacto: {item.get('text', '')}"
            )

    def _forgive(self) -> None:
        item = self._selected()
        if item is None:
            return
        if isinstance(item, dict):
            item["status"] = "FORGIVEN"
            self._rewrite_complaints()
        QMessageBox.information(self, "Incidencias", "Incidencia marcada como perdonada.")
        self.refresh()

    def _refund(self) -> None:
        item = self._selected()
        if not isinstance(item, dict):
            return
        complaint_id = str(item.get("complaint_id", ""))
        try:
            self.complaints.resolve(
                complaint_id, "refund",
                wallet_store=self.wallet, registry=self.registry,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Reembolso", str(error))
            return
        self.refresh()

    def _reject(self) -> None:
        item = self._selected()
        if not isinstance(item, dict):
            return
        complaint_id = str(item.get("complaint_id", ""))
        try:
            self.complaints.resolve(
                complaint_id, "reject",
                wallet_store=self.wallet, registry=self.registry,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Rechazo", str(error))
            return
        self.refresh()

    def _rewrite_complaints(self) -> None:
        try:
            payload = json.loads(self.complaints.path.read_text(encoding="utf-8"))
            self.complaints.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except (OSError, json.JSONDecodeError):
            return
