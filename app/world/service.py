from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.world_models import GameWorldEvent
from app.world.models import (
    PresenterKind,
    WorldEventEnvelope,
    WorldEventStatus,
    WorldEventType,
    WorldPresenterRef,
)


class WorldEventService:
    """Persistence boundary for the independent game-world event stream."""

    async def schedule(
        self,
        session: AsyncSession,
        *,
        event_key: str,
        event_type: WorldEventType,
        chat_id: int,
        presenter: WorldPresenterRef,
        title: str,
        payload: dict[str, object],
        dedupe_key: str,
        run_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> GameWorldEvent:
        self._validate_schedule(
            event_key=event_key,
            chat_id=chat_id,
            title=title,
            dedupe_key=dedupe_key,
        )
        if expires_at is not None and run_at is not None and expires_at <= run_at:
            raise ValueError("world event expires_at must be after run_at")

        row = GameWorldEvent(
            event_key=event_key.strip(),
            event_type=event_type.value,
            dedupe_key=dedupe_key.strip(),
            chat_id=chat_id,
            presenter_key=f"{presenter.kind.value}:{presenter.key.strip()}",
            title=title.strip(),
            payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            status=WorldEventStatus.PENDING.value,
            run_at=run_at or utc_now(),
            expires_at=expires_at,
            attempts=0,
            last_error=None,
            updated_at=utc_now(),
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(GameWorldEvent).where(
                    GameWorldEvent.dedupe_key == dedupe_key.strip()
                )
            )
            if existing is None:
                raise
            return existing
        return row

    async def schedule_game_news(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        presenter: WorldPresenterRef,
        title: str,
        text: str,
        dedupe_key: str,
        run_at: datetime | None = None,
    ) -> GameWorldEvent:
        return await self.schedule(
            session,
            event_key="game-news",
            event_type=WorldEventType.GAME_NEWS,
            chat_id=chat_id,
            presenter=presenter,
            title=title,
            payload={"text": text},
            dedupe_key=dedupe_key,
            run_at=run_at,
        )

    async def schedule_reward_notice(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        presenter: WorldPresenterRef,
        title: str,
        text: str,
        reward_key: str,
        dedupe_key: str,
        run_at: datetime | None = None,
    ) -> GameWorldEvent:
        return await self.schedule(
            session,
            event_key=reward_key,
            event_type=WorldEventType.REWARD_NOTICE,
            chat_id=chat_id,
            presenter=presenter,
            title=title,
            payload={"text": text, "reward_key": reward_key},
            dedupe_key=dedupe_key,
            run_at=run_at,
        )

    async def schedule_waifu_arrival(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        presenter: WorldPresenterRef,
        encounter_id: str,
        character_id: str,
        character_name: str,
        text: str,
        dedupe_key: str,
        run_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> GameWorldEvent:
        return await self.schedule(
            session,
            event_key=f"waifu-arrival:{encounter_id}",
            event_type=WorldEventType.WAIFU_ARRIVAL,
            chat_id=chat_id,
            presenter=presenter,
            title=f"🚨 ¡Apareció {character_name}!",
            payload={
                "text": text,
                "encounter_id": encounter_id,
                "character_id": character_id,
                "character_name": character_name,
            },
            dedupe_key=dedupe_key,
            run_at=run_at,
            expires_at=expires_at,
        )

    async def schedule_mystery_clue(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        presenter: WorldPresenterRef,
        round_id: int,
        clue_number: int,
        clue_text: str,
        dedupe_key: str,
        run_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> GameWorldEvent:
        if clue_number <= 0:
            raise ValueError("clue_number must be positive")
        return await self.schedule(
            session,
            event_key=f"mystery-clue:{round_id}:{clue_number}",
            event_type=WorldEventType.MYSTERY_CLUE,
            chat_id=chat_id,
            presenter=presenter,
            title=f"🕵️ Pista #{clue_number}",
            payload={
                "text": clue_text,
                "round_id": round_id,
                "clue_number": clue_number,
            },
            dedupe_key=dedupe_key,
            run_at=run_at,
            expires_at=expires_at,
        )

    async def get(self, session: AsyncSession, event_id: int) -> GameWorldEvent | None:
        return await session.get(GameWorldEvent, event_id)

    async def claim_due(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
    ) -> WorldEventEnvelope | None:
        """Claim exactly one due event and return its fenced immutable envelope."""
        current = now or utc_now()
        while True:
            candidate = await session.scalar(
                select(GameWorldEvent)
                .where(
                    GameWorldEvent.status == WorldEventStatus.PENDING.value,
                    GameWorldEvent.run_at <= current,
                    (
                        GameWorldEvent.expires_at.is_(None)
                        | (GameWorldEvent.expires_at > current)
                    ),
                )
                .order_by(GameWorldEvent.id.asc())
                .limit(1)
            )
            if candidate is None:
                return None

            result = await session.execute(
                update(GameWorldEvent)
                .where(
                    GameWorldEvent.id == candidate.id,
                    GameWorldEvent.status == WorldEventStatus.PENDING.value,
                    GameWorldEvent.run_at <= current,
                    (
                        GameWorldEvent.expires_at.is_(None)
                        | (GameWorldEvent.expires_at > current)
                    ),
                )
                .values(
                    status=WorldEventStatus.PUBLISHING.value,
                    locked_at=current,
                    heartbeat_at=current,
                    attempts=GameWorldEvent.attempts + 1,
                    updated_at=current,
                )
            )
            if result.rowcount != 1:
                return None

            candidate.status = WorldEventStatus.PUBLISHING.value
            candidate.locked_at = current
            candidate.heartbeat_at = current
            await session.commit()
            return self._envelope(candidate)

    async def renew(
        self,
        session: AsyncSession,
        *,
        event_id: int,
        lock_time: datetime,
    ) -> bool:
        now = utc_now()
        result = await session.execute(
            update(GameWorldEvent)
            .where(
                GameWorldEvent.id == event_id,
                GameWorldEvent.status == WorldEventStatus.PUBLISHING.value,
                GameWorldEvent.locked_at == lock_time,
            )
            .values(heartbeat_at=now, updated_at=now)
        )
        await session.commit()
        return result.rowcount == 1

    async def complete(
        self,
        session: AsyncSession,
        *,
        event_id: int,
        lock_time: datetime,
        message_id: int,
    ) -> bool:
        now = utc_now()
        result = await session.execute(
            update(GameWorldEvent)
            .where(
                GameWorldEvent.id == event_id,
                GameWorldEvent.status == WorldEventStatus.PUBLISHING.value,
                GameWorldEvent.locked_at == lock_time,
            )
            .values(
                status=WorldEventStatus.PUBLISHED.value,
                message_id=message_id,
                heartbeat_at=None,
                updated_at=now,
            )
        )
        await session.commit()
        return result.rowcount == 1

    async def mark_delivery_unknown(
        self,
        session: AsyncSession,
        *,
        event_id: int,
        lock_time: datetime,
        error: str,
    ) -> bool:
        now = utc_now()
        result = await session.execute(
            update(GameWorldEvent)
            .where(
                GameWorldEvent.id == event_id,
                GameWorldEvent.status == WorldEventStatus.PUBLISHING.value,
                GameWorldEvent.locked_at == lock_time,
            )
            .values(
                status=WorldEventStatus.DELIVERY_UNKNOWN.value,
                heartbeat_at=None,
                last_error=error[:4000],
                updated_at=now,
            )
        )
        await session.commit()
        return result.rowcount == 1

    async def cancel_event(
        self,
        session: AsyncSession,
        *,
        event_id: int,
        lock_time: datetime,
        reason: str,
    ) -> bool:
        now = utc_now()
        result = await session.execute(
            update(GameWorldEvent)
            .where(
                GameWorldEvent.id == event_id,
                GameWorldEvent.status == WorldEventStatus.PUBLISHING.value,
                GameWorldEvent.locked_at == lock_time,
            )
            .values(
                status=WorldEventStatus.CANCELLED.value,
                heartbeat_at=None,
                last_error=reason[:4000],
                updated_at=now,
            )
        )
        await session.commit()
        return result.rowcount == 1

    async def cancel_expired(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
    ) -> int:
        current = now or utc_now()
        result = await session.execute(
            update(GameWorldEvent)
            .where(
                GameWorldEvent.status == WorldEventStatus.PENDING.value,
                GameWorldEvent.expires_at.is_not(None),
                GameWorldEvent.expires_at <= current,
            )
            .values(
                status=WorldEventStatus.CANCELLED.value,
                updated_at=current,
            )
        )
        if result.rowcount:
            await session.commit()
        return int(result.rowcount or 0)

    async def recover_stale(
        self,
        session: AsyncSession,
        *,
        timeout_seconds: int = 300,
        now: datetime | None = None,
    ) -> int:
        """Fence stale recovery against a concurrent heartbeat renewal."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        current = now or utc_now()
        cutoff = current - timedelta(seconds=timeout_seconds)
        stale = list(
            await session.scalars(
                select(GameWorldEvent)
                .where(
                    GameWorldEvent.status == WorldEventStatus.PUBLISHING.value,
                    GameWorldEvent.heartbeat_at.is_not(None),
                    GameWorldEvent.heartbeat_at < cutoff,
                )
            )
        )
        recovered = 0
        for event in stale:
            result = await session.execute(
                update(GameWorldEvent)
                .where(
                    GameWorldEvent.id == event.id,
                    GameWorldEvent.status == WorldEventStatus.PUBLISHING.value,
                    GameWorldEvent.locked_at == event.locked_at,
                    GameWorldEvent.heartbeat_at == event.heartbeat_at,
                )
                .values(
                    status=WorldEventStatus.DELIVERY_UNKNOWN.value,
                    heartbeat_at=None,
                    last_error="World presentation lease expired; manual recovery required",
                    updated_at=current,
                )
            )
            recovered += int(result.rowcount == 1)
        if recovered:
            await session.commit()
        return recovered

    @staticmethod
    def _validate_schedule(
        *,
        event_key: str,
        chat_id: int,
        title: str,
        dedupe_key: str,
    ) -> None:
        if not event_key.strip():
            raise ValueError("event_key must not be empty")
        if chat_id >= 0:
            raise ValueError("world events require a group/supergroup chat id")
        if not title.strip():
            raise ValueError("world event title must not be empty")
        if not dedupe_key.strip():
            raise ValueError("world event dedupe key must not be empty")

    @staticmethod
    def _envelope(row: GameWorldEvent) -> WorldEventEnvelope:
        try:
            payload = json.loads(row.payload_json)
            if not isinstance(payload, dict):
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid world event payload #{row.id}") from exc

        presenter_raw = row.presenter_key.split(":", 1)
        if len(presenter_raw) != 2:
            raise RuntimeError(f"Invalid world presenter reference #{row.id}")
        if row.locked_at is None:
            raise RuntimeError(f"Claimed world event has no lock time #{row.id}")
        try:
            kind = PresenterKind(presenter_raw[0])
            event_type = WorldEventType(row.event_type)
            status = WorldEventStatus(row.status)
        except ValueError as exc:
            raise RuntimeError(f"Invalid world event enum #{row.id}") from exc

        return WorldEventEnvelope(
            event_id=row.id,
            event_key=row.event_key,
            event_type=event_type,
            chat_id=row.chat_id,
            presenter=WorldPresenterRef(key=presenter_raw[1], kind=kind),
            title=row.title,
            payload=payload,
            status=status,
            lock_time=row.locked_at,
        )
