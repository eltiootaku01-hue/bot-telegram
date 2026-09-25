# -*- coding: utf-8 -*-
"""Ledger SQLite de idempotencia para eventos externos de Telegram."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from datetime import datetime, timezone


class TelegramEventLedgerError(RuntimeError):
    """Error crítico del ledger; no se transforma en un evento procesado."""


class TelegramEventLedger:
    """Registra claims/completados de updates y pagos de Telegram.

    El claim se hace antes de ejecutar efectos. Sólo un evento marcado como
    COMPLETED se considera consumido; un evento ya reclamado se trata como
    in-doubt y nunca se ejecuta otra vez automáticamente.
    """

    SCHEMA_VERSION = 1
    APPLICATION_ID = 0x54474556  # "TGEV"

    def __init__(self, database_path: str | Path) -> None:
        self.path = Path(database_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self.path,
                timeout=15.0,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.execute("PRAGMA busy_timeout=15000")
            connection.execute("PRAGMA foreign_keys=ON")
            mode = str(
                connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            ).lower()
            if mode != "wal":
                connection.close()
                raise TelegramEventLedgerError(
                    f"No se pudo activar WAL en {self.path}"
                )
            return connection
        except TelegramEventLedgerError:
            raise
        except (OSError, sqlite3.DatabaseError) as error:
            raise TelegramEventLedgerError(
                f"No se pudo abrir TelegramEventLedger: {self.path}"
            ) from error

    def _initialize(self) -> None:
        with closing(self._connection()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                application_id = int(
                    connection.execute(
                        "PRAGMA application_id"
                    ).fetchone()[0]
                )
                version = int(
                    connection.execute(
                        "PRAGMA user_version"
                    ).fetchone()[0]
                )
                if application_id not in {0, self.APPLICATION_ID}:
                    raise TelegramEventLedgerError(
                        "bot_ia_events.sqlite3 pertenece a otra aplicación"
                    )
                if version not in {0, self.SCHEMA_VERSION}:
                    raise TelegramEventLedgerError(
                        f"Versión del TelegramEventLedger no soportada: {version}"
                    )
                connection.execute(
                    f"PRAGMA application_id={self.APPLICATION_ID}"
                )
                connection.execute(
                    f"PRAGMA user_version={self.SCHEMA_VERSION}"
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telegram_events (
                        event_type TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        update_id INTEGER,
                        status TEXT NOT NULL
                            CHECK(status IN ('CLAIMED', 'COMPLETED')),
                        metadata TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(event_type, event_id)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS ix_telegram_events_update
                    ON telegram_events(update_id)
                    """
                )
                connection.execute("COMMIT")
            except Exception:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.DatabaseError:
                    pass
                raise

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def claim(
        self,
        event_type: str,
        event_id: str | int,
        *,
        update_id: int | None = None,
        metadata: str = "",
    ) -> bool:
        """Reclama un evento nuevo.

        True sólo para el primer reclamante. Cualquier ID ya existente no
        vuelve a ejecutar efectos automáticamente.
        """
        event_type = str(event_type).strip()
        event_id = str(event_id).strip()
        if not event_type or not event_id:
            raise ValueError("event_type y event_id son obligatorios")

        now = self._now()
        with closing(self._connection()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT status
                    FROM telegram_events
                    WHERE event_type=? AND event_id=?
                    """,
                    (event_type, event_id),
                ).fetchone()
                if existing is not None:
                    connection.execute("COMMIT")
                    return False

                connection.execute(
                    """
                    INSERT INTO telegram_events(
                        event_type, event_id, update_id, status,
                        metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, 'CLAIMED', ?, ?, ?)
                    """,
                    (
                        event_type,
                        event_id,
                        update_id,
                        metadata,
                        now,
                        now,
                    ),
                )
                connection.execute("COMMIT")
                return True
            except Exception:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.DatabaseError:
                    pass
                raise

    def mark_completed(
        self,
        event_type: str,
        event_id: str | int,
        *,
        metadata: str = "",
    ) -> None:
        with closing(self._connection()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE telegram_events
                    SET status='COMPLETED',
                        metadata=?,
                        updated_at=?
                    WHERE event_type=? AND event_id=?
                    """,
                    (
                        metadata,
                        self._now(),
                        str(event_type),
                        str(event_id),
                    ),
                )
                if cursor.rowcount != 1:
                    raise TelegramEventLedgerError(
                        "No existe un claim de Telegram para completar"
                    )
                connection.execute("COMMIT")
            except Exception:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.DatabaseError:
                    pass
                raise

    def status(
        self,
        event_type: str,
        event_id: str | int,
    ) -> str | None:
        with closing(self._connection()) as connection:
            row = connection.execute(
                """
                SELECT status
                FROM telegram_events
                WHERE event_type=? AND event_id=?
                """,
                (str(event_type), str(event_id)),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def seen(
        self,
        event_type: str,
        event_id: str | int,
    ) -> bool:
        return self.status(event_type, event_id) is not None

    def completed(
        self,
        event_type: str,
        event_id: str | int,
    ) -> bool:
        return self.status(event_type, event_id) == "COMPLETED"

    def close(self) -> None:
        """La clase no conserva conexiones persistentes; existe por simetría de lifecycle."""
        return None
