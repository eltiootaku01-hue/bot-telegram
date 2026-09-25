from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.community_models import SetupSession
from app.db.models import UserChat


class CommunityResolver:
    """Resolve private-user actions only to currently authorized communities."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _allowed(self, chat_id: int) -> bool:
        return chat_id in self.settings.authorized_chat_ids_set

    async def for_user(self, session: AsyncSession, user_id: int) -> int | None:
        """Prefer the most recently seen configured community for this user."""
        memberships = await session.execute(
            select(SetupSession.chat_id)
            .join(UserChat, UserChat.chat_id == SetupSession.chat_id)
            .where(
                SetupSession.bot_identity == "chie",
                SetupSession.status == "configured",
                UserChat.user_id == user_id,
                UserChat.status.in_(("member", "administrator", "creator")),
            )
            .order_by(UserChat.last_seen_at.desc(), SetupSession.id.desc())
        )
        for chat_id in memberships.scalars():
            chat_id = int(chat_id)
            if self._allowed(chat_id):
                return chat_id

        configured = list(
            await session.scalars(
                select(SetupSession.chat_id)
                .where(
                    SetupSession.bot_identity == "chie",
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
            )
        )
        configured = [int(chat_id) for chat_id in dict.fromkeys(configured)]
        if len(configured) == 1 and self._allowed(configured[0]):
            return configured[0]
        return None

    async def configured(self, session: AsyncSession) -> list[int]:
        """Return every configured Chie community that is still authorized."""
        rows = await session.scalars(
            select(SetupSession.chat_id)
            .where(
                SetupSession.bot_identity == "chie",
                SetupSession.status == "configured",
            )
            .order_by(SetupSession.id.asc())
        )
        return list(dict.fromkeys(
            int(chat_id)
            for chat_id in rows
            if self._allowed(int(chat_id))
        ))
