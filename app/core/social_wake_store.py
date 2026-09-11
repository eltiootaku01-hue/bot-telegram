from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.social_wake import SocialWakeState, WakeReason
from app.core.time import utc_now
from app.db.social_models import SocialWake, SocialWakeReason


class SocialWakeStore:
    """Persist the social wake state without turning the heartbeat into polling.

    The controller remains pure and cheap; this store makes the next opportunity
    survive process restarts and lets all four bot processes observe the same
    chat-level social sleep state.
    """

    async def get_or_create(
        self,
        session: AsyncSession,
        chat_id: int,
        default: SocialWakeState,
        *,
        commit: bool = True,
    ) -> SocialWakeState:
        row = await session.scalar(select(SocialWake).where(SocialWake.chat_id == chat_id))
        if row is None:
            row = SocialWake(
                chat_id=chat_id,
                next_wake_at=default.next_wake_at,
                cooldown_until=default.cooldown_until,
                pending_reason=default.pending_reason.value if default.pending_reason else None,
                consecutive_silences=default.consecutive_silences,
                updated_at=utc_now(),
            )
            session.add(row)
            await session.flush()
        if commit:
            await session.commit()
        return self._state(row)

    async def save(
        self,
        session: AsyncSession,
        chat_id: int,
        state: SocialWakeState,
        *,
        commit: bool = True,
    ) -> SocialWakeState:
        row = await session.scalar(select(SocialWake).where(SocialWake.chat_id == chat_id))
        if row is None:
            row = SocialWake(chat_id=chat_id)
            session.add(row)
        row.next_wake_at = state.next_wake_at
        row.cooldown_until = state.cooldown_until
        row.pending_reason = state.pending_reason.value if state.pending_reason else None
        row.consecutive_silences = state.consecutive_silences
        row.updated_at = utc_now()
        if commit:
            await session.commit()
        return self._state(row)

    async def request_wake(
        self,
        session: AsyncSession,
        chat_id: int,
        now: datetime,
        *,
        reason: WakeReason = WakeReason.EVENT,
        commit: bool = True,
    ) -> SocialWakeState | None:
        row = await session.scalar(select(SocialWake).where(SocialWake.chat_id == chat_id))
        if row is None:
            return None
        if row.cooldown_until and now < row.cooldown_until:
            return self._state(row)
        if now < row.next_wake_at:
            row.next_wake_at = now
        row.pending_reason = reason.value
        row.updated_at = now
        if commit:
            await session.commit()
        return self._state(row)

    @staticmethod
    def _state(row: SocialWake) -> SocialWakeState:
        reason = WakeReason(row.pending_reason) if row.pending_reason else None
        return SocialWakeState(
            next_wake_at=row.next_wake_at,
            cooldown_until=row.cooldown_until,
            pending_reason=reason,
            consecutive_silences=row.consecutive_silences,
        )
