from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import GameDailyMissionCredit, GameDailyMissionProgress
from app.db.repositories import MemberRepository


@dataclass(frozen=True, slots=True)
class DailyMissionDefinition:
    key: str
    label: str
    target: int
    reward_points: int
    action: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("mission key must not be empty")
        if self.target <= 0:
            raise ValueError("mission target must be positive")
        if self.reward_points < 0:
            raise ValueError("mission reward cannot be negative")


DAILY_MISSIONS: tuple[DailyMissionDefinition, ...] = (
    DailyMissionDefinition(
        "capture_waifu",
        "Capturá una waifu en WaifuMon",
        1,
        20,
        "encounter.capture",
    ),
    DailyMissionDefinition(
        "trivia_participation",
        "Respondé dos trivias",
        2,
        25,
        "trivia.answer",
    ),
    DailyMissionDefinition(
        "gacha_roll",
        "Hacé una tirada de gacha",
        1,
        10,
        "gacha.roll",
    ),
)


def mission_for(key: str) -> DailyMissionDefinition:
    for mission in DAILY_MISSIONS:
        if mission.key == key:
            return mission
    raise KeyError(key)


@dataclass(frozen=True, slots=True)
class MissionProgressSnapshot:
    progress: int
    target: int
    claimed: bool


class DailyMissionService:
    """Deterministic daily missions with action-level dedupe and one-time rewards."""

    @staticmethod
    def day_key(now: datetime | None = None, timezone_name: str = "UTC") -> str:
        from app.core.time import localize_utc

        return localize_utc(now or utc_now(), timezone_name).date().isoformat()

    async def _ensure_progress(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        day_key: str,
        mission: DailyMissionDefinition,
    ) -> GameDailyMissionProgress:
        row = await session.scalar(
            select(GameDailyMissionProgress).where(
                GameDailyMissionProgress.user_id == user_id,
                GameDailyMissionProgress.chat_id == chat_id,
                GameDailyMissionProgress.day_key == day_key,
                GameDailyMissionProgress.mission_key == mission.key,
            )
        )
        if row is not None:
            return row

        row = GameDailyMissionProgress(
            user_id=user_id,
            chat_id=chat_id,
            day_key=day_key,
            mission_key=mission.key,
            target=mission.target,
            progress=0,
            claimed=False,
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            row = await session.scalar(
                select(GameDailyMissionProgress).where(
                    GameDailyMissionProgress.user_id == user_id,
                    GameDailyMissionProgress.chat_id == chat_id,
                    GameDailyMissionProgress.day_key == day_key,
                    GameDailyMissionProgress.mission_key == mission.key,
                )
            )
            if row is None:
                raise
        return row

    async def record(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        day_key: str,
        mission_key: str,
        reference_type: str,
        reference_id: str,
    ) -> GameDailyMissionProgress:
        mission = mission_for(mission_key)
        if not reference_type.strip() or not reference_id.strip():
            raise ValueError("mission reference must not be empty")

        credit = GameDailyMissionCredit(
            user_id=user_id,
            chat_id=chat_id,
            day_key=day_key,
            mission_key=mission.key,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        try:
            async with session.begin_nested():
                session.add(credit)
                await session.flush()
        except IntegrityError:
            row = await self._ensure_progress(
                session,
                user_id=user_id,
                chat_id=chat_id,
                day_key=day_key,
                mission=mission,
            )
            return MissionProgressSnapshot(
                progress=row.progress,
                target=row.target,
                claimed=row.claimed,
            )

        row = await self._ensure_progress(
            session,
            user_id=user_id,
            chat_id=chat_id,
            day_key=day_key,
            mission=mission,
        )
        await session.execute(
            update(GameDailyMissionProgress)
            .where(
                GameDailyMissionProgress.id == row.id,
                GameDailyMissionProgress.progress < mission.target,
            )
            .values(
                progress=GameDailyMissionProgress.progress + 1,
                updated_at=utc_now(),
            )
        )
        await session.refresh(row)
        return MissionProgressSnapshot(
            progress=row.progress,
            target=row.target,
            claimed=row.claimed,
        )

    async def claim(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        day_key: str,
        mission_key: str,
    ) -> tuple[bool, int]:
        mission = mission_for(mission_key)
        row = await self._ensure_progress(
            session,
            user_id=user_id,
            chat_id=chat_id,
            day_key=day_key,
            mission=mission,
        )
        claimed = await session.execute(
            update(GameDailyMissionProgress)
            .where(
                GameDailyMissionProgress.id == row.id,
                GameDailyMissionProgress.progress >= mission.target,
                GameDailyMissionProgress.claimed.is_(False),
            )
            .values(claimed=True, updated_at=utc_now())
        )
        if claimed.rowcount != 1:
            return False, 0

        balance = await MemberRepository().add_points(
            session,
            user_id=user_id,
            chat_id=chat_id,
            amount=mission.reward_points,
            reason=f"Misión diaria: {mission.label}",
            reference_type="mission",
            reference_id=f"{day_key}:{mission.key}",
            commit=False,
        )
        return True, balance

    async def list_progress(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        day_key: str,
    ) -> tuple[tuple[DailyMissionDefinition, GameDailyMissionProgress], ...]:
        rows = {
            row.mission_key: row
            for row in await session.scalars(
                select(GameDailyMissionProgress).where(
                    GameDailyMissionProgress.user_id == user_id,
                    GameDailyMissionProgress.chat_id == chat_id,
                    GameDailyMissionProgress.day_key == day_key,
                )
            )
        }
        result: list[tuple[DailyMissionDefinition, GameDailyMissionProgress]] = []
        for mission in DAILY_MISSIONS:
            row = rows.get(mission.key)
            if row is None:
                row = await self._ensure_progress(
                    session,
                    user_id=user_id,
                    chat_id=chat_id,
                    day_key=day_key,
                    mission=mission,
                )
            result.append((mission, row))
        return tuple(result)
