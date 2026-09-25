# -*- coding: utf-8 -*-
"""Registro autoritativo de salas Telegram derivado del provisioning."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class TelegramRoomRoutingError(RuntimeError):
    """Error al resolver una sala Telegram de forma segura."""


class TelegramRoomRouter:
    """Mapa exacto (chat_id, message_thread_id) -> room_key.

    La tabla se alimenta exclusivamente desde GroupSetupStore/provisioning.
    Un tema no registrado nunca se convierte silenciosamente en "general".
    """

    def __init__(self, database_path: str | Path) -> None:
        self.path = Path(database_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self.path,
                timeout=15.0,
                isolation_level=None,
            )
            connection.execute("PRAGMA busy_timeout=15000")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            return connection
        except (OSError, sqlite3.DatabaseError) as error:
            raise TelegramRoomRoutingError(
                f"No se pudo abrir el registro de salas: {self.path}"
            ) from error

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_room_routes (
                    chat_id TEXT NOT NULL,
                    message_thread_id INTEGER NOT NULL,
                    room_key TEXT NOT NULL,
                    room_name TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(chat_id, message_thread_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_telegram_room_routes_key
                ON telegram_room_routes(chat_id, room_key)
                """
            )
        finally:
            connection.close()

    def replace_chat_rooms(
        self,
        chat_id: str,
        rooms: tuple[object, ...],
    ) -> None:
        clean_chat = str(chat_id).strip()
        if not clean_chat:
            raise ValueError("chat_id es obligatorio")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM telegram_room_routes WHERE chat_id=?",
                (clean_chat,),
            )
            for room in rooms:
                room_key = str(getattr(room, "key", "")).strip()
                room_name = str(getattr(room, "name", "")).strip()
                external_id = str(getattr(room, "external_id", "")).strip()
                if not room_key or not external_id:
                    raise ValueError("El provisioning contiene una sala inválida")
                try:
                    thread_id = int(external_id)
                except ValueError as error:
                    raise ValueError(
                        f"message_thread_id inválido para {room_key!r}"
                    ) from error
                if thread_id < 0:
                    raise ValueError("message_thread_id no puede ser negativo")
                connection.execute(
                    """
                    INSERT INTO telegram_room_routes(
                        chat_id, message_thread_id, room_key, room_name
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (clean_chat, thread_id, room_key, room_name),
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def resolve(
        self,
        chat_id: str,
        message_thread_id: int | None,
    ) -> str | None:
        if message_thread_id is None:
            return None
        try:
            thread_id = int(message_thread_id)
        except (TypeError, ValueError):
            raise TelegramRoomRoutingError(
                "message_thread_id no es válido"
            )
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT room_key
                FROM telegram_room_routes
                WHERE chat_id=? AND message_thread_id=?
                """,
                (str(chat_id).strip(), thread_id),
            ).fetchone()
        finally:
            connection.close()
        return str(row[0]) if row is not None else None

    def close(self) -> None:
        """No mantiene conexiones persistentes; se conserva para lifecycle uniforme."""
        return None
