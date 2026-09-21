from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import GameCollection, GameProfile, User, WaifuDetectorDailyUsage, WaifuDetectorRound
from app.game.models import Rarity
from app.game.progression import add_collection_experience


MAX_DAILY_DETECTOR_USES = 3
DETECTOR_ROUND_SECONDS = 120


@dataclass(frozen=True, slots=True)
class DetectorMob:
    key: str
    name: str
    power: int
    reward_experience: int


DETECTOR_MOBS: tuple[DetectorMob, ...] = (
    DetectorMob("slime", "Gelatina Otaku", 15, 45),
    DetectorMob("mimic", "Mímico de Cartas", 25, 60),
    DetectorMob("bat", "Murciélago de Neón", 35, 80),
    DetectorMob("golem", "Gólem de Consola", 45, 105),
)


@dataclass(frozen=True, slots=True)
class DetectorStart:
    round: WaifuDetectorRound
    mob: DetectorMob
    use_number: int


class WaifuDetectorService:
    """Three daily deterministic mob fights with one irreversible fight per round."""

    MAX_DAILY_USES = MAX_DAILY_DETECTOR_USES

    @classmethod
    def _mob_for(cls, user_id: int, chat_id: int, day_key: str, use_number: int) -> DetectorMob:
        digest = hashlib.sha256(
            f"{user_id}:{chat_id}:{day_key}:{use_number}".encode("utf-8")
        ).digest()
        return DETECTOR_MOBS[int.from_bytes(digest[:8], "big") % len(DETECTOR_MOBS)]

    @staticmethod
    def _player_power(collection: GameCollection) -> int:
        rarity_bonus = {
            Rarity.D.value: 0,
            Rarity.C.value: 5,
            Rarity.B.value: 10,
            Rarity.A.value: 18,
            Rarity.S.value: 28,
            Rarity.SS.value: 40,
            Rarity.SSS.value: 55,
        }.get(collection.rarity, 0)
        return collection.level * 3 + rarity_bonus + collection.evolution_stage * 5

    async def start(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        day_key: str,
        character_id: str,
    ) -> DetectorStart | None:
        profile = await session.scalar(
            select(GameProfile).where(
                GameProfile.user_id == user_id,
                GameProfile.chat_id == chat_id,
            )
        )
        if profile is None:
            return None

        character = await session.scalar(
            select(GameCollection).where(
                GameCollection.profile_id == profile.id,
                GameCollection.character_id == character_id,
            )
        )
        if character is None:
            return None

        usage = await session.scalar(
            select(WaifuDetectorDailyUsage).where(
                WaifuDetectorDailyUsage.user_id == user_id,
                WaifuDetectorDailyUsage.chat_id == chat_id,
                WaifuDetectorDailyUsage.day_key == day_key,
            )
        )
        if usage is None:
            usage = WaifuDetectorDailyUsage(
                user_id=user_id,
                chat_id=chat_id,
                day_key=day_key,
                uses=0,
            )
            try:
                async with session.begin_nested():
                    session.add(usage)
                    await session.flush()
            except IntegrityError:
                usage = await session.scalar(
                    select(WaifuDetectorDailyUsage).where(
                        WaifuDetectorDailyUsage.user_id == user_id,
                        WaifuDetectorDailyUsage.chat_id == chat_id,
                        WaifuDetectorDailyUsage.day_key == day_key,
                    )
                )
                if usage is None:
                    raise

        claimed = await session.execute(
            update(WaifuDetectorDailyUsage)
            .where(
                WaifuDetectorDailyUsage.id == usage.id,
                WaifuDetectorDailyUsage.uses < MAX_DAILY_DETECTOR_USES,
            )
            .values(uses=WaifuDetectorDailyUsage.uses + 1)
        )
        if claimed.rowcount != 1:
            return None

        await session.refresh(usage)
        use_number = usage.uses
        mob = self._mob_for(user_id, chat_id, day_key, use_number)
        row = WaifuDetectorRound(
            user_id=user_id,
            chat_id=chat_id,
            day_key=day_key,
            use_number=use_number,
            character_id=character_id,
            mob_key=mob.key,
            status="active",
            expires_at=utc_now() + timedelta(seconds=DETECTOR_ROUND_SECONDS),
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            return None
        return DetectorStart(round=row, mob=mob, use_number=use_number)

    async def fight(
        self,
        session: AsyncSession,
        *,
        round_id: int,
        user_id: int,
        chat_id: int,
    ) -> tuple[str, int, GameCollection | None, DetectorMob | None]:
        row = await session.get(WaifuDetectorRound, round_id)
        if row is None or row.user_id != user_id or row.chat_id != chat_id:
            return "invalid", 0, None, None
        mob = next((mob for mob in DETECTOR_MOBS if mob.key == row.mob_key), None)
        if mob is None:
            return "invalid", 0, None, None
        if row.status != "active" or row.expires_at <= utc_now():
            if row.status == "active":
                row.status = "expired"
            return "expired", 0, None, mob

        won = await session.execute(
            update(WaifuDetectorRound)
            .where(
                WaifuDetectorRound.id == round_id,
                WaifuDetectorRound.user_id == user_id,
                WaifuDetectorRound.chat_id == chat_id,
                WaifuDetectorRound.status == "active",
                WaifuDetectorRound.expires_at > utc_now(),
            )
            .values(status="won", result="won", finished_at=utc_now())
        )
        if won.rowcount != 1:
            return "already_fought", 0, None, mob

        collection = await session.scalar(
            select(GameCollection)
            .join(GameProfile, GameProfile.id == GameCollection.profile_id)
            .where(
                GameProfile.user_id == user_id,
                GameProfile.chat_id == chat_id,
                GameCollection.character_id == row.character_id,
            )
        )
        if collection is None:
            row.status = "invalid"
            row.result = "missing_collection"
            return "invalid", 0, None, mob

        power = self._player_power(collection)
        threshold = mob.power
        if power < threshold:
            row.status = "lost"
            row.result = "lost"
            row.finished_at = utc_now()
            return "lost", power, collection, mob

        progress = add_collection_experience(
            level=collection.level,
            experience=collection.experience,
            evolution_stage=collection.evolution_stage,
            gained=mob.reward_experience,
            copies=collection.copies,
        )
        collection.level = progress.level
        collection.experience = progress.experience
        row.finished_at = utc_now()
        row.result = "won"
        await session.flush()
        return "won", progress.level, collection, mob
