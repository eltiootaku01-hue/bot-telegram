from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.identity import BotIdentity


@dataclass(frozen=True, slots=True)
class SocialObservation:
    """Small deterministic record used before invoking expensive AI."""

    chat_id: int
    message_count: int
    active_users: int
    last_message_at: datetime | None
    last_human_message_at: datetime | None
    last_bot_message_at: datetime | None
    last_event_at: datetime | None
    observed_at: datetime

    def minutes_since(self, value: datetime | None) -> int:
        if value is None:
            return 10**9
        return max(0, int((self.observed_at - value).total_seconds() // 60))


@dataclass(frozen=True, slots=True)
class SocialMemory:
    """Conversation-level facts that should survive a single scheduler tick."""

    last_speaker: BotIdentity | None = None
    last_bot_message_at: datetime | None = None
    last_event_at: datetime | None = None
    pending_followup_bot: BotIdentity | None = None
    pending_followup_until: datetime | None = None

    def with_bot_message(self, bot: BotIdentity, at: datetime) -> "SocialMemory":
        return SocialMemory(
            last_speaker=bot,
            last_bot_message_at=at,
            last_event_at=at,
            pending_followup_bot=None,
            pending_followup_until=None,
        )

    def arm_followup(self, bot: BotIdentity, until: datetime) -> "SocialMemory":
        return SocialMemory(
            last_speaker=self.last_speaker,
            last_bot_message_at=self.last_bot_message_at,
            last_event_at=self.last_event_at,
            pending_followup_bot=bot,
            pending_followup_until=until,
        )

    def followup_due(self, now: datetime) -> bool:
        return self.pending_followup_bot is not None and self.pending_followup_until is not None and now >= self.pending_followup_until

    def minutes_since_last_bot_message(self, now: datetime) -> int:
        if self.last_bot_message_at is None:
            return 10**9
        return max(0, int((now - self.last_bot_message_at).total_seconds() // 60))

    def minutes_since_last_event(self, now: datetime) -> int:
        if self.last_event_at is None:
            return 10**9
        return max(0, int((now - self.last_event_at).total_seconds() // 60))

    def human_activity_recent(self, now: datetime, *, window_minutes: int = 10) -> bool:
        # A scheduler should replace this with the DB observation when available.
        # The memory layer itself only knows about bot-side timestamps.
        return False


def human_activity_dominates(observation: SocialObservation, *, window_minutes: int = 10) -> bool:
    """Return true when humans, rather than the bots, own the conversation."""
    if observation.active_users < 2:
        return False
    recent = observation.minutes_since(observation.last_human_message_at)
    return recent <= window_minutes


def should_arm_followup(*, speaker: BotIdentity, now: datetime, probability_roll: int) -> bool:
    """Keep follow-ups optional; callers can pass a deterministic roll in tests."""
    if probability_roll < 0:
        return False
    # A simple 50% gate keeps Sunna's unfinished thought from becoming a forced duo.
    return probability_roll % 2 == 0
