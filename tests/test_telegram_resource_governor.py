# -*- coding: utf-8 -*-
"""Focused policy-gate tests; no Telegram network requests are made."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bot_ia.interfaces.telegram import TelegramAdapter, TelegramPoller
from bot_ia.resource_governor import TaskPriority


class FixedResourceStore:
    def __init__(self, allowed):
        self.allowed = allowed

    def allows_priority(self, priority):
        return self.allowed


class TelegramResourceGovernorTests(unittest.TestCase):
    @staticmethod
    def _poller():
        poller = object.__new__(TelegramPoller)
        poller._adapter = SimpleNamespace(_pending_attachments={})
        return poller

    def test_critical_commands_remain_p1(self):
        for command in ("/start", "/menu", "/help", "/setup_group", "/queja"):
            self.assertIs(
                TelegramAdapter._resource_priority_for_message(command),
                TaskPriority.P1_CRITICAL,
            )

    def test_game_social_and_order_commands_are_p3(self):
        for command in (
            "/gacha", "/pity", "/blackjack", "/duelo", "/mesera",
            "/inventario", "/turnos", "/bebida",
        ):
            self.assertIs(
                TelegramAdapter._resource_priority_for_message(command),
                TaskPriority.P3_GAMES,
            )

    def test_order_and_complaint_callbacks_remain_p1(self):
        for data in ("order:confirm:abc", "order:attach:abc", "complaint:close:abc"):
            self.assertIs(
                TelegramAdapter._resource_priority_for_callback(data),
                TaskPriority.P1_CRITICAL,
            )

    def test_connected_poller_classifies_critical_and_secondary_updates(self):
        poller = self._poller()
        self.assertIs(
            poller._resource_priority_for_update({"message": {"text": "/help"}}),
            TaskPriority.P1_CRITICAL,
        )
        self.assertIs(
            poller._resource_priority_for_update({"message": {"text": "/gacha"}}),
            TaskPriority.P3_GAMES,
        )
        self.assertIs(
            poller._resource_priority_for_update({"message": {"text": "hola"}}),
            TaskPriority.P2_ORDINARY,
        )
        self.assertIs(
            poller._resource_priority_for_update({
                "callback_query": {"data": "order:confirm:abc"}
            }),
            TaskPriority.P1_CRITICAL,
        )
        self.assertIs(
            poller._resource_priority_for_update({
                "callback_query": {"data": "bebida:resolution:512"}
            }),
            TaskPriority.P3_GAMES,
        )

    def test_pending_admin_order_photo_remains_p1(self):
        poller = self._poller()
        poller._adapter._pending_attachments["42"] = object()
        photo_update = {
            "message": {
                "from": {"id": 42},
                "chat": {"id": 99},
                "photo": [{"file_id": "test-photo"}],
            }
        }
        self.assertIs(
            poller._resource_priority_for_update(photo_update),
            TaskPriority.P1_CRITICAL,
        )
        photo_update["message"]["from"]["id"] = 43
        self.assertIs(
            poller._resource_priority_for_update(photo_update),
            TaskPriority.P2_ORDINARY,
        )

    def test_polling_conversation_id_handles_message_and_callback(self):
        self.assertEqual(
            TelegramPoller._resource_conversation_id({
                "message": {"chat": {"id": 123}},
            }),
            "123",
        )
        self.assertEqual(
            TelegramPoller._resource_conversation_id({
                "callback_query": {"message": {"chat": {"id": 456}}},
            }),
            "456",
        )

    def test_gacha_callback_is_blocked_when_p3_is_not_admitted(self):
        adapter = object.__new__(TelegramAdapter)
        adapter._resource_preferences = FixedResourceStore(False)
        callback = SimpleNamespace(user_id="10", conversation_id="20", data="gacha:draw")
        with patch("bot_ia.interfaces.telegram.parse_callback_update", return_value=callback):
            result = adapter.handle_callback({})
        self.assertEqual(result.route, "resource_limited")
        self.assertIn("actividad secundaria", result.text)

    def test_raw_comment_gate_skips_secondary_analysis_when_p2_is_paused(self):
        poller = object.__new__(TelegramPoller)
        poller._resource_preferences = FixedResourceStore(False)
        with patch("bot_ia.interfaces.telegram.analyze_telegram_comment") as analyze:
            self.assertIsNone(poller._comment_raw_update({"message": {}}))
        analyze.assert_not_called()

    def test_resource_pause_notice_is_throttled_per_chat(self):
        poller = object.__new__(TelegramPoller)
        poller._resource_notice_times = {}
        with patch(
            "bot_ia.interfaces.telegram.time.monotonic",
            side_effect=(100.0, 120.0, 161.0),
        ):
            self.assertTrue(poller._should_notify_resource_paused("123"))
            self.assertFalse(poller._should_notify_resource_paused("123"))
            self.assertTrue(poller._should_notify_resource_paused("123"))

    def test_resource_pause_notice_cooldown_is_independent_per_chat(self):
        poller = object.__new__(TelegramPoller)
        poller._resource_notice_times = {}
        with patch(
            "bot_ia.interfaces.telegram.time.monotonic",
            side_effect=(100.0, 101.0),
        ):
            self.assertTrue(poller._should_notify_resource_paused("123"))
            self.assertTrue(poller._should_notify_resource_paused("456"))

    def test_raw_comment_path_remains_available_when_p2_is_allowed(self):
        poller = object.__new__(TelegramPoller)
        poller._resource_preferences = FixedResourceStore(True)
        decision = SimpleNamespace(
            should_reply=True,
            chat_id="123",
            text="Respuesta de prueba",
            reply_to_message_id=9,
        )
        with patch(
            "bot_ia.interfaces.telegram.analyze_telegram_comment",
            return_value=decision,
        ):
            result = poller._comment_raw_update({"message": {}})
        self.assertEqual(result.chat_id, "123")
        self.assertEqual(result.reply_to_message_id, 9)


if __name__ == "__main__":
    unittest.main()
