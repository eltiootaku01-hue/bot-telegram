from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


class EventRepository:
    """Persistent SQLite audit log for Command Center notification events."""

    VALID_STATUSES = {"QUEUED", "RETRYING", "DELIVERED", "FAILED"}
    VALID_PLATFORMS = {"telegram", "discord"}

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        parent = Path(db_path).parent
        if str(parent) not in {".", ""}:
            parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS event_logs (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    bot_name TEXT NOT NULL,
                    thread_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    author TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'QUEUED',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    telegram_message_id INTEGER NULL,
                    last_error TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_logs_status ON event_logs(status)"
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    author TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    platform TEXT NOT NULL
                        CHECK (platform IN ('telegram', 'discord')),
                    destination_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'QUEUED'
                        CHECK (status IN ('QUEUED', 'RETRYING', 'DELIVERED', 'FAILED')),
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    external_message_id TEXT NULL,
                    last_error TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(event_id) REFERENCES notification_events(event_id)
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_deliveries_status "
                "ON notification_deliveries(platform, status)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_deliveries_event "
                "ON notification_deliveries(event_id)"
            )
            await db.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def create_event(
        self,
        *,
        event_id: str,
        event_type: str,
        bot_name: str,
        thread_id: int,
        title: str,
        url: str,
        author: str,
        max_retries: int = 3,
    ) -> bool:
        """Insert an event atomically. Returns False when event_id already exists."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO event_logs (
                    event_id, event_type, bot_name, thread_id, title, url, author,
                    status, retry_count, max_retries, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'QUEUED', 0, ?, ?, ?)
                """,
                (
                    event_id,
                    event_type,
                    bot_name,
                    thread_id,
                    title,
                    url,
                    author,
                    max_retries,
                    now,
                    now,
                ),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def create_notification_event(
        self,
        *,
        event_id: str,
        event_type: str,
        title: str,
        url: str,
        author: str,
    ) -> bool:
        """Create the platform-neutral event record idempotently."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO notification_events
                    (event_id, event_type, title, url, author)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, event_type, title, url, author),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def create_delivery(
        self,
        *,
        delivery_id: str,
        event_id: str,
        platform: str,
        destination_id: int,
        max_retries: int = 3,
    ) -> bool:
        """Create one independent platform delivery idempotently."""
        normalized_platform = platform.strip().casefold()
        if normalized_platform not in self.VALID_PLATFORMS:
            raise ValueError(f"Unsupported notification platform: {platform}")
        if destination_id <= 0:
            raise ValueError("destination_id must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO notification_deliveries
                    (delivery_id, event_id, platform, destination_id, max_retries)
                VALUES (?, ?, ?, ?, ?)
                """,
                (delivery_id, event_id, normalized_platform, destination_id, max_retries),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def mark_delivery_delivered(
        self,
        delivery_id: str,
        external_message_id: str,
    ) -> None:
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE notification_deliveries
                SET status = 'DELIVERED', external_message_id = ?,
                    last_error = NULL, updated_at = ?
                WHERE delivery_id = ?
                """,
                (external_message_id, now, delivery_id),
            )
            await db.commit()

    async def record_delivery_failure(
        self,
        delivery_id: str,
        error_msg: str,
        *,
        is_final: bool = False,
    ) -> None:
        now = self._now()
        status = 'FAILED' if is_final else 'RETRYING'
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE notification_deliveries
                SET status = ?, retry_count = retry_count + 1,
                    last_error = ?, updated_at = ?
                WHERE delivery_id = ?
                """,
                (status, error_msg[:2000], now, delivery_id),
            )
            await db.commit()

    async def get_pending_deliveries(
        self,
        platform: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return queued/retrying deliveries, optionally scoped to one platform."""
        query = (
            "SELECT * FROM notification_deliveries "
            "WHERE status IN ('QUEUED', 'RETRYING')"
        )
        params: tuple[str, ...] = ()
        if platform is not None:
            normalized_platform = platform.strip().casefold()
            if normalized_platform not in self.VALID_PLATFORMS:
                raise ValueError(f"Unsupported notification platform: {platform}")
            query += " AND platform = ?"
            params = (normalized_platform,)
        query += " ORDER BY created_at ASC"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def mark_delivered(self, event_id: str, telegram_message_id: int) -> None:
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE event_logs
                SET status = 'DELIVERED',
                    telegram_message_id = ?,
                    last_error = NULL,
                    updated_at = ?
                WHERE event_id = ?
                """,
                (telegram_message_id, now, event_id),
            )
            await db.commit()

    async def record_attempt_failure(
        self,
        event_id: str,
        error_msg: str,
        *,
        is_final: bool = False,
    ) -> None:
        now = self._now()
        new_status = "FAILED" if is_final else "RETRYING"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE event_logs
                SET status = ?,
                    retry_count = retry_count + 1,
                    last_error = ?,
                    updated_at = ?
                WHERE event_id = ?
                """,
                (new_status, error_msg[:2000], now, event_id),
            )
            await db.commit()

    async def get_event_by_id(self, event_id: str) -> dict[str, Any] | None:
        """Return one event by its stable event_id, or None when it does not exist."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM event_logs WHERE event_id = ?",
                (event_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        """Backward-compatible alias for get_event_by_id."""
        return await self.get_event_by_id(event_id)

    async def get_pending_events(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM event_logs
                WHERE status IN ('QUEUED', 'RETRYING')
                ORDER BY created_at ASC
                """
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def get_failed_events(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM event_logs
                WHERE status = 'FAILED'
                ORDER BY created_at DESC
                """
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]
