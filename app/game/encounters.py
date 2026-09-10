from dataclasses import dataclass
from datetime import datetime, timedelta
from random import randint
from secrets import token_urlsafe

from app.game.models import Character, Rarity


@dataclass(frozen=True, slots=True)
class EncounterPlan:
    requires_question: bool
    label: str


@dataclass(frozen=True, slots=True)
class Encounter:
    id: str
    character: Character
    expires_at: datetime
    question: str | None = None
    answer: str | None = None


# D is the everyday encounter. C is still easy: only pick the character name.
# B and above progressively test niche knowledge. Wild group alerts are capped at B.
PLANS: dict[Rarity, EncounterPlan] = {
    Rarity.D: EncounterPlan(False, "D"),
    Rarity.C: EncounterPlan(False, "C"),
    Rarity.B: EncounterPlan(True, "B"),
}


def new_encounter(character: Character, now: datetime | None = None) -> Encounter:
    now = now or datetime.utcnow()
    plan = PLANS.get(character.rarity, PLANS[Rarity.D])
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
