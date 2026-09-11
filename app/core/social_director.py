from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.identity import BotIdentity
from app.core.social import (
    MAX_EVENT_INTERVAL_MINUTES,
    MIN_EVENT_INTERVAL_MINUTES,
    PERSONALITY_POLICIES,
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
    """Cheap, deterministic gate that decides whether social AI should wake.

    The director deliberately does not generate text. It protects human
    conversations, staggers bot activity, and can decide to remain silent even
    when an event window is available. A caller can then choose a candidate
    randomly and only invoke an LLM after this gate succeeds.
    """

    def decide(self, snapshot: SocialSnapshot, fatigue_by_bot: dict[BotIdentity, int]) -> SocialDecision:
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
        return SocialDecision(True, candidates, "quiet_window", self._next_cooldown(snapshot))

    @staticmethod
    def _next_cooldown(snapshot: SocialSnapshot) -> int:
        # Busy rooms should wait longer before another bot-initiated nudge.
        # This keeps the default cadence in the requested 30–60 minute range.
        if snapshot.active_users >= 2 or snapshot.recent_messages >= 4:
            return MAX_EVENT_INTERVAL_MINUTES
        return MIN_EVENT_INTERVAL_MINUTES

    @staticmethod
    def followup_allowed(*, original_bot: BotIdentity, now: datetime, last_bot_message_at: datetime | None) -> bool:
        if last_bot_message_at is None:
            return False
        return now - last_bot_message_at >= timedelta(minutes=5)
