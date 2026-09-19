import pytest

from unittest.mock import AsyncMock

from app.core.config import Settings
from app.db.database import Database
from app.modules.trivia.module import TriviaModule


@pytest.mark.asyncio
async def test_publish_skips_unauthorized_community_before_database_work() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    module = TriviaModule(database, Settings(authorized_chat_ids="-100123"))

    module._bot = AsyncMock()

    assert await module._publish(-100999) is False
    module._bot.send_message.assert_not_awaited()

    await database.close()


@pytest.mark.asyncio
async def test_trivia_panel_reports_active_round(tmp_path) -> None:
    from datetime import timedelta
    from types import SimpleNamespace

    from app.core.time import utc_now
    from app.db.community_models import SetupSession
    from app.db.trivia_models import TriviaRound

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'trivia-panel.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add(
            SetupSession(
                user_id=1,
                chat_id=-100,
                bot_identity="chie",
                status="configured",
            )
        )
        session.add(
            TriviaRound(
                chat_id=-100,
                question="¿Quién es Saitama?",
                options='["Genos", "Saitama"]',
                answer_index=1,
                explanation="",
                points=15,
                status="active",
                expires_at=utc_now() + timedelta(minutes=1),
            )
        )

    module = TriviaModule(database, Settings(authorized_chat_ids="-100"))
    edits = []
    answers = []

    async def edit_text(text, **kwargs):
        edits.append(text)

    async def answer(text="", **kwargs):
        answers.append(text)

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=7, type="private"),
            edit_text=edit_text,
        ),
        answer=answer,
    )

    await module.start_panel(callback)

    assert edits
    assert "Trivia activa" in edits[0]
    assert "¿Quién es Saitama?" in edits[0]
    assert answers == [""]
    await database.close()


@pytest.mark.asyncio
async def test_trivia_panel_rejects_group_context() -> None:
    from types import SimpleNamespace

    module = TriviaModule(None, Settings(authorized_chat_ids="-100"))
    answers = []

    async def answer(text="", **kwargs):
        answers.append(text)

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
        ),
        answer=answer,
    )

    await module.start_panel(callback)

    assert answers == ["La consulta de trivia se hace desde tu chat privado con Sunna."]
