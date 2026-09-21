from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import GameAttempt, GameEncounter


MAX_ENCOUNTER_PARTICIPANTS = 3


class EncounterStore:
    async def create(self, session: AsyncSession, encounter: GameEncounter) -> None:
        session.add(encounter)
        await session.flush()

    async def get(self, session: AsyncSession, encounter_id: str) -> GameEncounter | None:
        return await session.get(GameEncounter, encounter_id)

    async def claim_attempt(
        self,
        session: AsyncSession,
        encounter_id: str,
        user_id: int,
        answer: str,
    ) -> bool | None:
        """Record exactly one attempt per player and at most three players per encounter.

        The caller should use Database.session(write=True), whose SQLite transaction
        begins IMMEDIATE, so participant-count and attempt insertion are serialized.
        """
        encounter = await session.get(GameEncounter, encounter_id)
        if encounter is None or encounter.status != "active" or encounter.expires_at <= utc_now():
            return None

        existing = await session.scalar(
            select(GameAttempt.id).where(
                GameAttempt.encounter_id == encounter_id,
                GameAttempt.user_id == user_id,
            )
        )
        if existing is not None:
            return None

        participants = await session.scalar(
            select(func.count(GameAttempt.id)).where(
                GameAttempt.encounter_id == encounter_id,
            )
        )
        if (participants or 0) >= MAX_ENCOUNTER_PARTICIPANTS:
            return None

        attempt = GameAttempt(
            encounter_id=encounter_id,
            user_id=user_id,
            answer=answer,
            correct=answer.casefold().strip() == (encounter.answer or "").casefold().strip(),
        )
        try:
            async with session.begin_nested():
                session.add(attempt)
                await session.flush()
        except IntegrityError:
            return None
        return attempt.correct

    async def finish(self, session: AsyncSession, encounter_id: str, status: str = "expired") -> bool:
        """Move an active encounter to one terminal state exactly once."""
        if status not in {"expired", "cancelled", "captured"}:
            raise ValueError(f"Unsupported encounter terminal status: {status}")
        result = await session.execute(
            update(GameEncounter)
            .where(
                GameEncounter.id == encounter_id,
                GameEncounter.status == "active",
            )
            .values(status=status)
        )
        changed = result.rowcount == 1
        if changed:
            await session.flush()
        return changed
