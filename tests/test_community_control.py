# -*- coding: utf-8 -*-
"""Unit tests for the bounded two-platform community admission controller."""

from dataclasses import replace
import unittest

from bot_ia.core.community_control import (
    AdmissionResult,
    CommunityAdmissionController,
    CommunityControlPolicy,
    CommunityEvent,
    CommunityPlatform,
    ControlMode,
)
from bot_ia.resource_governor import TaskPriority


class FakeClock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


def make_event(
    platform=CommunityPlatform.TELEGRAM,
    event_id="event-1",
    room_id="general",
    user_id="user-1",
    priority=TaskPriority.P2_ORDINARY,
    actor_is_bot=False,
    text="hello",
):
    return CommunityEvent(
        platform=platform,
        event_id=event_id,
        room_id=room_id,
        user_id=user_id,
        priority=priority,
        actor_is_bot=actor_is_bot,
        text=text,
    )


def compact_policy(**overrides):
    policy = CommunityControlPolicy.for_mode(ControlMode.MEDIUM)
    return replace(policy, **overrides)


class CommunityAdmissionControllerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.controller = CommunityAdmissionController(clock=self.clock)

    def test_medium_is_default_and_low_resource_profile_is_tighter(self):
        medium = CommunityControlPolicy.for_mode(ControlMode.MEDIUM)
        low = CommunityControlPolicy.for_mode(ControlMode.LOW_RESOURCE)

        self.assertEqual(self.controller.policy.mode, ControlMode.MEDIUM)
        self.assertEqual(medium.queue_capacity_per_platform, 256)
        self.assertEqual(medium.critical_reserve_per_platform, 32)
        self.assertEqual(low.queue_capacity_per_platform, 128)
        self.assertLess(low.max_pending_per_user, medium.max_pending_per_user)
        self.assertLess(
            low.max_user_events_per_window,
            medium.max_user_events_per_window,
        )

    def test_event_identity_and_input_bounds_are_validated(self):
        with self.assertRaises(ValueError):
            make_event(platform="irc")
        with self.assertRaises(ValueError):
            make_event(event_id=" ")
        with self.assertRaises(ValueError):
            make_event(text="x" * 24_001)

    def test_bot_authored_events_are_rejected(self):
        result = self.controller.enqueue(make_event(actor_is_bot=True))
        self.assertEqual(result, AdmissionResult(False, "bot_authored_event"))
        self.assertEqual(self.controller.queue_depth(), 0)

    def test_duplicate_identity_is_scoped_to_platform(self):
        first = self.controller.enqueue(
            make_event(CommunityPlatform.TELEGRAM, event_id="same-id")
        )
        duplicate = self.controller.enqueue(
            make_event(CommunityPlatform.TELEGRAM, event_id="same-id", room_id="other")
        )
        other_platform = self.controller.enqueue(
            make_event(CommunityPlatform.DISCORD, event_id="same-id")
        )

        self.assertTrue(first.accepted)
        self.assertEqual(duplicate.reason, "duplicate_event")
        self.assertTrue(other_platform.accepted)
        self.assertEqual(self.controller.queue_depth(), 2)

    def test_regular_events_cannot_consume_critical_reserved_capacity(self):
        policy = compact_policy(
            queue_capacity_per_platform=4,
            critical_reserve_per_platform=2,
            max_pending_per_room=10,
            max_pending_per_user=10,
            max_user_events_per_window=20,
        )
        controller = CommunityAdmissionController(policy, clock=self.clock)

        self.assertTrue(controller.enqueue(make_event(event_id="n1", user_id="u1")).accepted)
        self.assertTrue(controller.enqueue(make_event(event_id="n2", user_id="u2")).accepted)
        rejected = controller.enqueue(make_event(event_id="n3", user_id="u3"))
        self.assertEqual(rejected.reason, "critical_capacity_reserved")

        self.assertTrue(controller.enqueue(make_event(
            event_id="admin", user_id="admin", priority=TaskPriority.P1_CRITICAL
        )).accepted)
        self.assertTrue(controller.enqueue(make_event(
            event_id="moderation", user_id="mod", priority=TaskPriority.P0_MODERATION
        )).accepted)
        self.assertEqual(controller.queue_depth(CommunityPlatform.TELEGRAM), 4)

    def test_security_priority_displaces_lower_priority_when_queue_is_full(self):
        policy = compact_policy(
            queue_capacity_per_platform=4,
            critical_reserve_per_platform=1,
            max_pending_per_room=10,
            max_pending_per_user=10,
            max_user_events_per_window=20,
        )
        controller = CommunityAdmissionController(policy, clock=self.clock)
        for index in range(2):
            self.assertTrue(controller.enqueue(make_event(
                event_id=f"normal-{index}", user_id=f"normal-user-{index}",
                priority=TaskPriority.P2_ORDINARY,
            )).accepted)
        self.assertTrue(controller.enqueue(make_event(
            event_id="admin", user_id="admin", priority=TaskPriority.P1_CRITICAL
        )).accepted)
        self.assertTrue(controller.enqueue(make_event(
            event_id="game", user_id="game-user", priority=TaskPriority.P3_GAMES
        )).accepted)

        admitted = controller.enqueue(make_event(
            event_id="safety", user_id="moderator",
            priority=TaskPriority.P0_MODERATION,
        ))
        self.assertTrue(admitted.accepted)
        self.assertEqual(admitted.displaced_event_id, "game")
        self.assertEqual(controller.queue_depth(CommunityPlatform.TELEGRAM), 4)
        self.assertEqual(controller.dequeue_next().event_id, "safety")

    def test_per_user_rate_limit_applies_only_to_noncritical_events(self):
        policy = compact_policy(
            max_user_events_per_window=2,
            max_pending_per_user=10,
            max_pending_per_room=20,
        )
        controller = CommunityAdmissionController(policy, clock=self.clock)
        self.assertTrue(controller.enqueue(make_event(event_id="a")).accepted)
        self.assertTrue(controller.enqueue(make_event(event_id="b")).accepted)
        limited = controller.enqueue(make_event(event_id="c"))
        self.assertEqual(limited.reason, "user_rate_limited")

        critical = controller.enqueue(make_event(
            event_id="p0", priority=TaskPriority.P0_MODERATION
        ))
        self.assertTrue(critical.accepted)

    def test_user_and_room_pending_limits_bound_regular_work(self):
        policy = compact_policy(
            max_pending_per_user=2,
            max_pending_per_room=3,
            max_user_events_per_window=20,
        )
        controller = CommunityAdmissionController(policy, clock=self.clock)
        self.assertTrue(controller.enqueue(make_event(event_id="a")).accepted)
        self.assertTrue(controller.enqueue(make_event(event_id="b")).accepted)
        user_limited = controller.enqueue(make_event(event_id="c"))
        self.assertEqual(user_limited.reason, "user_pending_limit")

        self.assertTrue(controller.enqueue(make_event(
            event_id="d", room_id="general", user_id="other-user"
        )).accepted)
        room_limited = controller.enqueue(make_event(
            event_id="e", room_id="general", user_id="third-user"
        ))
        self.assertEqual(room_limited.reason, "room_queue_limit")

    def test_highest_priority_is_dequeued_first_across_both_platforms(self):
        self.controller.enqueue(make_event(
            CommunityPlatform.TELEGRAM, event_id="chat",
            priority=TaskPriority.P2_ORDINARY,
        ))
        self.controller.enqueue(make_event(
            CommunityPlatform.DISCORD, event_id="safety",
            priority=TaskPriority.P0_MODERATION,
        ))
        self.assertEqual(self.controller.dequeue_next().event_id, "safety")
        self.assertEqual(self.controller.dequeue_next().event_id, "chat")

    def test_platforms_share_capacity_fairly_when_priorities_match(self):
        policy = compact_policy(
            max_pending_per_user=10,
            max_pending_per_room=30,
            max_user_events_per_window=20,
        )
        controller = CommunityAdmissionController(policy, clock=self.clock)
        controller.enqueue(make_event(
            CommunityPlatform.TELEGRAM, event_id="tg-1", user_id="tg-user"
        ))
        controller.enqueue(make_event(
            CommunityPlatform.TELEGRAM, event_id="tg-2", user_id="tg-user"
        ))
        controller.enqueue(make_event(
            CommunityPlatform.DISCORD, event_id="dc-1", user_id="dc-user"
        ))

        first = controller.dequeue_next()
        second = controller.dequeue_next()
        third = controller.dequeue_next()
        self.assertEqual(first.platform, CommunityPlatform.TELEGRAM)
        self.assertEqual(second.platform, CommunityPlatform.DISCORD)
        self.assertEqual(third.platform, CommunityPlatform.TELEGRAM)

    def test_users_take_turns_within_a_room(self):
        policy = compact_policy(
            max_pending_per_user=10,
            max_pending_per_room=30,
            max_user_events_per_window=20,
        )
        controller = CommunityAdmissionController(policy, clock=self.clock)
        controller.enqueue(make_event(event_id="a1", user_id="alice"))
        controller.enqueue(make_event(event_id="a2", user_id="alice"))
        controller.enqueue(make_event(event_id="b1", user_id="bob"))

        self.assertEqual(controller.dequeue_next().event_id, "a1")
        self.assertEqual(controller.dequeue_next().event_id, "b1")
        self.assertEqual(controller.dequeue_next().event_id, "a2")

    def test_ttl_expires_ordinary_work_but_not_critical_work(self):
        policy = compact_policy(queue_ttl_seconds=5.0)
        controller = CommunityAdmissionController(policy, clock=self.clock)
        controller.enqueue(make_event(event_id="old-chat"))
        controller.enqueue(make_event(
            event_id="safety", user_id="moderator",
            priority=TaskPriority.P0_MODERATION,
        ))
        self.clock.advance(6.0)

        self.assertEqual(controller.queue_depth(), 1)
        self.assertEqual(controller.dequeue_next().event_id, "safety")
        self.assertEqual(controller.snapshot()["expired_total"], 1)

    def test_speaker_lease_prevents_multiple_characters_replying_in_room(self):
        self.assertTrue(self.controller.acquire_speaker(
            CommunityPlatform.TELEGRAM, "general", "cari", "task-1"
        ))
        self.assertFalse(self.controller.acquire_speaker(
            CommunityPlatform.TELEGRAM, "general", "sunna", "task-2"
        ))
        self.assertFalse(self.controller.release_speaker(
            CommunityPlatform.TELEGRAM, "general", "task-2"
        ))
        self.assertTrue(self.controller.release_speaker(
            CommunityPlatform.TELEGRAM, "general", "task-1"
        ))
        self.assertTrue(self.controller.acquire_speaker(
            CommunityPlatform.TELEGRAM, "general", "sunna", "task-2"
        ))

    def test_speaker_leases_are_isolated_by_platform(self):
        self.assertTrue(self.controller.acquire_speaker(
            CommunityPlatform.TELEGRAM, "general", "cari", "task-1"
        ))
        self.assertTrue(self.controller.acquire_speaker(
            CommunityPlatform.DISCORD, "general", "sunna", "task-2"
        ))

    def test_metrics_never_include_message_content(self):
        self.controller.enqueue(make_event(text="private-message-marker"))
        snapshot = self.controller.snapshot()
        self.assertNotIn("private-message-marker", repr(snapshot))
        self.assertEqual(snapshot["queue_depth"]["telegram"], 1)
        self.assertEqual(snapshot["mode"], "medium")


if __name__ == "__main__":
    unittest.main()
