# -*- coding: utf-8 -*-
"""Low-overhead admission control for the shared Telegram/Discord Cerebro.

This module is an isolated policy engine. Platform adapters must call it before
scheduling ordinary work; creating it does not start either platform connection.
It uses only the standard library and bounded in-memory state.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import math
import threading
import time
from typing import Callable, Iterator

from bot_ia.resource_governor import TaskPriority


MAX_EVENT_TEXT_CHARS = 24_000
MAX_EXTERNAL_ID_CHARS = 256
CRITICAL_PRIORITIES = frozenset({
    TaskPriority.P0_MODERATION,
    TaskPriority.P1_CRITICAL,
})


class CommunityPlatform(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"


class ControlMode(str, Enum):
    LOW_RESOURCE = "low_resource"
    MEDIUM = "medium"


@dataclass(frozen=True, slots=True)
class CommunityControlPolicy:
    """Bounded, conservative queue and per-user rate policy."""

    mode: ControlMode = ControlMode.MEDIUM
    queue_capacity_per_platform: int = 256
    critical_reserve_per_platform: int = 32
    max_pending_per_room: int = 80
    max_pending_per_user: int = 5
    user_rate_window_seconds: float = 10.0
    max_user_events_per_window: int = 6
    queue_ttl_seconds: float = 45.0
    dedupe_ttl_seconds: float = 900.0
    max_dedupe_entries: int = 10_000

    def __post_init__(self) -> None:
        try:
            mode = ControlMode(self.mode)
        except ValueError as error:
            raise ValueError("unsupported community control mode") from error
        object.__setattr__(self, "mode", mode)

        integer_limits = (
            self.queue_capacity_per_platform,
            self.critical_reserve_per_platform,
            self.max_pending_per_room,
            self.max_pending_per_user,
            self.max_user_events_per_window,
            self.max_dedupe_entries,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
               for value in integer_limits):
            raise ValueError("community control integer limits must be positive")
        if self.critical_reserve_per_platform >= self.queue_capacity_per_platform:
            raise ValueError("critical reserve must be smaller than queue capacity")
        if self.max_pending_per_user > self.max_pending_per_room:
            raise ValueError("per-user pending limit cannot exceed room limit")
        float_limits = (
            self.user_rate_window_seconds,
            self.queue_ttl_seconds,
            self.dedupe_ttl_seconds,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in float_limits
        ):
            raise ValueError("rate window and lifetimes must be finite and positive")

    @classmethod
    def for_mode(cls, mode: ControlMode | str) -> "CommunityControlPolicy":
        """Return an explicit low-resource or medium-control profile."""
        selected = ControlMode(mode)
        if selected is ControlMode.MEDIUM:
            return cls()
        return cls(
            mode=ControlMode.LOW_RESOURCE,
            queue_capacity_per_platform=128,
            critical_reserve_per_platform=24,
            max_pending_per_room=32,
            max_pending_per_user=3,
            user_rate_window_seconds=10.0,
            max_user_events_per_window=3,
            queue_ttl_seconds=20.0,
            dedupe_ttl_seconds=600.0,
            max_dedupe_entries=5_000,
        )


@dataclass(frozen=True, slots=True)
class CommunityEvent:
    """Normalized event identity. Platform IDs are never merged implicitly."""

    platform: CommunityPlatform | str
    event_id: str
    room_id: str
    user_id: str
    text: str = ""
    priority: TaskPriority = TaskPriority.P2_ORDINARY
    actor_is_bot: bool = False

    def __post_init__(self) -> None:
        try:
            platform = (
                self.platform
                if isinstance(self.platform, CommunityPlatform)
                else CommunityPlatform(str(self.platform).strip().lower())
            )
        except ValueError as error:
            raise ValueError("platform must be telegram or discord") from error
        object.__setattr__(self, "platform", platform)

        for field_name in ("event_id", "room_id", "user_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")
            normalized = value.strip()
            if not normalized or len(normalized) > MAX_EXTERNAL_ID_CHARS:
                raise ValueError(f"{field_name} is empty or too long")
            object.__setattr__(self, field_name, normalized)

        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if len(self.text) > MAX_EVENT_TEXT_CHARS:
            raise ValueError("event text exceeds configured input bound")
        if not isinstance(self.actor_is_bot, bool):
            raise ValueError("actor_is_bot must be boolean")
        if isinstance(self.priority, bool):
            raise ValueError("invalid task priority")
        try:
            object.__setattr__(self, "priority", TaskPriority(self.priority))
        except (TypeError, ValueError) as error:
            raise ValueError("invalid task priority") from error


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    accepted: bool
    reason: str
    displaced_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class _QueuedEvent:
    event: CommunityEvent
    enqueued_at: float
    sequence: int


@dataclass(frozen=True, slots=True)
class _SpeakerLease:
    speaker_id: str
    task_id: str
    expires_at: float


class CommunityAdmissionController:
    """Thread-safe, bounded policy shared by adapters and the task router.

    The controller is in-memory and process-local. It must not replace durable
    platform ledgers/outboxes, platform authorization, or physical browser locks.
    """

    def __init__(
        self,
        policy: CommunityControlPolicy | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.policy = policy or CommunityControlPolicy.for_mode(ControlMode.MEDIUM)
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._queues: dict[
            CommunityPlatform,
            dict[str, dict[str, list[_QueuedEvent]]],
        ] = {platform: {} for platform in CommunityPlatform}
        self._dedupe: OrderedDict[tuple[CommunityPlatform, str], float] = OrderedDict()
        self._user_rate: dict[tuple[CommunityPlatform, str], deque[float]] = defaultdict(deque)
        self._leases: dict[tuple[CommunityPlatform, str], _SpeakerLease] = {}
        self._sequence = 0
        self._last_platform: CommunityPlatform | None = None
        self._last_room: dict[CommunityPlatform, str] = {}
        self._last_user: dict[tuple[CommunityPlatform, str], str] = {}
        self._accepted_total = 0
        self._evicted_total = 0
        self._expired_total = 0
        self._rejected: dict[str, int] = defaultdict(int)

    @staticmethod
    def _critical(priority: TaskPriority) -> bool:
        return priority in CRITICAL_PRIORITIES

    def enqueue(self, event: CommunityEvent) -> AdmissionResult:
        """Admit a normalized event without executing it or sending a message."""
        if not isinstance(event, CommunityEvent):
            raise TypeError("event must be CommunityEvent")

        with self._lock:
            now = self._clock()
            self._purge(now)

            if event.actor_is_bot:
                return self._reject("bot_authored_event")
            dedupe_key = (event.platform, event.event_id)
            if dedupe_key in self._dedupe:
                return self._reject("duplicate_event")

            priority = event.priority
            critical = self._critical(priority)
            platform_depth = self._platform_depth(event.platform)
            room_depth = self._room_depth(event.platform, event.room_id)
            user_depth = self._user_depth(event.platform, event.room_id, event.user_id)

            rate_key = (event.platform, event.user_id)
            rate_events = self._user_rate[rate_key]
            self._prune_rate(rate_events, now)
            if not critical and len(rate_events) >= self.policy.max_user_events_per_window:
                return self._reject("user_rate_limited")
            if not critical and user_depth >= self.policy.max_pending_per_user:
                return self._reject("user_pending_limit")
            if not critical and room_depth >= self.policy.max_pending_per_room:
                return self._reject("room_queue_limit")

            regular_capacity = (
                self.policy.queue_capacity_per_platform
                - self.policy.critical_reserve_per_platform
            )
            if not critical and platform_depth >= regular_capacity:
                return self._reject("critical_capacity_reserved")

            displaced_event_id: str | None = None
            if platform_depth >= self.policy.queue_capacity_per_platform:
                displaced_event_id = self._evict_lower_priority(
                    event.platform,
                    incoming_priority=priority,
                )
                if displaced_event_id is None:
                    return self._reject("critical_queue_full" if critical else "queue_full")

            self._sequence += 1
            queued = _QueuedEvent(event, now, self._sequence)
            room_queues = self._queues[event.platform].setdefault(event.room_id, {})
            room_queues.setdefault(event.user_id, []).append(queued)
            self._dedupe[dedupe_key] = now + self.policy.dedupe_ttl_seconds
            self._dedupe.move_to_end(dedupe_key)
            while len(self._dedupe) > self.policy.max_dedupe_entries:
                self._dedupe.popitem(last=False)

            if not critical:
                rate_events.append(now)
            self._accepted_total += 1
            return AdmissionResult(True, "accepted", displaced_event_id)

    def dequeue_next(self) -> CommunityEvent | None:
        """Choose highest priority first, round-robin across platform/room/user."""
        with self._lock:
            now = self._clock()
            self._purge(now)
            queued_items = list(self._iter_queued())
            if not queued_items:
                return None

            best_priority = min(int(item.event.priority) for _, _, _, _, item in queued_items)
            platform_candidates = {
                platform
                for platform, _, _, _, item in queued_items
                if int(item.event.priority) == best_priority
            }
            platform_order = self._rotate_after(list(CommunityPlatform), self._last_platform)
            selected_platform = next(
                platform for platform in platform_order if platform in platform_candidates
            )

            room_candidates = [
                room_id for room_id, user_queues in self._queues[selected_platform].items()
                if any(
                    int(item.event.priority) == best_priority
                    for items in user_queues.values()
                    for item in items
                )
            ]
            room_order = self._rotate_after(
                room_candidates,
                self._last_room.get(selected_platform),
            )
            selected_room = room_order[0]

            user_queues = self._queues[selected_platform][selected_room]
            user_candidates = [
                user_id for user_id, items in user_queues.items()
                if any(int(item.event.priority) == best_priority for item in items)
            ]
            lease_key = (selected_platform, selected_room)
            user_order = self._rotate_after(
                user_candidates,
                self._last_user.get(lease_key),
            )
            selected_user = user_order[0]
            candidates = user_queues[selected_user]
            selected_index = min(
                (
                    index for index, item in enumerate(candidates)
                    if int(item.event.priority) == best_priority
                ),
                key=lambda index: candidates[index].sequence,
            )
            selected = candidates.pop(selected_index)
            self._last_platform = selected_platform
            self._last_room[selected_platform] = selected_room
            self._last_user[lease_key] = selected_user
            self._cleanup_empty(selected_platform, selected_room, selected_user)
            return selected.event

    def acquire_speaker(
        self,
        platform: CommunityPlatform | str,
        room_id: str,
        speaker_id: str,
        task_id: str,
        *,
        lease_seconds: float = 20.0,
    ) -> bool:
        """Reserve one public speaker for a room/turn to prevent character pile-ons."""
        selected_platform = self._as_platform(platform)
        room = self._identifier(room_id, "room_id")
        speaker = self._identifier(speaker_id, "speaker_id")
        task = self._identifier(task_id, "task_id")
        if not 1.0 <= float(lease_seconds) <= 120.0:
            raise ValueError("lease_seconds must be between 1 and 120")

        with self._lock:
            now = self._clock()
            key = (selected_platform, room)
            current = self._leases.get(key)
            if current is not None and current.expires_at > now:
                if current.speaker_id == speaker and current.task_id == task:
                    self._leases[key] = _SpeakerLease(speaker, task, now + lease_seconds)
                    return True
                return False
            self._leases[key] = _SpeakerLease(speaker, task, now + lease_seconds)
            return True

    def release_speaker(
        self,
        platform: CommunityPlatform | str,
        room_id: str,
        task_id: str,
    ) -> bool:
        """Release a room lease only when the owning task ID matches."""
        selected_platform = self._as_platform(platform)
        key = (selected_platform, self._identifier(room_id, "room_id"))
        task = self._identifier(task_id, "task_id")
        with self._lock:
            current = self._leases.get(key)
            if current is None or current.task_id != task:
                return False
            del self._leases[key]
            return True

    def queue_depth(self, platform: CommunityPlatform | str | None = None) -> int:
        with self._lock:
            self._purge(self._clock())
            if platform is None:
                return sum(self._platform_depth(item) for item in CommunityPlatform)
            return self._platform_depth(self._as_platform(platform))

    def snapshot(self) -> dict[str, object]:
        """Return aggregate counters only; never expose message text or tokens."""
        with self._lock:
            now = self._clock()
            self._purge(now)
            return {
                "mode": self.policy.mode.value,
                "queue_depth": {
                    platform.value: self._platform_depth(platform)
                    for platform in CommunityPlatform
                },
                "queue_capacity_per_platform": self.policy.queue_capacity_per_platform,
                "critical_reserve_per_platform": self.policy.critical_reserve_per_platform,
                "accepted_total": self._accepted_total,
                "rejected_by_reason": dict(self._rejected),
                "evicted_total": self._evicted_total,
                "expired_total": self._expired_total,
                "active_speaker_leases": sum(
                    lease.expires_at > now for lease in self._leases.values()
                ),
            }

    def _reject(self, reason: str) -> AdmissionResult:
        self._rejected[reason] += 1
        return AdmissionResult(False, reason)

    @staticmethod
    def _as_platform(value: CommunityPlatform | str) -> CommunityPlatform:
        if isinstance(value, CommunityPlatform):
            return value
        try:
            return CommunityPlatform(str(value).strip().lower())
        except ValueError as error:
            raise ValueError("platform must be telegram or discord") from error

    @staticmethod
    def _identifier(value: str, field_name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        normalized = value.strip()
        if not normalized or len(normalized) > MAX_EXTERNAL_ID_CHARS:
            raise ValueError(f"{field_name} is empty or too long")
        return normalized

    @staticmethod
    def _rotate_after(items: list, last):
        if not items or last not in items:
            return items
        index = items.index(last)
        return items[index + 1:] + items[:index + 1]

    def _iter_queued(
        self,
    ) -> Iterator[tuple[CommunityPlatform, str, str, int, _QueuedEvent]]:
        for platform, rooms in self._queues.items():
            for room_id, users in rooms.items():
                for user_id, items in users.items():
                    for index, item in enumerate(items):
                        yield platform, room_id, user_id, index, item

    def _platform_depth(self, platform: CommunityPlatform) -> int:
        return sum(
            1 for queued_platform, _, _, _, _ in self._iter_queued()
            if queued_platform is platform
        )

    def _room_depth(self, platform: CommunityPlatform, room_id: str) -> int:
        users = self._queues[platform].get(room_id, {})
        return sum(len(items) for items in users.values())

    def _user_depth(
        self,
        platform: CommunityPlatform,
        room_id: str,
        user_id: str,
    ) -> int:
        return len(self._queues[platform].get(room_id, {}).get(user_id, ()))

    def _remove_queued(
        self,
        platform: CommunityPlatform,
        room_id: str,
        user_id: str,
        index: int,
        *,
        remove_dedupe: bool,
    ) -> _QueuedEvent:
        item = self._queues[platform][room_id][user_id].pop(index)
        if remove_dedupe:
            self._dedupe.pop((platform, item.event.event_id), None)
        self._cleanup_empty(platform, room_id, user_id)
        return item

    def _cleanup_empty(
        self,
        platform: CommunityPlatform,
        room_id: str,
        user_id: str,
    ) -> None:
        users = self._queues[platform].get(room_id)
        if users is None:
            return
        if not users.get(user_id):
            users.pop(user_id, None)
        if not users:
            self._queues[platform].pop(room_id, None)

    def _evict_lower_priority(
        self,
        platform: CommunityPlatform,
        *,
        incoming_priority: TaskPriority,
    ) -> str | None:
        candidates = [
            (room, user, index, item)
            for item_platform, room, user, index, item in self._iter_queued()
            if item_platform is platform and int(item.event.priority) > int(incoming_priority)
        ]
        if not candidates:
            return None
        room, user, index, victim = max(
            candidates,
            key=lambda entry: (int(entry[3].event.priority), entry[3].sequence),
        )
        self._remove_queued(platform, room, user, index, remove_dedupe=True)
        self._evicted_total += 1
        return victim.event.event_id

    def _prune_rate(self, events: deque[float], now: float) -> None:
        cutoff = now - self.policy.user_rate_window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

    def _purge(self, now: float) -> None:
        while self._dedupe:
            _, expires_at = next(iter(self._dedupe.items()))
            if expires_at > now:
                break
            self._dedupe.popitem(last=False)

        for key, events in list(self._user_rate.items()):
            self._prune_rate(events, now)
            if not events:
                self._user_rate.pop(key, None)

        # Ordinary work may expire; moderation/admin events are never silently
        # removed by TTL and remain visible in bounded queue/overflow counters.
        stale_items = [
            (platform, room, user, index, item)
            for platform, room, user, index, item in self._iter_queued()
            if item.event.priority not in CRITICAL_PRIORITIES
            and now - item.enqueued_at >= self.policy.queue_ttl_seconds
        ]
        for platform, room, user, index, item in reversed(stale_items):
            # Re-find by identity because earlier removals can shift list indexes.
            items = self._queues.get(platform, {}).get(room, {}).get(user, [])
            current_index = next(
                (idx for idx, queued in enumerate(items) if queued.sequence == item.sequence),
                None,
            )
            if current_index is None:
                continue
            self._remove_queued(
                platform, room, user, current_index, remove_dedupe=False
            )
            self._expired_total += 1
