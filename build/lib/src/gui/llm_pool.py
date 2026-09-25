from __future__ import annotations

import json
import os
import sqlite3
import uuid

import keyring
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

SERVICE = "cafe-otaku.llm"
CONFIG_KEY = "pool_config"
PROVIDERS = ("OpenAI", "Hugging Face", "Groq", "Google Gemini", "Custom REST")


def load_pool() -> list[dict]:
    try:
        value = json.loads(keyring.get_password(SERVICE, CONFIG_KEY) or "[]")
        return value if isinstance(value, list) else []
    except Exception:
        return []


def save_pool(rows: list[dict]) -> None:
    keyring.set_password(SERVICE, CONFIG_KEY, json.dumps(rows, ensure_ascii=False))


def _key(provider_id: str) -> str:
    return keyring.get_password(SERVICE, f"provider:{provider_id}") or ""


def _set_key(provider_id: str, value: str) -> None:
    keyring.set_password(SERVICE, f"provider:{provider_id}", value)


def _delete_key(provider_id: str) -> None:
    try:
        keyring.delete_password(SERVICE, f"provider:{provider_id}")
    except Exception:
        pass


def _db_path() -> str:
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")
    if ":///" in url:
        return url.split(":///", 1)[1].split("?", 1)[0] or "data/bot.db"
    return os.getenv("COMMAND_CENTER_DB_PATH", "data/command_center_events.db")


def publish_event(event_type: str, payload: dict) -> None:
    path = _db_path()
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS domain_events "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, "
                "event_type TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}', "
                "status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, "
                "available_at TEXT NOT NULL, locked_at TEXT, heartbeat_at TEXT, "
                "completed_at TEXT, last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT INTO domain_events "
                "(event_id,event_type,payload,status,attempts,available_at,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, event_type, json.dumps(payload, ensure_ascii=False),
                 "pending", 0, now, now, now),
            )
            conn.commit()
    except sqlite3.Error:
        pass


class LLMProviderPoolWidget(QWidget):
    status_changed = Signal(str)
    event_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectionLLM")
        self.rows: list[dict] = []
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("⚡ Proveedores LLM / APIs · Pool dinámico y Failover"))
        add = QPushButton("+ AGREGAR NUEVA API")
        add.clicked.connect(self.add_row)
        header.addWidget(add)
        root.addLayout(header)

        self.status = QLabel(
            "API Keys en keyring del sistema. Prioridad menor = primer intento. "
            "429/error → siguiente instancia → OFFLINE/SQLite."
        )
        root.addWidget(self.status)

        self.container = QWidget()
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.container)
        root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        save = QPushButton("Guardar pool + activar failover")
        save.clicked.connect(self.save)
        offline = QPushButton("Registrar prueba OFFLINE")
        offline.clicked.connect(self.test_offline)
        buttons.addWidget(save)
        buttons.addWidget(offline)
        root.addLayout(buttons)

        for row in load_pool():
            self.add_row(row)
        if not self.rows:
            self.add_row()

    def add_row(self, data: dict | None = None) -> None:
        data = data or {}
        provider_id = str(data.get("id") or uuid.uuid4().hex)
        box = QGroupBox()
        form = QFormLayout(box)

        provider = QComboBox()
        provider.addItems(PROVIDERS)
        provider.setCurrentText(str(data.get("provider") or "OpenAI"))

        alias = QLineEdit(str(data.get("alias") or f"API {len(self.rows) + 1}"))
        key = QLineEdit()
        key.setEchoMode(QLineEdit.EchoMode.Password)
        key.setPlaceholderText("API Key (enmascarada)")
        if _key(provider_id):
            key.setPlaceholderText("Clave guardada en keyring")

        endpoint = QLineEdit(str(data.get("endpoint") or ""))
        endpoint.setPlaceholderText("Endpoint REST (opcional)")
        model = QLineEdit(str(data.get("model") or ""))
        model.setPlaceholderText("Modelo")

        priority = QSpinBox()
        priority.setRange(1, 999)
        priority.setValue(int(data.get("priority") or len(self.rows) + 1))

        enabled = QCheckBox("Activo")
        enabled.setChecked(bool(data.get("enabled", True)))

        remove = QPushButton("Eliminar")
        remove.clicked.connect(lambda: self.remove_row(provider_id))

        form.addRow("Proveedor:", provider)
        form.addRow("Alias / nombre:", alias)
        form.addRow("API Key:", key)
        form.addRow("Endpoint:", endpoint)
        form.addRow("Modelo:", model)
        form.addRow("Prioridad:", priority)
        form.addRow(enabled)
        form.addRow(remove)

        row = {
            "id": provider_id, "box": box, "provider": provider, "alias": alias,
            "key": key, "endpoint": endpoint, "model": model,
            "priority": priority, "enabled": enabled,
        }
        self.rows.append(row)
        self.rows_layout.addWidget(box)

    def remove_row(self, provider_id: str) -> None:
        for row in list(self.rows):
            if row["id"] != provider_id:
                continue
            self.rows.remove(row)
            row["box"].setParent(None)
            row["box"].deleteLater()
            _delete_key(provider_id)
            self.save()
            return

    def save(self) -> None:
        rows = []
        for row in self.rows:
            secret = row["key"].text().strip()
            if secret:
                _set_key(row["id"], secret)
            rows.append({
                "id": row["id"],
                "provider": row["provider"].currentText(),
                "alias": row["alias"].text().strip() or row["provider"].currentText(),
                "endpoint": row["endpoint"].text().strip(),
                "model": row["model"].text().strip(),
                "priority": row["priority"].value(),
                "enabled": row["enabled"].isChecked(),
            })
        rows.sort(key=lambda item: (item["priority"], item["alias"].casefold()))
        save_pool(rows)
        publish_event("LLM_PROVIDER_POOL_UPDATED", {
            "providers": [
                {key: item[key] for key in ("id", "provider", "alias", "priority", "enabled")}
                for item in rows
            ]
        })
        message = f"Pool guardado: {sum(1 for item in rows if item['enabled'])} instancias activas."
        self.status.setText(message + " Failover → OFFLINE/SQLite habilitado.")
        self.status_changed.emit(message)

    def test_offline(self) -> None:
        publish_event("LLM_OFFLINE_FALLBACK_REQUESTED", {"source": "command_center"})
        self.status.setText("Evento OFFLINE registrado. Runtime usará SQLite si no hay proveedor disponible.")
        self.event_requested.emit()
