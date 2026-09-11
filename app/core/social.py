from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.identity import BotIdentity


class SocialMode(StrEnum):
    QUIET = "quiet"
    ACTIVE = "active"
    OBSERVE = "observe"


@dataclass(frozen=True, slots=True)
class PersonalityPolicy:
    identity: BotIdentity
    mode: SocialMode
    description: str
    max_reply_sentences: int
    intervention_weight: int
    can_finish_another_bot: bool = False


@dataclass(frozen=True, slots=True)
class ActivityCost:
    reply: int
    conversation: int
    social_event: int
    web_lookup: int
    ai_call: int
    heavy_task: int


PERSONALITY_POLICIES: dict[BotIdentity, PersonalityPolicy] = {
    BotIdentity.CARI: PersonalityPolicy(
        BotIdentity.CARI,
        SocialMode.ACTIVE,
        "Animada, expresiva y espontánea; intenta mantener viva la conversación.",
        max_reply_sentences=3,
        intervention_weight=7,
    ),
    BotIdentity.SUNNA: PersonalityPolicy(
        BotIdentity.SUNNA,
        SocialMode.QUIET,
        "Kuudere: habla poco, con frases cortas, tono sereno y aparentemente indiferente.",
        max_reply_sentences=1,
        intervention_weight=2,
        can_finish_another_bot=True,
    ),
    BotIdentity.CAMI: PersonalityPolicy(
        BotIdentity.CAMI,
        SocialMode.OBSERVE,
        "Elocuente y fría; explica con precisión sin buscar protagonismo social.",
        max_reply_sentences=4,
        intervention_weight=4,
    ),
    BotIdentity.CHIE: PersonalityPolicy(
        BotIdentity.CHIE,
        SocialMode.ACTIVE,
        "Miedosa y nerviosa; duda, se corrige y aun así intenta ayudar.",
        max_reply_sentences=3,
        intervention_weight=5,
        can_finish_another_bot=True,
    ),
}


ACTIVITY_COSTS: dict[BotIdentity, ActivityCost] = {
    BotIdentity.CARI: ActivityCost(2, 3, 5, 4, 7, 8),
    BotIdentity.SUNNA: ActivityCost(1, 2, 5, 4, 7, 8),
    BotIdentity.CAMI: ActivityCost(2, 4, 4, 6, 7, 8),
    BotIdentity.CHIE: ActivityCost(2, 3, 5, 4, 7, 8),
}


MIN_EVENT_INTERVAL_MINUTES = 30
MAX_EVENT_INTERVAL_MINUTES = 60
HIGH_ACTIVITY_WINDOW_MINUTES = 10
HIGH_ACTIVITY_MESSAGES = 8


def personality_for(identity: BotIdentity) -> PersonalityPolicy:
    return PERSONALITY_POLICIES[identity]


def costs_for(identity: BotIdentity) -> ActivityCost:
    return ACTIVITY_COSTS[identity]


def should_intervene(*, recent_messages: int, minutes_since_last_message: int) -> bool:
    """Conservative local gate before any LLM call or social event.

    A busy chat is protected from bot interruptions. A quiet chat is eligible
    for a nudge only after enough silence has accumulated.
    """
    if recent_messages >= HIGH_ACTIVITY_MESSAGES:
        return False
    return minutes_since_last_message >= MIN_EVENT_INTERVAL_MINUTES
