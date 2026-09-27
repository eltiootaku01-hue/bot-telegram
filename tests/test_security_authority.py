# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import contextmanager
import os
import unittest

from bot_ia.interfaces.cami_guard import is_superadmin as cami_is_superadmin
from bot_ia.interfaces.schrodinger import build_schrodinger_token_hint
from bot_ia.interfaces.superadmin import is_superadmin
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramInputError
from bot_ia.interfaces.web import WebApi
from bot_ia.security.authority import AuthorizationRequest, AuthorityCore


AUTH_ENV_KEYS = (
    "TELEGRAM_ADMIN_USER_IDS",
    "TELEGRAM_SUPERADMIN_ID",
    "TELEGRAM_SUPERADMIN_USERNAME",
    "AUTHORIZED_GROUP_ID",
    "TELEGRAM_OFFICIAL_CHAT_IDS",
    "AUTHORIZED_FORUM_ID",
    "TELEGRAM_ADMIN_CHAT_ID",
    "TELEGRAM_ADMIN_CHAT_PRIVATE",
    "DISCORD_SUPERADMIN_USER_ID",
    "DISCORD_ADMIN_USER_IDS",
    "DISCORD_AUTHORIZED_GUILD_IDS",
)


@contextmanager
def auth_env(**values: str):
    previous = {key: os.environ.get(key) for key in AUTH_ENV_KEYS}
    try:
        for key in AUTH_ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class SecurityAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authority = AuthorityCore()

    def test_01_telegram_owner_id_is_valid(self) -> None:
        with auth_env(TELEGRAM_SUPERADMIN_ID="100"):
            self.assertTrue(self.authority.is_superadmin("telegram", "100"))

    def test_02_telegram_normal_user_is_not_admin(self) -> None:
        with auth_env(TELEGRAM_SUPERADMIN_ID="100", TELEGRAM_ADMIN_USER_IDS="200"):
            self.assertFalse(self.authority.is_admin("telegram", "300"))

    def test_03_discord_owner_id_is_valid(self) -> None:
        with auth_env(DISCORD_SUPERADMIN_USER_ID="300"):
            self.assertTrue(self.authority.is_superadmin("discord", "300"))

    def test_04_discord_normal_user_is_not_admin(self) -> None:
        with auth_env(DISCORD_SUPERADMIN_USER_ID="300"):
            self.assertFalse(self.authority.is_admin("discord", "400"))

    def test_05_username_wrong_but_id_correct_is_allowed(self) -> None:
        with auth_env(TELEGRAM_SUPERADMIN_ID="100", TELEGRAM_SUPERADMIN_USERNAME="tiootakuu"):
            self.assertTrue(is_superadmin(user_id="100", username="otro_nombre"))
            self.assertTrue(cami_is_superadmin(user_id="100", username="otro_nombre"))

    def test_06_username_correct_but_id_wrong_is_denied(self) -> None:
        with auth_env(TELEGRAM_SUPERADMIN_ID="100", TELEGRAM_SUPERADMIN_USERNAME="tiootakuu"):
            self.assertFalse(is_superadmin(user_id="999", username="tiootakuu"))
            self.assertFalse(cami_is_superadmin(user_id="999", username="tiootakuu"))

    def test_07_telegram_authorized_group(self) -> None:
        with auth_env(TELEGRAM_OFFICIAL_CHAT_IDS="-100"):
            decision = self.authority.authorize(
                AuthorizationRequest(
                    "telegram", "200", "conversation",
                    destination_id="-100",
                    destination_kind="group",
                    require_authorized_destination=True,
                )
            )
            self.assertTrue(decision.allowed)

    def test_08_telegram_unauthorized_group(self) -> None:
        with auth_env(TELEGRAM_OFFICIAL_CHAT_IDS="-100"):
            decision = self.authority.authorize(
                AuthorizationRequest(
                    "telegram", "200", "conversation",
                    destination_id="-999",
                    destination_kind="group",
                    require_authorized_destination=True,
                )
            )
            self.assertFalse(decision.allowed)

    def test_09_telegram_authorized_topic(self) -> None:
        with auth_env(
            TELEGRAM_OFFICIAL_CHAT_IDS="-100",
            AUTHORIZED_FORUM_ID="-100:42",
        ):
            decision = self.authority.authorize(
                AuthorizationRequest(
                    "telegram", "200", "conversation",
                    destination_id="-100",
                    destination_kind="group",
                    thread_id=42,
                    require_authorized_destination=True,
                )
            )
            self.assertTrue(decision.allowed)

    def test_10_telegram_unauthorized_topic(self) -> None:
        with auth_env(
            TELEGRAM_OFFICIAL_CHAT_IDS="-100",
            AUTHORIZED_FORUM_ID="-100:42",
        ):
            decision = self.authority.authorize(
                AuthorizationRequest(
                    "telegram", "200", "conversation",
                    destination_id="-100",
                    destination_kind="group",
                    thread_id=99,
                    require_authorized_destination=True,
                )
            )
            self.assertFalse(decision.allowed)

    def test_11_discord_authorized_guild(self) -> None:
        with auth_env(DISCORD_AUTHORIZED_GUILD_IDS="900"):
            decision = self.authority.authorize_discord_event(
                "400",
                action="drop",
                guild_id="900",
            )
            self.assertTrue(decision.allowed)

    def test_12_discord_unauthorized_guild(self) -> None:
        with auth_env(DISCORD_AUTHORIZED_GUILD_IDS="900"):
            decision = self.authority.authorize_discord_event(
                "400",
                action="drop",
                guild_id="901",
            )
            self.assertFalse(decision.allowed)

    def test_13_normal_user_cannot_execute_admin_action(self) -> None:
        with auth_env(TELEGRAM_ADMIN_USER_IDS="100"):
            decision = self.authority.authorize_telegram_admin(
                "200",
                action="configuration",
            )
            self.assertFalse(decision.allowed)

    def test_14_authorized_admin_can_execute_admin_action(self) -> None:
        with auth_env(TELEGRAM_ADMIN_USER_IDS="100"):
            decision = self.authority.authorize_telegram_admin(
                "100",
                action="configuration",
            )
            self.assertTrue(decision.allowed)
            self.assertEqual("admin", decision.permission)

    def test_15_conversation_does_not_become_admin_from_text_or_username(self) -> None:
        with auth_env(
            TELEGRAM_SUPERADMIN_ID="100",
            TELEGRAM_SUPERADMIN_USERNAME="tiootakuu",
        ):
            decision = self.authority.authorize(
                AuthorizationRequest("telegram", "999", "conversation")
            )
            self.assertTrue(decision.allowed)
            privileged = self.authority.authorize_telegram_admin(
                "999",
                action="configuration",
            )
            self.assertFalse(privileged.allowed)

    def test_16_public_web_contract_contains_no_secret_fields(self) -> None:
        secret = "TOP_SECRET_TEST_VALUE"
        previous = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = secret

            class Application:
                def handle(self, request):
                    class Decision:
                        route = type("Route", (), {"value": "search"})()
                        agent_id = None
                        external_api_authorized = False

                    class Brain:
                        universe_id = "one_neko_punch"

                    class Response:
                        text = "respuesta publica"
                        decision = Decision()
                        brain = Brain()
                        execution = None

                    return Response()

            result = WebApi(Application()).query({"message": "hola"})
            self.assertNotIn(secret, str(result))
            self.assertNotIn("OPENAI_API_KEY", result)
            self.assertNotIn("TELEGRAM_BOT_TOKEN", result)
            self.assertNotIn("DISCORD_BOT_TOKEN", result)
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous

    def test_17_secret_hint_never_returns_secret(self) -> None:
        previous = os.environ.get("SCHRODINGER_BOT_TOKEN")
        secret = "SCHRODINGER_SECRET_TEST"
        try:
            os.environ["SCHRODINGER_BOT_TOKEN"] = secret
            self.assertEqual(
                "SCHRODINGER_BOT_TOKEN=configured",
                build_schrodinger_token_hint(),
            )
            self.assertNotIn(secret, build_schrodinger_token_hint())
        finally:
            if previous is None:
                os.environ.pop("SCHRODINGER_BOT_TOKEN", None)
            else:
                os.environ["SCHRODINGER_BOT_TOKEN"] = previous

    def test_18_unauthorized_telegram_group_does_not_reach_adapter_flow(self) -> None:
        class Application:
            def handle(self, request):
                raise AssertionError(
                    "no debe alcanzarse BOT-IA para un grupo no autorizado"
                )

        with auth_env(TELEGRAM_OFFICIAL_CHAT_IDS="-100"):
            adapter = TelegramAdapter(Application())
            self.addCleanup(adapter.close)
            update = {
                "message": {
                    "from": {"id": 200, "username": "normal"},
                    "chat": {"id": -999, "type": "supergroup"},
                    "text": "hola",
                }
            }
            with self.assertRaises(TelegramInputError):
                adapter.room_key_for_update(update)


if __name__ == "__main__":
    unittest.main()
