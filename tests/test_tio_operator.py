from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.models import TioOperatorRequest
from app.modules.tio_operator.module import TioOperatorModule
from app.services.tio_operator import TioOperatorService


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


def test_operator_address_requires_explicit_call() -> None:
    module = TioOperatorModule.__new__(TioOperatorModule)

    assert module._should_capture("Tío Otaku, necesito hablar con vos.")
    assert module._should_capture("tío, vení un segundo.")
    assert module._should_capture("¿Dónde está Tío Otaku?")
    assert not module._should_capture("Mi tío vive acá.")
    assert not module._should_capture("El tío de Juan llegó.")


@pytest.mark.asyncio
async def test_operator_capture_is_idempotent(database: Database) -> None:
    service = TioOperatorService()

    async with database.session() as session:
        first = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=1,
            text="Tío Otaku, necesito hablar con vos.",
        )
        second = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=1,
            text="Tío Otaku, necesito hablar con vos.",
        )

    assert first.created is True
    assert second.created is False
    assert first.request.id == second.request.id

    async with database.session() as session:
        rows = list(await session.scalars(select(TioOperatorRequest)))

    assert len(rows) == 1
    assert rows[0].status == "pending"


@pytest.mark.asyncio
async def test_operator_module_forwards_explicit_request_without_replying_as_tio(
    database: Database,
) -> None:
    module = TioOperatorModule(
        database,
        Settings(
            admin_user_id=77,
            authorized_chat_ids="-100",
        ),
    )
    bot = AsyncMock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=7, full_name="Integrante", is_bot=False),
        chat=SimpleNamespace(id=-100, type="supergroup", title="Café Otaku"),
        message_id=42,
        text="Tío Otaku, necesito hablar con vos.",
    )

    await module.capture_message(message, bot)

    bot.send_message.assert_awaited_once()
    destination = bot.send_message.await_args.args[0]
    forwarded = bot.send_message.await_args.args[1]
    assert destination == 77
    assert "Solicitud para Tío Otaku" in forwarded
    assert "sistema solo transporta la solicitud" in forwarded
    assert not hasattr(message, "answer")


@pytest.mark.asyncio
async def test_operator_module_ignores_unauthorized_group(database: Database) -> None:
    module = TioOperatorModule(
        database,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )
    bot = AsyncMock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=7, full_name="Integrante", is_bot=False),
        chat=SimpleNamespace(id=-101, type="supergroup", title="Otro"),
        message_id=43,
        text="Tío, te necesito.",
    )

    await module.capture_message(message, bot)

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_operator_decision_is_owner_only_and_single_use(database: Database) -> None:
    module = TioOperatorModule(database, Settings(admin_user_id=77))

    async with database.session() as session:
        row = await TioOperatorService().capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=44,
            text="Tío, necesito una mano.",
        )

    denied = SimpleNamespace(
        message=SimpleNamespace(
            chat=SimpleNamespace(type="private"),
        ),
        from_user=SimpleNamespace(id=88),
        data=f"tio:request:resolve:{row.request.id}",
        answer=AsyncMock(),
    )
    await module.decide_request(denied)
    denied.answer.assert_awaited_once()

    owner_message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=77),
        edit_reply_markup=AsyncMock(),
        answer=AsyncMock(),
    )
    owner = SimpleNamespace(
        message=owner_message,
        from_user=SimpleNamespace(id=77),
        data=f"tio:request:resolve:{row.request.id}",
        answer=AsyncMock(),
    )
    await module.decide_request(owner)

    async with database.session() as session:
        stored = await session.get(TioOperatorRequest, row.request.id)

    assert stored is not None
    assert stored.status == "resolved"
    owner_message.edit_reply_markup.assert_awaited_once()
    owner_message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_operator_request_can_progress_from_acknowledged_to_resolved(
    database: Database,
) -> None:
    service = TioOperatorService()

    async with database.session() as session:
        captured = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=45,
            text="Tío, cuando puedas ayudame.",
        )
        request_id = captured.request.id
        acknowledged = await service.decide(
            session,
            request_id=request_id,
            status="acknowledged",
        )
        resolved = await service.decide(
            session,
            request_id=request_id,
            status="resolved",
        )

    assert acknowledged is True
    assert resolved is True

    async with database.session() as session:
        row = await session.get(TioOperatorRequest, request_id)

    assert row is not None
    assert row.status == "resolved"
