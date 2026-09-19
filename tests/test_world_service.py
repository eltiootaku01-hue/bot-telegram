import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldUsageStat
from app.services.world import WorldService


@pytest.fixture
async def session():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as db:
        yield db
    await database.close()


@pytest.mark.asyncio
async def test_observation_aggregates_without_storing_raw_text(session: AsyncSession):
    service = WorldService()
    first = await service.observe(
        session,
        bot_identity=BotIdentity.CARI,
        entry_type="topic",
        entry_key="hombres_lobo",
    )
    second = await service.observe(
        session,
        bot_identity=BotIdentity.CARI,
        entry_type="topic",
        entry_key="hombres_lobo",
        delta=2,
    )

    assert first.id == second.id
    assert second.count == 3
    rows = (await session.scalars(select(WorldUsageStat))).all()
    assert len(rows) == 1
    assert rows[0].entry_key == "hombres_lobo"
    assert not hasattr(rows[0], "raw_text")


@pytest.mark.asyncio
async def test_database_session_commits_world_observation_between_sessions():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    async with database.session() as session:
        service = WorldService()
        await service.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="persisted",
        )

    async with database.session() as session:
        rows = (await session.scalars(select(WorldUsageStat))).all()

    assert len(rows) == 1
    assert rows[0].entry_key == "persisted"
    assert rows[0].count == 1
    await database.close()


@pytest.mark.asyncio
async def test_user_and_world_scopes_stay_separate(session: AsyncSession):
    service = WorldService()
    await service.observe(
        session,
        bot_identity=BotIdentity.SUNNA,
        entry_type="action",
        entry_key="gacha",
        scope_type="world",
    )
    await service.observe(
        session,
        bot_identity=BotIdentity.SUNNA,
        entry_type="action",
        entry_key="gacha",
        scope_type="user",
        scope_id="42",
    )

    summary = await service.user_summary(session, bot_identity=BotIdentity.SUNNA, user_id=42)
    assert len(summary) == 1
    assert summary[0].scope_type == "user"


@pytest.mark.asyncio
async def test_insights_identify_hot_and_unseen_catalog_entries(session: AsyncSession):
    service = WorldService()
    await service.register_catalog_entry(
        session,
        bot_identity=BotIdentity.CARI,
        entry_type="topic",
        entry_key="hombres_lobo",
        label="Hombres lobo",
        priority=1,
    )
    await service.register_catalog_entry(
        session,
        bot_identity=BotIdentity.CARI,
        entry_type="topic",
        entry_key="gatos",
        label="Gatos",
        priority=5,
    )
    await service.observe(
        session,
        bot_identity=BotIdentity.CARI,
        entry_type="topic",
        entry_key="hombres_lobo",
        delta=4,
    )

    insights = await service.insights(session, bot_identity=BotIdentity.CARI)
    assert insights.hot == [("hombres_lobo", 4)]
    assert insights.unseen == [("gatos", "Gatos")]


@pytest.mark.asyncio
async def test_invalid_observation_is_rejected(session: AsyncSession):
    service = WorldService()
    with pytest.raises(ValueError):
        await service.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="",
        )
    with pytest.raises(ValueError):
        await service.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="anime",
            delta=0,
        )


@pytest.mark.asyncio
async def test_observe_action_populates_world_user_and_user_chat_scopes(session: AsyncSession):
    service = WorldService()

    await service.observe_action(
        session,
        bot_identity=BotIdentity.CAMI,
        action_key="media_tag",
        user_id=42,
        chat_id=99,
    )

    rows = list(await session.scalars(select(WorldUsageStat)))
    scopes = {(row.scope_type, row.scope_id, row.count) for row in rows}

    assert ("world", "global", 1) in scopes
    assert ("user", "42", 1) in scopes
    assert ("user_chat", "42:99", 1) in scopes
