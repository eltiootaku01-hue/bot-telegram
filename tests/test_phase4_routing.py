# -*- coding: utf-8 -*-
"""Pruebas de routing Telegram, allowlist y aislamiento administrativo."""

from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from bot_ia.interfaces.group_setup import GroupRoom, GroupSetupStore, TelegramGroupSetup
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramInputError
from bot_ia.interfaces.telegram_room_routing import TelegramRoomRouter
from bot_ia.interfaces.telegram_security import (
    is_authorized_admin_destination,
    is_authorized_telegram_forum_route,
    is_authorized_telegram_group,
)


class Phase4RoutingTests(unittest.TestCase):
    def _adapter(self, router: TelegramRoomRouter) -> TelegramAdapter:
        adapter = object.__new__(TelegramAdapter)
        adapter._room_router = router
        return adapter

    def test_authoritative_topic_mapping_uses_exact_chat_and_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            router = TelegramRoomRouter(root / "telegram_rooms.sqlite3")
            rooms = (
                GroupRoom("#general", "general", "10"),
                GroupRoom("#cantina-18", "cantina_18", "42"),
                GroupRoom("#pedidos-nsfw", "pedidos_nsfw", "43"),
            )
            GroupSetupStore(root).save_target("telegram", "-100123", rooms)

            adapter = self._adapter(router)
            with patch.dict(
                os.environ,
                {
                    "AUTHORIZED_GROUP_ID": "-100123",
                    "AUTHORIZED_FORUM_ID": "-100123:42,-100123:43",
                },
                clear=False,
            ):
                self.assertEqual(
                    "cantina_18",
                    adapter.room_key_for_update(
                        {
                            "message": {
                                "message_thread_id": 42,
                                "is_topic_message": True,
                                "chat": {
                                    "id": -100123,
                                    "type": "supergroup",
                                },
                            }
                        }
                    ),
                )

    def test_unregistered_forum_topic_fails_closed_instead_of_general(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            router = TelegramRoomRouter(Path(temporary) / "telegram_rooms.sqlite3")
            router.replace_chat_rooms(
                "-100123",
                (GroupRoom("#general", "general", "10"),),
            )
            adapter = self._adapter(router)
            with patch.dict(
                os.environ,
                {
                    "AUTHORIZED_GROUP_ID": "-100123",
                    "AUTHORIZED_FORUM_ID": "-100123:10,-100123:99",
                },
                clear=False,
            ):
                with self.assertRaises(TelegramInputError):
                    adapter.room_key_for_update(
                        {
                            "message": {
                                "message_thread_id": 99,
                                "is_topic_message": True,
                                "chat": {
                                    "id": -100123,
                                    "type": "supergroup",
                                },
                            }
                        }
                    )

    def test_group_allowlist_rejects_unknown_group(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_GROUP_ID": "-100123",
                "AUTHORIZED_FORUM_ID": "",
            },
            clear=False,
        ):
            self.assertTrue(is_authorized_telegram_group("-100123"))
            self.assertFalse(is_authorized_telegram_group("-100999"))

    def test_forum_allowlist_is_exact_pair(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_FORUM_ID": "-100123:42",
            },
            clear=False,
        ):
            self.assertTrue(is_authorized_telegram_forum_route("-100123", 42))
            self.assertFalse(is_authorized_telegram_forum_route("-100123", 43))
            self.assertFalse(is_authorized_telegram_forum_route("-100999", 42))

    def test_automatic_bot_promotion_fails_before_network_on_unknown_group(self) -> None:
        setup = TelegramGroupSetup("test-token")
        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_GROUP_ID": "-100123",
                "TELEGRAM_OFFICIAL_CHAT_IDS": "-100123",
            },
            clear=False,
        ):
            with self.assertRaises(PermissionError):
                setup.configure_authorized_bots("-100999")

    def test_admin_destination_requires_private_flag_and_cannot_be_official_group(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_GROUP_ID": "-100123",
                "TELEGRAM_OFFICIAL_CHAT_IDS": "-100123",
                "TELEGRAM_ADMIN_CHAT_PRIVATE": "true",
            },
            clear=False,
        ):
            self.assertFalse(is_authorized_admin_destination("-100123"))
            self.assertTrue(is_authorized_admin_destination("-100555"))

        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_GROUP_ID": "-100123",
                "TELEGRAM_ADMIN_CHAT_PRIVATE": "false",
            },
            clear=False,
        ):
            self.assertFalse(is_authorized_admin_destination("-100555"))

    def test_admin_followup_is_suppressed_for_non_private_destination(self) -> None:
        class Complaint:
            complaint_id = "CMP-1"
            user_id = "u1"
            order_id = "ORD-1"
            product_type = "Carta TCG"
            points_paid = 35
            text = "motivo"

        adapter = object.__new__(TelegramAdapter)
        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_GROUP_ID": "-100123",
                "TELEGRAM_OFFICIAL_CHAT_IDS": "-100123",
                "TELEGRAM_ADMIN_CHAT_ID": "-100123",
                "TELEGRAM_ADMIN_CHAT_PRIVATE": "true",
            },
            clear=False,
        ):
            self.assertIsNone(adapter._admin_followup(Complaint()))

        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_GROUP_ID": "-100123",
                "TELEGRAM_ADMIN_CHAT_ID": "-100555",
                "TELEGRAM_ADMIN_CHAT_PRIVATE": "false",
            },
            clear=False,
        ):
            self.assertIsNone(adapter._admin_followup(Complaint()))

        with patch.dict(
            os.environ,
            {
                "AUTHORIZED_GROUP_ID": "-100123",
                "TELEGRAM_ADMIN_CHAT_ID": "-100555",
                "TELEGRAM_ADMIN_CHAT_PRIVATE": "true",
            },
            clear=False,
        ):
            followup = adapter._admin_followup(Complaint())
            self.assertIsNotNone(followup)
            self.assertEqual("-100555", followup.chat_id)


    def test_provisioning_publishes_room_map(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = GroupSetupStore(root)
            rooms = (
                GroupRoom("#pedidos-admin", "pedidos_admin", "77"),
                GroupRoom("#mesa-de-apuestas-21", "mesa_apuestas_21", "78"),
            )
            store.save_target("telegram", "-100123", rooms)
            router = TelegramRoomRouter(root / "telegram_rooms.sqlite3")
            self.assertEqual(
                "pedidos_admin",
                router.resolve("-100123", 77),
            )
            self.assertEqual(
                "mesa_apuestas_21",
                router.resolve("-100123", 78),
            )


if __name__ == "__main__":
    unittest.main()
