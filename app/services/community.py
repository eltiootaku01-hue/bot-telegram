from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.community_models import SetupSession
from app.db.models import UserChat


class CommunityResolver:
    """Resolve private-user actions to a community the user actually belongs to."""

    async def for_user(self, session: AsyncSession, user_id: int) -> int | None:
        """Prefer the most recently seen configured community for this user.

        When only one configured community exists, it is used as the initial
        default so a new private user can open Sunna before sending a group
        message. With multiple communities, membership is required to avoid
        assigning points or collections to another community.
        """
        membership = await session.scalar(
            select(SetupSession.chat_id)
            .join(
                UserChat,
                UserChat.chat_id == SetupSession.chat_id,
            )
            .where(
                SetupSession.bot_identity == "chie",
                SetupSession.status == "configured",
                UserChat.user_id == user_id,
                UserChat.status.in_(("member", "administrator", "creator")),
            )
            .order_by(UserChat.last_seen_at.desc(), SetupSession.id.desc())
            .limit(1)
        )
        if membership is not None:
            return int(membership)

        configured = list(
            await session.scalars(
                select(SetupSession.chat_id)
                .where(
                    SetupSession.bot_identity == "chie",
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
                .limit(2)
            )
        )
        if len(configured) == 1:
            return int(configured[0])
        return None
