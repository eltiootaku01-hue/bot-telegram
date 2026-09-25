from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.identity import BotIdentity
from app.core.social import (
    MAX_EVENT_INTERVAL_MINUTES,
    MIN_EVENT_INTERVAL_MINUTES,
    rank_interveners,
)


@dataclass(frozen=True, slots=True)
class SocialSnapshot:
    recent_messages: int
    active_users: int
    minutes_since_last_message: int
    minutes_since_last_bot_message: int
    minutes_since_last_event: int
    conversation_active: bool


@dataclass(frozen=True, slots=True)
class SocialDecision:
    should_speak: bool
    candidates: tuple[BotIdentity, ...]
    reason: str
    cooldown_minutes: int


class SocialDirector:
    """Cheap deterministic gate that decides whether social AI should wake.

    It protects human conversations, staggers bot activity and keeps the
    expensive LLM outside the decision gate. A caller may still choose silence
    after receiving candidates.
    """

    def decide(
        self,
        snapshot: SocialSnapshot,
        fatigue_by_bot: dict[BotIdentity, int],
        *,
        cooldown_roll: int = 0,
    ) -> SocialDecision:
        if snapshot.conversation_active:
            return SocialDecision(False, (), "human_conversation_active", 0)
        if snapshot.recent_messages >= 8 or snapshot.active_users >= 3:
            return SocialDecision(False, (), "chat_busy", 0)
        if snapshot.minutes_since_last_bot_message < MIN_EVENT_INTERVAL_MINUTES:
            return SocialDecision(False, (), "bot_cooldown", MIN_EVENT_INTERVAL_MINUTES - snapshot.minutes_since_last_bot_message)
        if snapshot.minutes_since_last_event < MIN_EVENT_INTERVAL_MINUTES:
            return SocialDecision(False, (), "event_cooldown", MIN_EVENT_INTERVAL_MINUTES - snapshot.minutes_since_last_event)
        if snapshot.minutes_since_last_message < MIN_EVENT_INTERVAL_MINUTES:
            return SocialDecision(False, (), "silence_not_long_enough", MIN_EVENT_INTERVAL_MINUTES - snapshot.minutes_since_last_message)

        candidates = rank_interveners(
            recent_messages=snapshot.recent_messages,
            minutes_since_last_message=snapshot.minutes_since_last_message,
            fatigue_by_bot=fatigue_by_bot,
        )
        if not candidates:
            return SocialDecision(False, (), "no_rested_bot", 0)
        return SocialDecision(True, candidates, "quiet_window", self._next_cooldown(cooldown_roll))

    @staticmethod
    def _next_cooldown(cooldown_roll: int) -> int:
        """Return a testable pseudo-random interval in the 30–60 minute band."""
        span = MAX_EVENT_INTERVAL_MINUTES - MIN_EVENT_INTERVAL_MINUTES + 1
        return MIN_EVENT_INTERVAL_MINUTES + (max(0, cooldown_roll) % span)

    @staticmethod
    def followup_allowed(*, original_bot: BotIdentity, now: datetime, last_bot_message_at: datetime | None) -> bool:
        if last_bot_message_at is None:
            return False
        return now - last_bot_message_at >= timedelta(minutes=5)
