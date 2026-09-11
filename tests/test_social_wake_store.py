from datetime import datetime, timedelta

import pytest

from app.core.social_wake import SocialWakeController, WakeReason
from app.core.social_wake_store import SocialWakeStore
from app.db.database import Database


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_social_wake_survives_store_round_trip(database):
    controller = SocialWakeController()
    now = datetime(2026, 9, 11, 12, 0)
    state = controller.schedule(now, roll=10)
    store = SocialWakeStore()

    async with database.session() as session:
        saved = await store.get_or_create(session, 123, state)
        assert saved.next_wake_at == now + timedelta(minutes=40)

    async with database.session() as session:
        loaded = await store.get_or_create(session, 123, controller.schedule(now, roll=0))
        assert loaded.next_wake_at == saved.next_wake_at
        assert loaded.consecutive_silences == 0


@pytest.mark.asyncio
async def test_event_wake_creates_chat_state_on_first_event(database):
    now = datetime(2026, 9, 11, 12, 0)
    store = SocialWakeStore()

    async with database.session() as session:
        created = await store.request_wake(
            session,
            456,
            now,
            reason=WakeReason.EVENT,
        )

    assert created.next_wake_at == now
    assert created.pending_reason == WakeReason.EVENT
    assert created.consecutive_silences == 0


@pytest.mark.asyncio
async def test_event_wake_coalesces_into_existing_future_wake(database):
    controller = SocialWakeController()
    now = datetime(2026, 9, 11, 12, 0)
    store = SocialWakeStore()

    async with database.session() as session:
        await store.get_or_create(session, 123, controller.schedule(now, roll=20))
        updated = await store.request_wake(
            session,
            123,
            now + timedelta(minutes=5),
            reason=WakeReason.EVENT,
        )
        assert updated.next_wake_at == now + timedelta(minutes=5)
        assert updated.pending_reason == WakeReason.EVENT


@pytest.mark.asyncio
async def test_event_wake_respects_persisted_cooldown(database):
    controller = SocialWakeController()
    now = datetime(2026, 9, 11, 12, 0)
    state = controller.after_check(controller.schedule(now), now, spoke=True)
    store = SocialWakeStore()

    async with database.session() as session:
        await store.get_or_create(session, 123, state)
        before = await store.request_wake(
            session,
            123,
            now + timedelta(minutes=1),
            reason=WakeReason.EVENT,
        )
        assert before.next_wake_at == state.next_wake_at
        assert before.pending_reason is None
