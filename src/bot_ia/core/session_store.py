# -*- coding: utf-8 -*-
"""Persistencia local y aislada del estado activo de las conversaciones."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import threading

from bot_ia.contracts import SessionState


class SessionStorageError(RuntimeError):
    pass


class PersistentSessionStore:
    """Guarda sólo estado operativo; no convierte conversación en canon."""

    SCHEMA_VERSION = 1
    APPLICATION_ID = 0x42494153  # "BIAS"

    def __init__(self, database_path: Path) -> None:
        self._path = database_path
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connection()) as connection:
            with connection:
                connection.execute("PRAGMA journal_mode=WAL")
                application_id = connection.execute("PRAGMA application_id").fetchone()[0]
                if application_id not in (0, self.APPLICATION_ID):
                    raise SessionStorageError("database belongs to another application")
                connection.execute(f"PRAGMA application_id={self.APPLICATION_ID}")
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > self.SCHEMA_VERSION:
                    raise SessionStorageError("session database is newer than this BOT-IA version")
                if version == 0:
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS sessions (user_id TEXT NOT NULL, conversation_id TEXT NOT NULL, session_id TEXT NOT NULL, universe_id TEXT NOT NULL, expires_at TEXT NOT NULL, active_entity_ids TEXT NOT NULL, recent_reference_ids TEXT NOT NULL, chapter_id TEXT, mode TEXT NOT NULL, PRIMARY KEY (user_id, conversation_id))"
                    )
                    connection.execute("CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at)")
                    connection.execute(f"PRAGMA user_version={self.SCHEMA_VERSION}")

    def get(self, user_id: str, conversation_id: str) -> SessionState | None:
        with self._lock:
            return self._get_locked(user_id, conversation_id)

    def _get_locked(self, user_id: str, conversation_id: str) -> SessionState | None:
        with closing(self._connection()) as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE user_id=? AND conversation_id=?",
                (user_id, conversation_id),
            ).fetchone()
            if row is None:
                return None
            try:
                expires_at = datetime.fromisoformat(row["expires_at"])
                if expires_at.tzinfo is None:
                    raise ValueError("session expiry must be timezone-aware")
                if datetime.now(timezone.utc) >= expires_at:
                    self._delete(connection, user_id, conversation_id)
                    connection.commit()
                    return None
                active_entities = json.loads(row["active_entity_ids"])
                recent_references = json.loads(row["recent_reference_ids"])
                if not isinstance(active_entities, list) or not isinstance(recent_references, list):
                    raise ValueError("session collections must be lists")
                return SessionState(
                    row["session_id"], row["universe_id"], expires_at,
                    tuple(active_entities), tuple(recent_references),
                    row["chapter_id"], row["mode"],
                )
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise SessionStorageError("invalid persisted session") from error

    def get_or_create(self, user_id: str, conversation_id: str, universe_id: str | None) -> SessionState | None:
        """Satisfy the application session-store contract using only local persistence."""
        state = self.get(user_id, conversation_id)
        if state is not None or universe_id is None:
            return state
        state = SessionState(
            f"local:{user_id}:{conversation_id}",
            universe_id,
            datetime.now(timezone.utc) + timedelta(hours=8),
        )
        self.put(user_id, conversation_id, state)
        return state

    def put(self, user_id: str, conversation_id: str, state: SessionState) -> None:
        with self._lock:
            return self._put_locked(user_id, conversation_id, state)

    def _put_locked(self, user_id: str, conversation_id: str, state: SessionState) -> None:
        if not user_id or not conversation_id:
            raise SessionStorageError("user and conversation identifiers are required")
        if state.is_expired(datetime.now(timezone.utc)):
            self.delete(user_id, conversation_id)
            return
        with closing(self._connection()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id, conversation_id) DO UPDATE SET session_id=excluded.session_id, universe_id=excluded.universe_id, expires_at=excluded.expires_at, active_entity_ids=excluded.active_entity_ids, recent_reference_ids=excluded.recent_reference_ids, chapter_id=excluded.chapter_id, mode=excluded.mode",
                    (user_id, conversation_id, state.session_id, state.universe_id, state.expires_at.isoformat(), json.dumps(state.active_entity_ids), json.dumps(state.recent_reference_ids), state.chapter_id, state.mode),
                )

    def delete(self, user_id: str, conversation_id: str) -> None:
        with self._lock:
            return self._delete_public_locked(user_id, conversation_id)

    def _delete_public_locked(self, user_id: str, conversation_id: str) -> None:
        with closing(self._connection()) as connection:
            with connection:
                self._delete(connection, user_id, conversation_id)

    @staticmethod
    def _delete(connection: sqlite3.Connection, user_id: str, conversation_id: str) -> None:
        connection.execute("DELETE FROM sessions WHERE user_id=? AND conversation_id=?", (user_id, conversation_id))

    def purge_expired(self, now: datetime | None = None) -> int:
        with self._lock:
            return self._purge_expired_locked(now)

    def _purge_expired_locked(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        with closing(self._connection()) as connection:
            with connection:
                cursor = connection.execute("DELETE FROM sessions WHERE expires_at<=?", (now.isoformat(),))
                return cursor.rowcount
