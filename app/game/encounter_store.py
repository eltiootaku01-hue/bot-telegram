from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameAttempt, GameEncounter


class EncounterStore:
    async def create(self, session: AsyncSession, encounter: GameEncounter) -> None:
        session.add(encounter)
        await session.commit()

    async def get(self, session: AsyncSession, encounter_id: str) -> GameEncounter | None:
        return await session.get(GameEncounter, encounter_id)

    async def claim_attempt(
        self,
        session: AsyncSession,
        encounter_id: str,
        user_id: int,
        answer: str,
    ) -> bool | None:
        """Return True/False for the first attempt, None when the user already tried."""
        encounter = await session.get(GameEncounter, encounter_id)
        if encounter is None or encounter.status != "active" or encounter.expires_at <= datetime.utcnow():
            return None
        attempt = GameAttempt(
            encounter_id=encounter_id,
            user_id=user_id,
            answer=answer,
            correct=answer.casefold().strip() == (encounter.answer or "").casefold().strip(),
        )
        session.add(attempt)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return None
        return attempt.correct

    async def finish(self, session: AsyncSession, encounter_id: str, status: str = "expired") -> None:
        encounter = await session.get(GameEncounter, encounter_id)
        if encounter is not None and encounter.status == "active":
            encounter.status = status
            await session.commit()
