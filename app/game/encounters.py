from dataclasses import dataclass
from datetime import datetime, timedelta
from random import randint
from secrets import token_urlsafe

from app.game.models import Character, Rarity


@dataclass(frozen=True, slots=True)
class EncounterPlan:
    requires_question: bool


@dataclass(frozen=True, slots=True)
class Encounter:
    id: str
    character: Character
    expires_at: datetime
    question: str | None = None
    answer: str | None = None


# Wild alerts are intentionally capped at class B for now.
PLANS: dict[Rarity, EncounterPlan] = {
    Rarity.COMMON: EncounterPlan(False),
    Rarity.RARE: EncounterPlan(True),
}


def new_encounter(character: Character, now: datetime | None = None) -> Encounter:
    now = now or datetime.utcnow()
    plan = PLANS.get(character.rarity, EncounterPlan(False))
    duration = randint(60, 600)
    question = (
        "¿Cómo se llama el protagonista masculino de Toradora!?"
        if plan.requires_question
        else None
    )
    return Encounter(
        id=token_urlsafe(12),
        character=character,
        expires_at=now + timedelta(seconds=duration),
        question=question,
        answer="ryuuji" if question else "capture",
    )
