from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TelegramUser
from sqlalchemy import text

from app.db.database import Database

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]

CREATE_XP_TABLE = """
CREATE TABLE IF NOT EXISTS xp_activity (
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    last_awarded_at TEXT NOT NULL,
    PRIMARY KEY (user_id, chat_id)
)
"""

UPSERT_PROFILE = """
INSERT INTO game_profiles (user_id, chat_id, level, experience, points, coins, gacha_d_streak)
VALUES (:user_id, :chat_id, 1, :xp, 0, 0, 0)
ON CONFLICT(user_id, chat_id) DO UPDATE SET
    experience = game_profiles.experience + excluded.experience,
    updated_at = CURRENT_TIMESTAMP
"""


class XPTrackerMiddleware(BaseMiddleware):
    """Persistent per-user XP tracker with an atomic SQLite cooldown."""

    def __init__(
        self,
        database: Database,
        *,
        xp_per_message: int = 5,
        cooldown_seconds: int = 60,
    ) -> None:
        if xp_per_message <= 0:
            raise ValueError("xp_per_message must be positive")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        self.database = database
        self.xp_per_message = xp_per_message
        self.cooldown_seconds = cooldown_seconds

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)
        if isinstance(user, TelegramUser) and chat is not None and not user.is_bot:
            await self.record_activity(user.id, chat.id)
        return result

    async def record_activity(
        self,
        user_id: int,
        chat_id: int,
        *,
        now: datetime | None = None,
    ) -> bool:
        if user_id <= 0 or chat_id == 0:
            return False
        instant = now or datetime.now(timezone.utc)
        async with self.database.session(write=True) as session:
            await session.execute(text(CREATE_XP_TABLE))
            row = await session.execute(
                text(
                    "SELECT last_awarded_at FROM xp_activity "
                    "WHERE user_id=:user_id AND chat_id=:chat_id"
                ),
                {"user_id": user_id, "chat_id": chat_id},
            )
            previous = row.scalar_one_or_none()
            if previous is not None:
                previous_dt = datetime.fromisoformat(str(previous))
                if previous_dt.tzinfo is None:
                    previous_dt = previous_dt.replace(tzinfo=timezone.utc)
                if (
                    instant.timestamp() - previous_dt.timestamp()
                    < self.cooldown_seconds
                ):
                    return False

            await session.execute(
                text(
                    """
                    INSERT INTO xp_activity(user_id, chat_id, last_awarded_at)
                    VALUES (:user_id, :chat_id, :now)
                    ON CONFLICT(user_id, chat_id)
                    DO UPDATE SET last_awarded_at=excluded.last_awarded_at
                    """
                ),
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "now": instant.isoformat(),
                },
            )
            await session.execute(
                text(UPSERT_PROFILE),
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "xp": self.xp_per_message,
                },
            )
            return True
