from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

from app.core.config import Settings
from app.db.database import Database
from app.db.world_models import GameWorldEvent
from app.modules.world.recovery import WorldEventRecoveryModule
from app.world.models import PresenterKind, WorldEventStatus, WorldPresenterRef
from app.world.service import WorldEventService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'world-recovery-module.db'}")
    await database.create_schema()
    yield database
    await database.close()


async def _make_unknown_event(database: Database) -> int:
    service = WorldEventService()
    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            title="Entrega ambigua",
            text="Prueba",
            dedupe_key="module-recovery-test",
        )
        await session.execute(
            update(GameWorldEvent)
            .where(GameWorldEvent.id == event.id)
            .values(status=WorldEventStatus.DELIVERY_UNKNOWN.value, last_error="network")
        )
        await session.commit()
        return event.id


@pytest.mark.asyncio
async def test_master_can_confirm_world_event_from_private_command(database):
    settings = Settings(master_telegram_id=77, allow_user_private_chat=True)
    module = WorldEventRecoveryModule(database, settings=settings)
    event_id = await _make_unknown_event(database)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=77),
        text=f"/world_confirmar {event_id} 901",
        answer=AsyncMock(),
    )

    await module.confirm_command(message)

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == WorldEventStatus.PUBLISHED.value
    assert event.message_id == 901
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_master_cannot_change_world_event_from_private_command(database):
    settings = Settings(master_telegram_id=77, allow_user_private_chat=True)
    module = WorldEventRecoveryModule(database, settings=settings)
    event_id = await _make_unknown_event(database)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=88),
        from_user=SimpleNamespace(id=88),
        text=f"/world_cancelar {event_id}",
        answer=AsyncMock(),
    )

    await module.cancel_command(message)

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == WorldEventStatus.DELIVERY_UNKNOWN.value
    message.answer.assert_not_awaited()
