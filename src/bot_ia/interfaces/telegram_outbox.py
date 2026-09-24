# -*- coding: utf-8 -*-
"""Persistencia idempotente de entregas de Telegram.

La cola guarda únicamente respuestas ya procesadas por BOT-IA. El offset de
Telegram se avanza sólo después de una entrega completa.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .telegram import TelegramOutbound


class TelegramOutboxError(RuntimeError):
    """Error de persistencia o integridad de la outbox."""


@dataclass(frozen=True, slots=True)
class TelegramOutboxRecord:
    update_id: int
    chat_id: str
    outbound: TelegramOutbound
    next_chunk: int
    status: str


class TelegramOutboxStore:
    """Outbox durable e idempotente para respuestas de Telegram."""

    VALID_STATUSES = {"PENDING", "DELIVERED", "FAILED"}

    def __init__(self, database_path: Path | str) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_outbox (
                    update_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    next_chunk INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'DELIVERED', 'FAILED')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_telegram_outbox_status "
                "ON telegram_outbox(status, created_at)"
            )

    @staticmethod
    def _serialize(outbound: "TelegramOutbound") -> str:
        payload: dict[str, Any] = {
            "chat_id": outbound.chat_id,
            "text": outbound.text,
            "route": outbound.route,
            "keyboard": [
                [list(button) for button in row]
                for row in outbound._normalized_keyboard()
            ],
            "auto_delete_seconds": outbound.auto_delete_seconds,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _deserialize(payload: str) -> "TelegramOutbound":
        from .telegram import TelegramOutbound
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as error:
            raise TelegramOutboxError("telegram outbox payload is invalid JSON") from error
        if not isinstance(raw, dict):
            raise TelegramOutboxError("telegram outbox payload must be an object")
        keyboard_raw = raw.get("keyboard", [])
        keyboard: list[tuple[tuple[str, str], ...]] = []
        if not isinstance(keyboard_raw, list):
            raise TelegramOutboxError("telegram outbox keyboard is invalid")
        for row in keyboard_raw:
            if not isinstance(row, list):
                raise TelegramOutboxError("telegram outbox keyboard row is invalid")
            buttons: list[tuple[str, str]] = []
            for button in row:
                if not isinstance(button, list) or len(button) != 2:
                    raise TelegramOutboxError("telegram outbox button is invalid")
                label, data = button
                if not isinstance(label, str) or not isinstance(data, str):
                    raise TelegramOutboxError("telegram outbox button values are invalid")
                buttons.append((label, data))
            keyboard.append(tuple(buttons))
        chat_id = raw.get("chat_id")
        text = raw.get("text")
        route = raw.get("route")
        auto_delete_seconds = raw.get("auto_delete_seconds")
        if not isinstance(chat_id, str) or not isinstance(text, str):
            raise TelegramOutboxError("telegram outbox message fields are invalid")
        if route is not None and not isinstance(route, str):
            raise TelegramOutboxError("telegram outbox route is invalid")
        if auto_delete_seconds is not None and (
            not isinstance(auto_delete_seconds, int) or isinstance(auto_delete_seconds, bool)
        ):
            raise TelegramOutboxError("telegram outbox auto-delete value is invalid")
        return TelegramOutbound(
            chat_id,
            text,
            route,
            tuple(keyboard),
            auto_delete_seconds,
        )

    def get(self, update_id: int) -> TelegramOutboxRecord | None:
        if not isinstance(update_id, int) or update_id < 0:
            raise ValueError("update_id must be a non-negative integer")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT update_id, chat_id, payload, next_chunk, status "
                "FROM telegram_outbox WHERE update_id=?",
                (update_id,),
            ).fetchone()
        if row is None:
            return None
        status = row["status"]
        if status not in self.VALID_STATUSES:
            raise TelegramOutboxError("telegram outbox contains an invalid status")
        if row["next_chunk"] < 0:
            raise TelegramOutboxError("telegram outbox contains an invalid chunk offset")
        outbound = self._deserialize(row["payload"])
        return TelegramOutboxRecord(
            row["update_id"],
            str(row["chat_id"]),
            outbound,
            row["next_chunk"],
            status,
        )

    def create_pending(self, update_id: int, outbound: "TelegramOutbound") -> TelegramOutboxRecord:
        if not isinstance(update_id, int) or update_id < 0:
            raise ValueError("update_id must be a non-negative integer")
        serialized = self._serialize(outbound)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO telegram_outbox
                    (update_id, chat_id, payload, next_chunk, status)
                VALUES (?, ?, ?, 0, 'PENDING')
                """,
                (update_id, int(outbound.chat_id), serialized),
            )
        record = self.get(update_id)
        if record is None:
            raise TelegramOutboxError("telegram outbox record disappeared after insert")
        return record

    def ack_chunk(self, update_id: int, next_chunk: int) -> None:
        if not isinstance(next_chunk, int) or next_chunk < 0:
            raise ValueError("next_chunk must be a non-negative integer")
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE telegram_outbox
                SET next_chunk=?
                WHERE update_id=? AND status='PENDING' AND next_chunk<=?
                """,
                (next_chunk, update_id, next_chunk),
            )
            if cursor.rowcount != 1:
                raise TelegramOutboxError("telegram outbox chunk ACK was not applied")

    def mark_delivered(self, update_id: int) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE telegram_outbox
                SET status='DELIVERED'
                WHERE update_id=? AND status='PENDING'
                """,
                (update_id,),
            )
            if cursor.rowcount != 1:
                record = self.get(update_id)
                if record is not None and record.status == "DELIVERED":
                    return
                raise TelegramOutboxError("telegram outbox delivery transition failed")

    def mark_failed(self, update_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE telegram_outbox SET status='FAILED' WHERE update_id=?",
                (update_id,),
            )
