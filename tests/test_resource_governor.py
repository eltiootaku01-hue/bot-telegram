# -*- coding: utf-8 -*-
"""Unit tests for the resource budget, worker policy and pressure hysteresis."""

import json
from pathlib import Path
import tempfile
import unittest

from bot_ia.resource_governor import (
    BUDGET_STEP_BYTES,
    MAX_BUDGET_BYTES,
    MIN_BUDGET_BYTES,
    MemorySnapshot,
    PressureLevel,
    ResourceGovernor,
    ResourcePreferenceStore,
    TaskPriority,
    WindowsProcessTreeSampler,
    validate_budget_bytes,
)


class FakeSampler:
    def __init__(self, *samples):
        self.samples = list(samples)

    def sample(self):
        if not self.samples:
            return MemorySnapshot.invalid("no sample")
        item = self.samples.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ResourceGovernorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ResourcePreferenceStore(Path(self.tempdir.name) / "resource.json")

    def tearDown(self):
        self.tempdir.cleanup()

    def governor(self, samples, budget=MIN_BUDGET_BYTES, clock=None):
        governor = ResourceGovernor(
            store=self.store,
            sampler=FakeSampler(*samples),
            clock=clock or (lambda: 1000.0),
        )
        if budget != governor.budget_bytes:
            governor.set_budget_bytes(budget)
        return governor

    def test_budget_bounds_and_step_are_enforced(self):
        self.assertEqual(validate_budget_bytes(MIN_BUDGET_BYTES), MIN_BUDGET_BYTES)
        self.assertEqual(validate_budget_bytes(MAX_BUDGET_BYTES), MAX_BUDGET_BYTES)
        self.assertEqual(BUDGET_STEP_BYTES, 250_000_000)
        for value in (
            MIN_BUDGET_BYTES - 1, MAX_BUDGET_BYTES + 1,
            MIN_BUDGET_BYTES + 1, True, 1.25,
        ):
            with self.assertRaises(ValueError):
                validate_budget_bytes(value)

    def test_invalid_preference_recovers_to_safe_default(self):
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.store.path.write_text("{broken", encoding="utf-8")
        governor = self.governor([MemorySnapshot.invalid("sensor unavailable")])
        self.assertEqual(governor.budget_bytes, MIN_BUDGET_BYTES)
        self.assertTrue(governor.configuration_recovered)
        self.assertEqual(self.store.load_preferences().budget_bytes, MIN_BUDGET_BYTES)

    def test_invalid_sensor_never_means_zero_and_preserves_p0_p1(self):
        governor = self.governor([MemorySnapshot.invalid("sensor unavailable")])
        state = governor.sample()
        self.assertIsNone(state.memory.working_set_bytes)
        self.assertEqual(state.status_label, "PRESUPUESTO NO VERIFICADO")
        self.assertTrue(governor.allows(TaskPriority.P0_MODERATION))
        self.assertTrue(governor.allows(TaskPriority.P1_CRITICAL))
        for priority in (
            TaskPriority.P2_ORDINARY, TaskPriority.P3_GAMES,
            TaskPriority.P4_BACKGROUND,
        ):
            self.assertFalse(governor.allows(priority))

    def test_1gb_profile_pauses_games_and_background(self):
        governor = self.governor([MemorySnapshot(True, 400_000_000, 450_000_000, 1)])
        governor.sample()
        self.assertTrue(governor.allows(TaskPriority.P2_ORDINARY))
        self.assertFalse(governor.allows(TaskPriority.P3_GAMES))
        self.assertFalse(governor.allows(TaskPriority.P4_BACKGROUND))

    def test_1500mb_admits_games_but_not_background(self):
        governor = self.governor(
            [MemorySnapshot(True, 500_000_000, 550_000_000, 1)],
            budget=1_500_000_000,
        )
        governor.sample()
        self.assertTrue(governor.allows(TaskPriority.P3_GAMES))
        self.assertFalse(governor.allows(TaskPriority.P4_BACKGROUND))

    def test_1750mb_may_admit_background_when_normal(self):
        governor = self.governor(
            [MemorySnapshot(True, 500_000_000, 550_000_000, 1)],
            budget=1_750_000_000,
        )
        governor.sample()
        self.assertTrue(governor.allows(TaskPriority.P4_BACKGROUND))

    def test_warning_pauses_p4_before_p3_and_p2(self):
        governor = self.governor(
            [MemorySnapshot(True, 1_275_000_000, 1_300_000_000, 1)],
            budget=1_500_000_000,
        )
        state = governor.sample()
        self.assertEqual(state.pressure, PressureLevel.WARNING)
        self.assertTrue(governor.allows(TaskPriority.P2_ORDINARY))
        self.assertTrue(governor.allows(TaskPriority.P3_GAMES))
        self.assertFalse(governor.allows(TaskPriority.P4_BACKGROUND))
        self.assertEqual(
            state.paused_categories,
            ("trabajo de fondo y navegación pesada",),
        )

    def test_games_stage_pauses_p3_before_p2(self):
        governor = self.governor(
            [MemorySnapshot(True, 1_425_000_000, 1_450_000_000, 1)],
            budget=1_500_000_000,
        )
        state = governor.sample()
        self.assertEqual(state.pressure, PressureLevel.GAMES_PAUSED)
        self.assertTrue(governor.allows(TaskPriority.P2_ORDINARY))
        self.assertFalse(governor.allows(TaskPriority.P3_GAMES))
        self.assertFalse(governor.allows(TaskPriority.P4_BACKGROUND))

    def test_over_budget_pauses_secondary_work_but_not_moderation(self):
        governor = self.governor(
            [MemorySnapshot(True, 1_050_000_000, 1_100_000_000, 1)]
        )
        state = governor.sample()
        self.assertEqual(state.pressure, PressureLevel.REDUCING)
        self.assertEqual(state.status_label, "PRESUPUESTO SUPERADO")
        self.assertTrue(governor.allows(TaskPriority.P0_MODERATION))
        self.assertTrue(governor.allows(TaskPriority.P1_CRITICAL))
        self.assertFalse(governor.allows(TaskPriority.P2_ORDINARY))

    def test_hysteresis_requires_ten_consecutive_recovery_samples(self):
        samples = [MemorySnapshot(True, 1_150_000_000, 1_200_000_000, 1)]
        samples += [MemorySnapshot(True, 890_000_000, 900_000_000, 1)] * 10
        governor = self.governor(samples)
        self.assertEqual(governor.sample().pressure, PressureLevel.CRITICAL)
        states = [governor.sample().pressure for _ in range(10)]
        self.assertTrue(all(state is PressureLevel.CRITICAL for state in states[:-1]))
        self.assertEqual(states[-1], PressureLevel.REDUCING)

    def test_hysteresis_recovers_through_stages_in_order(self):
        samples = [MemorySnapshot(True, 1_150_000_000, 1_200_000_000, 1)]
        samples += [MemorySnapshot(True, 990_000_000, 1_000_000_000, 1)] * 10
        samples += [MemorySnapshot(True, 940_000_000, 950_000_000, 1)] * 10
        samples += [MemorySnapshot(True, 890_000_000, 900_000_000, 1)] * 10
        samples += [MemorySnapshot(True, 740_000_000, 750_000_000, 1)] * 10
        governor = self.governor(samples)
        self.assertEqual(governor.sample().pressure, PressureLevel.CRITICAL)
        for expected in (
            PressureLevel.REDUCING,
            PressureLevel.GAMES_PAUSED,
            PressureLevel.WARNING,
            PressureLevel.NORMAL,
        ):
            for _ in range(10):
                state = governor.sample()
            self.assertEqual(state.pressure, expected)

    def test_peak_is_separate_from_current_working_set(self):
        governor = self.governor([
            MemorySnapshot(True, 700_000_000, 750_000_000, 1),
            MemorySnapshot(True, 500_000_000, 550_000_000, 1),
        ])
        self.assertEqual(governor.sample().peak_working_set_bytes, 700_000_000)
        second = governor.sample()
        self.assertEqual(second.memory.working_set_bytes, 500_000_000)
        self.assertEqual(second.peak_working_set_bytes, 700_000_000)

    def test_preference_and_runtime_publish_atomically_without_secrets(self):
        governor = self.governor([MemorySnapshot(True, 300_000_000, 350_000_000, 1)])
        self.assertTrue(governor.set_budget_bytes(1_250_000_000))
        state = governor.sample()
        self.assertEqual(self.store.load_preferences().budget_bytes, 1_250_000_000)
        payload = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["runtime"]["status_label"], state.status_label)
        self.assertNotIn("token", json.dumps(payload).lower())
        self.assertNotIn("secret", json.dumps(payload).lower())

    def test_missing_runtime_state_preserves_legacy_secondary_behavior(self):
        self.assertIsNone(self.store.allows_priority(TaskPriority.P2_ORDINARY))
        self.assertTrue(self.store.secondary_comments_allowed(now=1000))

    def test_invalid_or_stale_runtime_blocks_secondary_tasks(self):
        governor = self.governor([MemorySnapshot.invalid("sensor unavailable")])
        governor.sample()
        self.assertFalse(self.store.secondary_comments_allowed(now=1000))
        fresh = self.governor([MemorySnapshot(True, 300_000_000, 350_000_000, 1)])
        fresh.sample()
        self.assertTrue(self.store.secondary_comments_allowed(now=1000))
        self.assertFalse(self.store.secondary_comments_allowed(now=1020))

    def test_worker_policy_matches_profiles_and_pressure(self):
        governor = self.governor(
            [MemorySnapshot(True, 500_000_000, 550_000_000, 1)],
            budget=1_500_000_000,
        )
        governor.sample()
        self.assertTrue(self.store.allows_priority(TaskPriority.P2_ORDINARY, now=1000))
        self.assertTrue(self.store.allows_priority(TaskPriority.P3_GAMES, now=1000))
        self.assertFalse(self.store.allows_priority(TaskPriority.P4_BACKGROUND, now=1000))

    def test_worker_policy_sheds_p4_then_p3_before_p2(self):
        governor = self.governor(
            [
                MemorySnapshot(True, 1_275_000_000, 1_300_000_000, 1),
                MemorySnapshot(True, 1_425_000_000, 1_450_000_000, 1),
            ],
            budget=1_500_000_000,
        )
        warning = governor.sample()
        self.assertEqual(warning.pressure, PressureLevel.WARNING)
        self.assertTrue(self.store.allows_priority(TaskPriority.P2_ORDINARY, now=1000))
        self.assertTrue(self.store.allows_priority(TaskPriority.P3_GAMES, now=1000))
        self.assertFalse(self.store.allows_priority(TaskPriority.P4_BACKGROUND, now=1000))
        games_paused = governor.sample()
        self.assertEqual(games_paused.pressure, PressureLevel.GAMES_PAUSED)
        self.assertTrue(self.store.allows_priority(TaskPriority.P2_ORDINARY, now=1000))
        self.assertFalse(self.store.allows_priority(TaskPriority.P3_GAMES, now=1000))
        self.assertFalse(self.store.allows_priority(TaskPriority.P4_BACKGROUND, now=1000))

    def test_off_windows_sensor_reports_unknown_not_zero(self):
        import os
        if os.name != "nt":
            state = WindowsProcessTreeSampler().sample()
            self.assertFalse(state.valid)
            self.assertIsNone(state.working_set_bytes)


if __name__ == "__main__":
    unittest.main()
