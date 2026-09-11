from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.core.jobs import JobQueue
from app.core.time import utc_now
from app.db.models import DurableJob


SOCIAL_TURN_JOB = "social.turn"


@dataclass(frozen=True, slots=True)
class SocialTurnLease:
    """Exclusive social-turn lease shared by all bot processes."""

    job_id: int
    chat_id: int
    window_key: str
    bot_identity: BotIdentity
    lock_time: datetime


class SocialTurnArbiter:
    """Use the durable SQLite queue as a cross-process speaking lock.

    Every eligible bot may race for the same `(chat, window)` key. SQLite's
    atomic job claim guarantees that only one process obtains the turn. Losing
    the race is intentionally a valid outcome: the group does not need a bot
    reply every time an opportunity appears.
    """

    def __init__(self, queue: JobQueue | None = None) -> None:
        self.queue = queue or JobQueue()

    async def acquire(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        window_key: str,
        identity: BotIdentity,
    ) -> SocialTurnLease | None:
        dedupe_key = f"social-turn:{chat_id}:{window_key}"
        await self.queue.enqueue(
            session,
            SOCIAL_TURN_JOB,
            {"chat_id": chat_id, "window_key": window_key},
            dedupe_key=dedupe_key,
            run_at=utc_now(),
            commit=True,
        )
        job = await self.queue.claim(session, job_type=SOCIAL_TURN_JOB)
        if job is None or job.dedupe_key != dedupe_key:
            return None
        return SocialTurnLease(
            job_id=job.id,
            chat_id=chat_id,
            window_key=window_key,
            bot_identity=identity,
            lock_time=job.locked_at,
        )

    async def complete(self, session: AsyncSession, lease: SocialTurnLease) -> bool:
        return await self.queue.complete(session, lease.job_id, lock_time=lease.lock_time)

    async def abandon(self, session: AsyncSession, lease: SocialTurnLease, reason: str) -> bool:
        return await self.queue.fail(
            session,
            lease.job_id,
            reason,
            lock_time=lease.lock_time,
            retry_at=utc_now(),
        )


def social_window_key(now: datetime | None = None) -> str:
    """Return a deterministic minute bucket for coalescing competing wakeups."""
    value = now or utc_now()
    return value.strftime("%Y%m%d%H%M")
