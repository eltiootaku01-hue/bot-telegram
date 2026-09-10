from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DomainEvent


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_type: str
    payload: dict


class EventBus:
    """Durable event inbox shared by Cari, Sunna, Cami and Chie.

    Publishing is persisted before any consumer acts. Consumers can therefore
    recover after a process restart instead of depending on in-memory callbacks.
    """

    async def publish(
        self,
        session: AsyncSession,
        event_type: str,
        payload: dict,
        *,
        event_id: str | None = None,
    ) -> EventEnvelope:
        envelope = EventEnvelope(event_id or uuid.uuid4().hex, event_type, payload)
        event = DomainEvent(
            event_id=envelope.event_id,
            event_type=event_type,
            payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
        session.add(event)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(DomainEvent).where(DomainEvent.event_id == envelope.event_id)
            )
            if existing is None:
                raise
            return EventEnvelope(
                event_id=existing.event_id,
                event_type=existing.event_type,
                payload=json.loads(existing.payload),
            )
        return envelope

    async def claim(
        self,
        session: AsyncSession,
        *,
        event_type: str | None = None,
        now: datetime | None = None,
    ) -> DomainEvent | None:
        """Atomically claim one pending event for a worker.

        SQLite has no SELECT ... FOR UPDATE, so claiming uses a conditional UPDATE.
        Only the worker whose UPDATE affects one row owns the event.
        """
        now = now or datetime.utcnow()
        query = select(DomainEvent).where(
            DomainEvent.status == "pending",
            DomainEvent.available_at <= now,
        )
        if event_type is not None:
            query = query.where(DomainEvent.event_type == event_type)
        candidate = await session.scalar(query.order_by(DomainEvent.id.asc()).limit(1))
        if candidate is None:
            return None

        result = await session.execute(
            update(DomainEvent)
            .where(DomainEvent.id == candidate.id, DomainEvent.status == "pending")
            .values(
                status="processing",
                attempts=DomainEvent.attempts + 1,
                locked_at=now,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            await session.rollback()
            return None
        await session.commit()
        await session.refresh(candidate)
        return candidate

    async def complete(self, session: AsyncSession, event_id: str) -> None:
        now = datetime.utcnow()
        await session.execute(
            update(DomainEvent)
            .where(DomainEvent.event_id == event_id)
            .values(status="completed", completed_at=now, updated_at=now)
        )
        await session.commit()

    async def fail(
        self,
        session: AsyncSession,
        event_id: str,
        error: str,
        *,
        retry_at: datetime | None = None,
    ) -> None:
        now = datetime.utcnow()
        await session.execute(
            update(DomainEvent)
            .where(DomainEvent.event_id == event_id)
            .values(
                status="pending" if retry_at else "failed",
                available_at=retry_at or now,
                locked_at=None,
                last_error=error[:4000],
                updated_at=now,
            )
        )
        await session.commit()
