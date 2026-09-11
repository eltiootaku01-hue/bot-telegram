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
    BotIdentity.CARI: PersonalityPolicy(BotIdentity.CARI, SocialMode.ACTIVE, "Animada, expresiva y espontánea; intenta mantener viva la conversación.", 3, 7),
    BotIdentity.SUNNA: PersonalityPolicy(BotIdentity.SUNNA, SocialMode.QUIET, "Kuudere: habla poco, con frases cortas, tono sereno y aparentemente indiferente.", 1, 2, True),
    BotIdentity.CAMI: PersonalityPolicy(BotIdentity.CAMI, SocialMode.OBSERVE, "Elocuente y fría; explica con precisión sin buscar protagonismo social.", 4, 4),
    BotIdentity.CHIE: PersonalityPolicy(BotIdentity.CHIE, SocialMode.ACTIVE, "Miedosa y nerviosa; duda, se corrige y aun así intenta ayudar.", 3, 5, True),
}

ACTIVITY_COSTS: dict[BotIdentity, ActivityCost] = {
    BotIdentity.CARI: ActivityCost(2, 3, 5, 4, 7, 8),
    BotIdentity.SUNNA: ActivityCost(1, 2, 5, 4, 7, 8),
    BotIdentity.CAMI: ActivityCost(2, 4, 4, 6, 7, 8),
    BotIdentity.CHIE: ActivityCost(2, 3, 5, 4, 7, 8),
}

MIN_EVENT_INTERVAL_MINUTES = 30
MAX_EVENT_INTERVAL_MINUTES = 60
HIGH_ACTIVITY_MESSAGES = 8
FOLLOWUP_DELAY_MINUTES = 5


def personality_for(identity: BotIdentity) -> PersonalityPolicy:
    return PERSONALITY_POLICIES[identity]


def costs_for(identity: BotIdentity) -> ActivityCost:
    return ACTIVITY_COSTS[identity]


def should_intervene(*, recent_messages: int, minutes_since_last_message: int) -> bool:
    """Do not interrupt a busy chat; only consider a nudge after silence."""
    return recent_messages < HIGH_ACTIVITY_MESSAGES and minutes_since_last_message >= MIN_EVENT_INTERVAL_MINUTES


def rank_interveners(*, recent_messages: int, minutes_since_last_message: int, fatigue_by_bot: dict[BotIdentity, int]) -> tuple[BotIdentity, ...]:
    """Return an eligible pool; scheduler may randomly choose or choose silence."""
    if not should_intervene(recent_messages=recent_messages, minutes_since_last_message=minutes_since_last_message):
        return ()
    candidates = [identity for identity in BotIdentity if fatigue_by_bot.get(identity, 0) < 100]
    candidates.sort(key=lambda identity: (PERSONALITY_POLICIES[identity].intervention_weight - fatigue_by_bot.get(identity, 0) // 20, -fatigue_by_bot.get(identity, 0)), reverse=True)
    return tuple(candidates)


def choose_followup(*, speaker: BotIdentity, rng_value: int) -> BotIdentity | None:
    """Optionally choose a delayed helper; negative means deliberately stay silent."""
    if rng_value < 0:
        return None
    helpers = [identity for identity, policy in PERSONALITY_POLICIES.items() if identity != speaker and policy.can_finish_another_bot]
    return helpers[rng_value % len(helpers)] if helpers else None
