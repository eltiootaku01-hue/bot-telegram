from types import SimpleNamespace

import pytest

from app.core.identity import BotIdentity
from app.modules.chie.module import ChieModule


@pytest.mark.asyncio
async def test_chie_rules_command_returns_operational_community_rules() -> None:
    module = ChieModule.__new__(ChieModule)
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup"),
        from_user=None,
        answer=answer,
    )

    await module.rules_command(message)

    assert len(answers) == 1
    assert "Respeto entre integrantes" in answers[0]
    assert "No compartas datos personales" in answers[0]
    assert "juegos, puntos y pedidos" in answers[0]


def test_chie_identity_is_distinct_from_game_and_archive_bots() -> None:
    assert BotIdentity.CHIE is not BotIdentity.SUNNA
    assert BotIdentity.CHIE is not BotIdentity.CAMI


@pytest.mark.asyncio
async def test_chie_setup_refuses_unallowlisted_community_before_topic_creation() -> None:
    from app.core.config import Settings

    class FakeSession:
        async def scalar(self, statement):
            return SimpleNamespace(chat_id=-200)

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeDatabase:
        def session(self):
            return SessionContext()

    module = ChieModule.__new__(ChieModule)
    module.database = FakeDatabase()
    module.settings = Settings(authorized_chat_ids="-100")

    answers: list[str] = []

    async def answer(text: str, **kwargs) -> None:
        answers.append(text)

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(
            chat=SimpleNamespace(type="private"),
        ),
        answer=answer,
    )

    class FakeBot:
        async def get_chat_member(self, chat_id, user_id):
            raise AssertionError("Telegram permissions must not be checked before allowlist validation")

    await module.check_setup(callback, FakeBot())

    assert answers
    assert "AUTHORIZED_CHAT_IDS" in answers[0]
