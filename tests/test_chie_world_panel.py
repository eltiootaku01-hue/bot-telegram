from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.modules.chie.module import ChieModule
from app.services.world import WorldService


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_world_command_is_admin_private_only(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77))
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    denied = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=88),
        answer=answer,
    )
    await module.world_command(denied)
    assert answers == []


@pytest.mark.asyncio
async def test_world_command_reports_aggregate_signals(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77))
    world = WorldService()

    async with database.session() as session:
        await world.register_catalog_entry(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="anime",
            label="Anime",
            priority=10,
        )
        await world.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="anime",
            delta=3,
        )

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=77),
        answer=answer,
    )
    await module.world_command(message)

    assert answers
    assert "Ciudad Animals" in answers[0]
    assert "anime (3)" in answers[0]
    assert "Cami" in answers[0]
