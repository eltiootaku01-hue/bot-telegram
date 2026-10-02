# -*- coding: utf-8 -*-
"""Persistencia SQLite compartida para la economía y administración del Café."""

from __future__ import annotations

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


APPLICATION_ID = 0x424F5449  # "BOTI"
SCHEMA_VERSION = 2
BUSY_TIMEOUT_MS = 15_000


class EconomyPersistenceError(RuntimeError):
    """Error crítico de persistencia: nunca se convierte en estado vacío."""


class EconomyDatabase:
    """Base SQLite única, WAL, segura frente a concurrencia entre procesos."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self.path,
                timeout=BUSY_TIMEOUT_MS / 1000,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys=ON")
            mode = str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if mode != "wal":
                raise EconomyPersistenceError(
                    f"No se pudo activar WAL en {self.path}"
                )
            connection.execute("PRAGMA synchronous=NORMAL")
            return connection
        except EconomyPersistenceError:
            if connection is not None:
                connection.close()
            raise
        except (OSError, sqlite3.DatabaseError) as error:
            if connection is not None:
                connection.close()
            raise EconomyPersistenceError(
                f"No se pudo abrir la base SQLite de BOT-IA: {self.path}"
            ) from error

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with closing(self.connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                yield connection
                connection.execute("COMMIT")
            except Exception:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.DatabaseError:
                    pass
                raise

    def _initialize(self) -> None:
        try:
            with self.transaction(immediate=True) as connection:
                identity = int(connection.execute("PRAGMA application_id").fetchone()[0])
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if identity not in {0, APPLICATION_ID}:
                    raise EconomyPersistenceError(
                        "La base SQLite pertenece a otra aplicación."
                    )
                if version not in {0, 1, SCHEMA_VERSION}:
                    raise EconomyPersistenceError(
                        f"Versión SQLite no soportada: {version}"
                    )
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                statements = (
                    """
                    CREATE TABLE IF NOT EXISTS schema_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS wallet (
                        user_id TEXT PRIMARY KEY,
                        points INTEGER NOT NULL CHECK(points >= 0),
                        pity_sr INTEGER NOT NULL CHECK(pity_sr >= 0),
                        pity_ur INTEGER NOT NULL CHECK(pity_ur >= 0),
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS vip (
                        user_id TEXT PRIMARY KEY,
                        vip INTEGER NOT NULL CHECK(vip IN (0, 1)),
                        source TEXT NOT NULL DEFAULT '',
                        donated_stars INTEGER NOT NULL CHECK(donated_stars >= 0),
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS complaints (
                        complaint_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        chat_id TEXT NOT NULL,
                        text TEXT NOT NULL,
                        order_id TEXT NOT NULL DEFAULT '',
                        product_type TEXT NOT NULL DEFAULT '',
                        points_paid INTEGER NOT NULL CHECK(points_paid >= 0),
                        status TEXT NOT NULL DEFAULT 'OPEN',
                        action TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        resolved_at TEXT,
                        points_adjustment INTEGER NOT NULL DEFAULT 0
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS idx_complaints_user
                        ON complaints(user_id)
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS idx_complaints_status
                        ON complaints(status)
                    """,
                )
                for statement in statements:
                    connection.execute(statement)

                # Schema v2: orders becomes durable SQLite state shared with wallet.
                # For an existing v1 database the CREATE statements below are
                # the migration body; user_version advances only after all
                # schema changes succeed inside this transaction.
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        product_type TEXT NOT NULL,
                        destination TEXT NOT NULL,
                        rarity TEXT NOT NULL,
                        cost INTEGER NOT NULL CHECK(cost > 0),
                        summary TEXT NOT NULL,
                        resolution TEXT NOT NULL,
                        render_style TEXT NOT NULL,
                        prompt_en TEXT NOT NULL,
                        status TEXT NOT NULL
                            CHECK(status IN ('PENDING', 'CONFIRMED', 'CANCELLED')),
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_orders_user_status_created
                        ON orders(user_id, status, created_at)
                    """
                )
                connection.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_one_pending_user
                        ON orders(user_id)
                        WHERE status = 'PENDING'
                    """
                )
                if version < SCHEMA_VERSION:
                    connection.execute(
                        f"PRAGMA user_version={SCHEMA_VERSION}"
                    )
        except EconomyPersistenceError:
            raise
        except (OSError, sqlite3.DatabaseError) as error:
            raise EconomyPersistenceError(
                f"No se pudo inicializar la base SQLite de BOT-IA: {self.path}"
            ) from error
