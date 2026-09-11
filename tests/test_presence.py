from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.core.presence import PresenceService
from app.core.time import utc_now
from app.db.database import Database
from app.db.models import BotPresence, BotPresenceState


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_all_bots_start_active(database):
    service = PresenceService()
    async with database.session() as session:
        for identity in BotIdentity:
            snapshot = await service.get_or_create(session, identity)
            assert snapshot.status == BotPresence.ACTIVE
            assert snapshot.energy == 0


@pytest.mark.asyncio
async def test_energy_reaches_rest_and_does_not_continue_spending(database):
    service = PresenceService()
    async with database.session() as session:
        first = await service.spend_energy(session, BotIdentity.SUNNA, 90, commit=False)
        assert first.status == BotPresence.ACTIVE
        assert first.energy == 90
        resting = await service.spend_energy(session, BotIdentity.SUNNA, 20, rest_minutes=30, commit=False)
        assert resting.status == BotPresence.RESTING
        assert resting.energy == 100
        blocked = await service.spend_energy(session, BotIdentity.SUNNA, 10, commit=False)
        assert blocked.status == BotPresence.RESTING
        assert blocked.energy == 100


@pytest.mark.asyncio
async def test_auto_resume_requires_timer_and_optional_pc_idle(database):
    service = PresenceService()
    async with database.session() as session:
        await service.spend_energy(
            session,
            BotIdentity.CHIE,
            100,
            rest_minutes=30,
            pc_idle_required=True,
            commit=False,
        )
        state = await service.get_or_create(session, BotIdentity.CHIE, commit=False)
        assert state.status == BotPresence.RESTING
        blocked = await service.try_auto_resume(session, BotIdentity.CHIE, pc_is_idle=False, commit=False)
        assert blocked.status == BotPresence.RESTING

        db_state = await session.scalar(
            select(BotPresenceState).where(BotPresenceState.bot_identity == BotIdentity.CHIE.value)
        )
        assert db_state is not None
        db_state.rest_until = utc_now() - timedelta(seconds=1)
        await session.flush()
        resumed = await service.try_auto_resume(session, BotIdentity.CHIE, pc_is_idle=True, commit=False)
        assert resumed.status == BotPresence.ACTIVE
        assert resumed.energy == 0


@pytest.mark.asyncio
async def test_manual_off_is_not_auto_resumed(database):
    service = PresenceService()
    async with database.session() as session:
        await service.set_manual_off(session, BotIdentity.CARI, commit=False)
        snapshot = await service.try_auto_resume(session, BotIdentity.CARI, pc_is_idle=True, commit=False)
        assert snapshot.status == BotPresence.MANUAL_OFF
        snapshot = await service.wake(session, BotIdentity.CARI, force=True, commit=False)
        assert snapshot.status == BotPresence.ACTIVE
        assert snapshot.energy == 0
