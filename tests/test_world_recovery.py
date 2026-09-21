from datetime import timedelta
import pytest
from sqlalchemy import BigInteger, update

from app.core.config import Settings
from app.core.time import utc_now
from app.db.database import Database
from app.db.world_models import GameWorldEvent
from app.world.models import PresenterKind, WorldEventStatus, WorldPresenterRef
from app.world.presenter import WorldPresentationRejected, WorldPresenter
from app.world.runtime import WorldRuntime
from app.world.service import WorldEventService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'world-recovery.db'}")
    await database.create_schema()
    yield database
    await database.close()


async def _schedule_unknown(database: Database, *, presenter: WorldPresenterRef) -> int:
    service = WorldEventService()
    async with database.session() as session:
        row = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=presenter,
            title="Recuperable",
            text="Evento",
            dedupe_key=f"recovery-{presenter.key}-{utc_now().timestamp()}",
        )
        await session.execute(
            update(GameWorldEvent)
            .where(GameWorldEvent.id == row.id)
            .values(
                status=WorldEventStatus.DELIVERY_UNKNOWN.value,
                last_error="ambiguous",
            )
        )
        await session.commit()
        return row.id


@pytest.mark.asyncio
async def test_retry_delivery_unknown_can_reassign_presenter(database):
    service = WorldEventService()
    event_id = await _schedule_unknown(
        database,
        presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
    )

    async with database.session() as session:
        changed = await service.retry_delivery_unknown(
            session,
            event_id=event_id,
            presenter=WorldPresenterRef("world", PresenterKind.WORLD_BOT),
        )
        assert changed is True

    async with database.session(write=True) as session:
        envelope = await service.claim_due(
            session,
            presenter_key="world_bot:world",
            now=utc_now() + timedelta(seconds=1),
        )

    assert envelope is not None
    assert envelope.presenter.key == "world"
    assert envelope.presenter.kind is PresenterKind.WORLD_BOT


@pytest.mark.asyncio
async def test_confirm_delivery_unknown_is_terminal_and_single_use(database):
    service = WorldEventService()
    event_id = await _schedule_unknown(
        database,
        presenter=WorldPresenterRef("cami", PresenterKind.EXISTING_BOT),
    )

    async with database.session() as session:
        assert await service.confirm_delivery_unknown(
            session,
            event_id=event_id,
            message_id=9001,
        )
    async with database.session() as session:
        assert not await service.confirm_delivery_unknown(
            session,
            event_id=event_id,
            message_id=9002,
        )
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == WorldEventStatus.PUBLISHED.value
    assert event.message_id == 9001


@pytest.mark.asyncio
async def test_cancel_delivery_unknown_is_terminal(database):
    service = WorldEventService()
    event_id = await _schedule_unknown(
        database,
        presenter=WorldPresenterRef("cari", PresenterKind.EXISTING_BOT),
    )

    async with database.session() as session:
        assert await service.cancel_delivery_unknown(
            session,
            event_id=event_id,
            reason="operator discarded duplicated delivery risk",
        )

    async with database.session() as session:
        assert not await service.retry_delivery_unknown(session, event_id=event_id)
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == WorldEventStatus.CANCELLED.value


def test_world_event_telegram_ids_use_64_bit_columns() -> None:
    assert isinstance(GameWorldEvent.__table__.c.chat_id.type, BigInteger)
    assert isinstance(GameWorldEvent.__table__.c.message_id.type, BigInteger)


@pytest.mark.asyncio
async def test_runtime_marks_definitive_presenter_rejection_as_failed(database):
    async def send(_event) -> int:
        raise WorldPresentationRejected("telegram rejected the request")

    runtime = WorldRuntime(
        database,
        WorldPresenter(send),
        settings=Settings(authorized_chat_ids="-100"),
    )
    service = WorldEventService()

    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            title="Rechazado",
            text="Test",
            dedupe_key="runtime-definitive-rejection",
        )
        await session.commit()
        event_id = event.id

    assert await runtime.tick() is True

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == WorldEventStatus.FAILED.value
    assert "telegram rejected" in (event.last_error or "")


@pytest.mark.asyncio
async def test_retry_delivery_unknown_refuses_expired_event(database):
    service = WorldEventService()
    event_id = await _schedule_unknown(
        database,
        presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
    )

    async with database.session() as session:
        await session.execute(
            update(GameWorldEvent)
            .where(GameWorldEvent.id == event_id)
            .values(expires_at=utc_now() - timedelta(seconds=1))
        )
        await session.commit()

    async with database.session() as session:
        changed = await service.retry_delivery_unknown(
            session,
            event_id=event_id,
        )

    assert changed is False

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == WorldEventStatus.DELIVERY_UNKNOWN.value


def test_world_recovery_text_is_bounded_for_telegram() -> None:
    from app.modules.world.recovery import WorldEventRecoveryModule

    event = GameWorldEvent(
        id=1,
        event_key="huge-payload",
        event_type="game_news",
        chat_id=-100,
        presenter_key="existing_bot:cami",
        title="Evento",
        payload_json="x" * 12000,
        status="delivery_unknown",
        run_at=utc_now(),
        attempts=1,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    text = WorldEventRecoveryModule._event_text(event)

    assert len(text) < 4096
    assert "…" in text
