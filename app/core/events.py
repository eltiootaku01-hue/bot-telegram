from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DomainEvent


DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_SECONDS = (5, 30, 120, 600, 1800)


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_type: str
    payload: dict


class EventBus:
    """Durable event inbox shared by Cari, Sunna, Cami and Chie."""

    async def publish(
        self,
        session: AsyncSession,
        event_type: str,
        payload: dict,
        *,
        event_id: str | None = None,
        commit: bool = True,
    ) -> EventEnvelope:
        """Publish an event, optionally making it part of the caller's transaction."""
        envelope = EventEnvelope(event_id or uuid.uuid4().hex, event_type, payload)
        event = DomainEvent(
            event_id=envelope.event_id,
            event_type=event_type,
            payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
        session.add(event)
        try:
            if commit:
                await session.commit()
            else:
                async with session.begin_nested():
                    await session.flush()
        except IntegrityError:
            if commit:
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

    async def recover_stale(
        self,
        session: AsyncSession,
        *,
        event_type: str | None = None,
        timeout_seconds: int = 300,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> int:
        """Recover events abandoned by a crashed worker."""
        cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        now = datetime.utcnow()
        query = select(DomainEvent).where(
            DomainEvent.status == "processing",
            DomainEvent.locked_at.is_not(None),
            DomainEvent.locked_at < cutoff,
        )
        if event_type is not None:
            query = query.where(DomainEvent.event_type == event_type)
        result = await session.scalars(query)
        events = list(result)
        for event in events:
            if event.attempts >= max_attempts:
                event.status = "failed"
                event.last_error = "Event abandoned after maximum recovery attempts"
            else:
                delay = DEFAULT_BACKOFF_SECONDS[min(event.attempts, len(DEFAULT_BACKOFF_SECONDS) - 1)]
                event.status = "pending"
                event.available_at = now + timedelta(seconds=delay)
                event.last_error = "Recovered stale processing event"
            event.locked_at = None
            event.updated_at = now
        if events:
            await session.commit()
        return len(events)

    async def claim(
        self,
        session: AsyncSession,
        *,
        event_type: str | None = None,
        now: datetime | None = None,
    ) -> DomainEvent | None:
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

    async def complete(
        self,
        session: AsyncSession,
        event_id: str,
        *,
        lock_time: datetime | None = None,
    ) -> bool:
        """Complete only the claim that currently owns the event lease."""
        now = datetime.utcnow()
        conditions = [DomainEvent.event_id == event_id, DomainEvent.status == "processing"]
        if lock_time is not None:
            conditions.append(DomainEvent.locked_at == lock_time)
        result = await session.execute(
            update(DomainEvent)
            .where(*conditions)
            .values(status="completed", completed_at=now, updated_at=now)
        )
        await session.commit()
        return result.rowcount == 1

    async def fail(
        self,
        session: AsyncSession,
        event_id: str,
        error: str,
        *,
        lock_time: datetime | None = None,
        retry_at: datetime | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> bool:
        now = datetime.utcnow()
        event = await session.scalar(select(DomainEvent).where(DomainEvent.event_id == event_id))
        if event is None:
            return False
        if lock_time is not None and (event.status != "processing" or event.locked_at != lock_time):
            return False
        if retry_at is None and event.attempts < max_attempts:
            delay = DEFAULT_BACKOFF_SECONDS[min(event.attempts, len(DEFAULT_BACKOFF_SECONDS) - 1)]
            retry_at = now + timedelta(seconds=delay)
        permanent = event.attempts >= max_attempts and retry_at is None
        conditions = [DomainEvent.event_id == event_id, DomainEvent.status == "processing"]
        if lock_time is not None:
            conditions.append(DomainEvent.locked_at == lock_time)
        result = await session.execute(
            update(DomainEvent)
            .where(*conditions)
            .values(
                status="failed" if permanent else "pending",
                available_at=retry_at or now,
                locked_at=None,
                last_error=error[:4000],
                updated_at=now,
            )
        )
        await session.commit()
        return result.rowcount == 1
