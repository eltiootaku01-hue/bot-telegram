from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum


class WakeReason(StrEnum):
    SCHEDULED = "scheduled"
    EVENT = "event"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class SocialWakeState:
    """Small deterministic state machine for proactive social opportunities.

    A wake is an opportunity, never a command to speak. The caller still runs
    the SocialDirector and may choose silence. Event wakes can pull a check
    forward without creating another scheduler or background timer.
    """

    next_wake_at: datetime
    cooldown_until: datetime | None = None
    pending_reason: WakeReason | None = None
    consecutive_silences: int = 0


class SocialWakeController:
    """Adaptive, event-aware cadence that keeps proactive checks cheap."""

    def __init__(self, *, min_minutes: int = 30, max_minutes: int = 60) -> None:
        if min_minutes <= 0 or max_minutes < min_minutes:
            raise ValueError("invalid social wake interval")
        self.min_minutes = min_minutes
        self.max_minutes = max_minutes

    def schedule(self, now: datetime, *, roll: int = 0) -> SocialWakeState:
        return SocialWakeState(next_wake_at=now + timedelta(minutes=self._interval(roll)))

    def request_wake(
        self,
        state: SocialWakeState,
        now: datetime,
        *,
        reason: WakeReason = WakeReason.EVENT,
    ) -> SocialWakeState:
        """Coalesce an event into the current sleep instead of spawning work."""
        if state.cooldown_until and now < state.cooldown_until:
            return state
        return replace(state, next_wake_at=min(state.next_wake_at, now), pending_reason=reason)

    def due(self, state: SocialWakeState, now: datetime) -> bool:
        if state.cooldown_until and now < state.cooldown_until:
            return False
        return now >= state.next_wake_at

    def after_check(
        self,
        state: SocialWakeState,
        now: datetime,
        *,
        spoke: bool,
        roll: int = 0,
        chat_busy: bool = False,
    ) -> SocialWakeState:
        """Schedule the next opportunity after a director check.

        Busy conversations stretch the next interval. Repeated silence also
        stretches it slightly, preventing a quiet group from becoming a
        machine that keeps asking itself whether it should talk.
        """
        silence_count = 0 if spoke else min(state.consecutive_silences + 1, 3)
        base = self._interval(roll)
        if chat_busy:
            base = min(self.max_minutes, base + 15)
        elif silence_count:
            base = min(self.max_minutes, base + 5 * silence_count)
        return SocialWakeState(
            next_wake_at=now + timedelta(minutes=base),
            cooldown_until=now + timedelta(minutes=self.min_minutes),
            pending_reason=None,
            consecutive_silences=silence_count,
        )

    def _interval(self, roll: int) -> int:
        span = self.max_minutes - self.min_minutes + 1
        return self.min_minutes + (max(0, roll) % span)
