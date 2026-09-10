from dataclasses import dataclass
from datetime import datetime, timedelta
from secrets import token_urlsafe

from app.game.models import Character, Rarity


@dataclass(frozen=True, slots=True)
class EncounterPlan:
    duration_seconds: int
    requires_question: bool


@dataclass(frozen=True, slots=True)
class Encounter:
    id: str
    character: Character
    expires_at: datetime
    question: str | None = None
    answer: str | None = None


# A and below can be instant captures. B+ asks a niche question.
PLANS: dict[Rarity, EncounterPlan] = {
    Rarity.COMMON: EncounterPlan(60, False),
    Rarity.RARE: EncounterPlan(120, False),
    Rarity.EPIC: EncounterPlan(300, False),
    Rarity.LEGENDARY: EncounterPlan(600, True),
    Rarity.MYTHIC: EncounterPlan(600, True),
}


def new_encounter(character: Character, now: datetime | None = None) -> Encounter:
    now = now or datetime.utcnow()
    plan = PLANS[character.rarity]
    return Encounter(
        id=token_urlsafe(12),
        character=character,
        expires_at=now + timedelta(seconds=plan.duration_seconds),
        question=("¿Cómo se llama la hermana del protagonista de este anime?" if plan.requires_question else None),
        answer=("yasuko" if plan.requires_question else None),
    )
