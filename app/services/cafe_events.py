from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import CafeDailyEventRound


@dataclass(frozen=True, slots=True)
class CafeDailyEvent:
    key: str
    title: str
    text: str


CAFE_DAILY_EVENTS: tuple[CafeDailyEvent, ...] = (
    CafeDailyEvent(
        "morning-cleanup",
        "Una mañana tranquila",
        "Cari decidió ordenar una mesa antes de abrir del todo. Cami dejó una ficha cerca para comprobar si todo quedó en su sitio.",
    ),
    CafeDailyEvent(
        "game-break",
        "Pausa de juegos",
        "Sunna dejó una partida a medias y se quedó mirando el mostrador un momento antes de volver a la zona de juegos.",
    ),
    CafeDailyEvent(
        "archive-note",
        "Una nota en el archivo",
        "Cami encontró una nota sin importancia narrativa entre dos fichas de trabajo y decidió archivarla para revisarla más tarde.",
    ),
    CafeDailyEvent(
        "reception-quiet",
        "Recepción en silencio",
        "Chie terminó una lista de avisos antes de tiempo. Durante unos minutos, la recepción quedó completamente tranquila.",
    ),
    CafeDailyEvent(
        "shared-table",
        "Mesa compartida",
        "Hoy una mesa del Café queda especialmente cómoda para quedarse un rato y charlar sin prisa.",
    ),
)


@dataclass(frozen=True, slots=True)
class CafeDailyEventStart:
    round: CafeDailyEventRound
    event: CafeDailyEvent
    created: bool


class CafeEventService:
    """Persistent daily Café events; content is authored and explicitly non-canonical."""

    def event_for(self, day_key: str, chat_id: int) -> CafeDailyEvent:
        if not day_key.strip():
            raise ValueError("day_key must not be empty")
        if not CAFE_DAILY_EVENTS:
            raise RuntimeError("No Café daily events configured")
        digest = hashlib.sha256(f"{day_key}:{chat_id}".encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(CAFE_DAILY_EVENTS)
        return CAFE_DAILY_EVENTS[index]

    async def start_event(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        day_key: str,
    ) -> CafeDailyEventStart:
        event = self.event_for(day_key, chat_id)
        existing = await session.scalar(
            select(CafeDailyEventRound).where(
                CafeDailyEventRound.chat_id == chat_id,
                CafeDailyEventRound.day_key == day_key,
            )
        )
        if existing is not None:
            return CafeDailyEventStart(existing, event, False)

        row = CafeDailyEventRound(
            chat_id=chat_id,
            day_key=day_key,
            event_key=event.key,
            title=event.title,
            text=event.text,
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(row)
        try:
            async with session.begin_nested():
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(CafeDailyEventRound).where(
                    CafeDailyEventRound.chat_id == chat_id,
                    CafeDailyEventRound.day_key == day_key,
                )
            )
            if existing is None:
                raise
            return CafeDailyEventStart(existing, event, False)

        return CafeDailyEventStart(row, event, True)

    async def mark_published(
        self,
        session: AsyncSession,
        *,
        round_id: int,
        message_id: int,
    ) -> CafeDailyEventRound | None:
        row = await session.get(CafeDailyEventRound, round_id)
        if row is None:
            return None
        if row.status not in {"active", "published"}:
            return row
        if row.message_id is None:
            row.message_id = message_id
        row.status = "published"
        row.updated_at = utc_now()
        await session.flush()
        return row

    async def expire_old(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        now: datetime | None = None,
    ) -> int:
        """Retire stale active rows older than one day if a clock-based cleanup is requested."""
        cutoff = (now or utc_now()) - timedelta(days=1)
        rows = list(
            await session.scalars(
                select(CafeDailyEventRound).where(
                    CafeDailyEventRound.chat_id == chat_id,
                    CafeDailyEventRound.status == "active",
                    CafeDailyEventRound.created_at < cutoff,
                )
            )
        )
        for row in rows:
            row.status = "expired"
            row.updated_at = utc_now()
        return len(rows)
