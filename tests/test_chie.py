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
