from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.core.config import Settings
from app.db.database import Database
from app.db.world_models import WorldReview
from app.modules.chie.module import ChieModule
from app.services.world import WorldService
from app.services.world_curator import WorldCuratorService, format_world_review


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_daily_review_is_immutable_and_idempotent(database: Database) -> None:
    world = WorldService()
    curator = WorldCuratorService(world)

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
        first = await curator.build_daily(session, day_key="2026-09-20")

    async with database.session() as session:
        await world.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="anime",
            delta=4,
        )
        second = await curator.build_daily(session, day_key="2026-09-20")

    assert first.period_key == second.period_key
    assert first.generated_at == second.generated_at

    cari = next(item for item in second.identities if item.identity is BotIdentity.CARI)
    assert cari.hot == (("anime", 3),)

    async with database.session() as session:
        rows = list(await session.scalars(select(WorldReview)))
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_world_review_format_contains_only_aggregate_signals(database: Database) -> None:
    world = WorldService()
    curator = WorldCuratorService(world)

    async with database.session() as session:
        await world.register_catalog_entry(
            session,
            bot_identity=BotIdentity.SUNNA,
            entry_type="action",
            entry_key="waifumon",
            label="WaifuMon",
            priority=10,
        )
        report = await curator.build_daily(session, day_key="2026-09-20")

    rendered = format_world_review(report)
    assert "Snapshot agregado" in rendered
    assert "Sunna" in rendered
    assert "waifumon" in rendered
    assert "conversaciones" in rendered.casefold()


@pytest.mark.asyncio
async def test_review_command_is_private_owner_only(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77))
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    denied = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=88),
        answer=answer,
    )
    await module.world_review_command(denied)
    assert answers == []

    allowed = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=77),
        answer=answer,
    )
    await module.world_review_command(allowed)

    assert answers
    assert "Revisión daily" in answers[0]
