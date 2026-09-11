from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.core.social_director import SocialSnapshot
from app.core.social_memory import SocialMemory
from app.core.time import utc_now
from app.db.models import User, UserChat


@dataclass(frozen=True, slots=True)
class SocialActivity:
    """Cheap DB-backed observation used before any autonomous/social AI call."""

    chat_id: int
    recent_messages: int
    active_users: int
    last_human_message_at: datetime | None
    observed_at: datetime

    def to_snapshot(self, memory: SocialMemory) -> SocialSnapshot:
        now = self.observed_at
        last_human = self.last_human_message_at or now
        human_recent = self.active_users >= 2 and (now - last_human).total_seconds() <= 10 * 60
        return SocialSnapshot(
            recent_messages=self.recent_messages,
            active_users=self.active_users,
            minutes_since_last_message=max(0, int((now - last_human).total_seconds() // 60)),
            minutes_since_last_bot_message=memory.minutes_since_last_bot_message(now),
            minutes_since_last_event=memory.minutes_since_last_event(now),
            conversation_active=human_recent,
        )


class SocialActivityService:
    """Build social context from existing member data without an LLM."""

    ACTIVE_WINDOW_MINUTES = 10

    async def observe(
        self,
        session: AsyncSession,
        chat_id: int,
        *,
        now: datetime | None = None,
    ) -> SocialActivity:
        observed_at = now or utc_now()
        since = observed_at - timedelta(minutes=self.ACTIVE_WINDOW_MINUTES)

        active_users = await session.scalar(
            select(func.count(UserChat.user_id))
            .join(User, User.id == UserChat.user_id)
            .where(
                UserChat.chat_id == chat_id,
                User.is_bot.is_(False),
                UserChat.last_seen_at >= since,
            )
        ) or 0

        last_human_message_at = await session.scalar(
            select(func.max(UserChat.last_seen_at))
            .join(User, User.id == UserChat.user_id)
            .where(
                UserChat.chat_id == chat_id,
                User.is_bot.is_(False),
            )
        )

        # UserChat has no rolling message history. Use the latest human
        # activity and active-user count rather than Chat.last_seen_at, which
        # is shared by human and bot Telegram events.
        recent_messages = min(int(active_users), 8)
        return SocialActivity(
            chat_id=chat_id,
            recent_messages=recent_messages,
            active_users=int(active_users),
            last_human_message_at=last_human_message_at,
            observed_at=observed_at,
        )


def fatigue_map_from_presence(values: dict[BotIdentity, int]) -> dict[BotIdentity, int]:
    """Copy a presence-derived fatigue map before passing it to the director."""
    return dict(values)
