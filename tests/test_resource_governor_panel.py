# -*- coding: utf-8 -*-
"""Headless UI tests for the rotary memory control and bot action availability."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget

from bot_ia.resource_governor import MemorySnapshot, ResourceGovernor, ResourcePreferenceStore
from gui.resource_governor_panel import ResourceGovernorPanel


class FakeSampler:
    def __init__(self, *samples):
        self.samples = list(samples)
        self.last = samples[-1] if samples else MemorySnapshot.invalid("no sample")

    def sample(self):
        if self.samples:
            self.last = self.samples.pop(0)
        return self.last


class FakeTavern:
    def list_turns(self):
        return tuple(SimpleNamespace(waitress_id=value) for value in (
            "cari", "cami", "sunna", "chie", "chloe", "scarlet"
        ))


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._tavern = FakeTavern()
        self.selected = ""
        self.started = 0
        self.rested = 0
        self.opened_matrix = []
        self.opened_games = 0
        self.opened_waifu = []
        self.opened_orders = 0
        self.messages = []
        self.main_tabs = QTabWidget(self)
        self.incidents_panel = QWidget()
        self.main_tabs.addTab(QWidget(), "Home")
        self.main_tabs.addTab(self.incidents_panel, "Moderación")

    def _append_system(self, message):
        self.messages.append(message)

    def select_bot(self, bot_id):
        self.selected = bot_id

    def _start_selected_tavern_session(self):
        self.started += 1

    def _force_selected_rest(self):
        self.rested += 1

    def _open_bot_expanded(self, bot_id):
        self.opened_matrix.append(bot_id)

    def _start_matrix_chain(self, bot_id):
        self.opened_matrix.append(bot_id)

    def _open_mini_games(self):
        self.opened_games += 1

    def _open_waifu_registry(self, bot_id):
        self.opened_waifu.append(bot_id)

    def _open_bebida_order(self):
        self.opened_orders += 1


class ResourceGovernorPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ResourcePreferenceStore(Path(self.tempdir.name) / "resource.json")
        self.window = TestWindow()
        self.profiles = (
            SimpleNamespace(bot_id="cari", name="Cari", avatar="🦫✨", short_role="Capibara feliz"),
            SimpleNamespace(bot_id="cami", name="Cami", avatar="🦫👓", short_role="Capibara seria"),
            SimpleNamespace(bot_id="sunna", name="Sunna", avatar="🐍⚪", short_role="Serpiente blanca"),
            SimpleNamespace(bot_id="chie", name="Chie", avatar="🐭", short_role="Ratonsito"),
            SimpleNamespace(bot_id="chloe", name="Chloe", avatar="🦇", short_role="Murciélago"),
            SimpleNamespace(bot_id="scarlet", name="Scarlet", avatar="🧛‍♀️", short_role="Vampiresa"),
        )
        self.governor = ResourceGovernor(
            store=self.store,
            sampler=FakeSampler(
                MemorySnapshot(True, 100_000_000, 120_000_000, 2),
                MemorySnapshot(True, 100_000_000, 120_000_000, 2),
            ),
            clock=lambda: 1000.0,
        )
        self.panel = ResourceGovernorPanel(
            self.governor,
            self.window,
            profiles=self.profiles,
            matrix_bot_ids=("cari", "cami", "sunna", "chie"),
        )

    def tearDown(self):
        self.panel.timer.stop()
        self.window.close()
        self.panel.setParent(None)
        self.panel.deleteLater()
        self.tempdir.cleanup()

    def test_shows_six_profiles_and_only_four_matrix_profiles(self):
        self.assertEqual(len(self.panel.bot_cards), 6)
        self.assertEqual(len(self.panel.matrix_bot_ids), 4)
        self.assertIn("matrix", self.panel.bot_cards["cari"]["extra"])
        self.assertIn("matrix", self.panel.bot_cards["cami"]["extra"])
        self.assertIn("matrix", self.panel.bot_cards["sunna"]["extra"])
        self.assertIn("matrix", self.panel.bot_cards["chie"]["extra"])
        self.assertNotIn("matrix", self.panel.bot_cards["chloe"]["extra"])
        self.assertNotIn("matrix", self.panel.bot_cards["scarlet"]["extra"])

    def test_rotary_dial_persists_budget_and_rearranges_available_actions(self):
        self.panel.memory_dial.setValue(2)
        self.assertEqual(self.governor.budget_bytes, 1_500_000_000)
        self.assertEqual(self.store.load_preferences().budget_bytes, 1_500_000_000)
        self.assertTrue(self.panel.bot_cards["chie"]["extra"]["games"].isEnabled())
        self.assertFalse(self.panel.bot_cards["cari"]["extra"]["matrix"].isEnabled())

    def test_selecting_profile_does_not_start_a_service(self):
        self.panel.bot_cards["cari"]["select"].click()
        self.assertEqual(self.window.selected, "cari")
        self.assertEqual(self.window.started, 0)
        self.assertEqual(self.window.opened_matrix, [])

    def test_cami_moderation_button_only_navigates_to_existing_panel(self):
        self.panel.bot_cards["cami"]["extra"]["moderation"].click()
        self.assertIs(
            self.window.main_tabs.currentWidget(),
            self.window.incidents_panel,
        )

    def test_role_specific_actions_are_connected_to_existing_handlers(self):
        self.panel.bot_cards["cari"]["extra"]["waifu"].click()
        self.assertEqual(self.window.opened_waifu, ["cari"])
        self.panel.memory_dial.setValue(2)
        self.panel.bot_cards["chie"]["extra"]["games"].click()
        self.assertEqual(self.window.opened_games, 1)
        self.panel.bot_cards["chloe"]["extra"]["order"].click()
        self.assertEqual(self.window.opened_orders, 1)


if __name__ == "__main__":
    unittest.main()
