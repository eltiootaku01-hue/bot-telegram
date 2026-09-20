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
    assert module._should_capture("Oye, Tío Otaku, vení un segundo.")
    assert not module._should_capture("¿Dónde está Tío Otaku?")
    assert not module._should_capture("Mi tío vive acá.")
    assert not module._should_capture("El tío de Juan llegó.")
    assert not module._should_capture("Tío de Juan llegó.")
    assert not module._should_capture("Tío necesito que vengas.")


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



@pytest.mark.asyncio
async def test_operator_can_relay_human_reply_and_resolve_request(database: Database) -> None:
    module = TioOperatorModule(
        database,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )
    bot = AsyncMock()

    async with database.session() as session:
        captured = await TioOperatorService().capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=46,
            text="Tío Otaku, ¿podés ayudarme?",
        )
        request_id = captured.request.id

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=77),
        text=f"/tio_responder {request_id} Sí, decime qué pasó.",
        answer=AsyncMock(),
    )

    await module.respond_command(message, bot)

    bot.send_message.assert_awaited_once_with(
        -100,
        "💬 <b>Tío Otaku (operador humano)</b>\n\nSí, decime qué pasó.",
    )

    async with database.session() as session:
        stored = await session.get(TioOperatorRequest, request_id)

    assert stored is not None
    assert stored.status == "resolved"


@pytest.mark.asyncio
async def test_operator_reply_keeps_request_open_when_delivery_fails(database: Database) -> None:
    module = TioOperatorModule(
        database,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("telegram unavailable")

    async with database.session() as session:
        captured = await TioOperatorService().capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=47,
            text="Tío, necesito ayuda.",
        )
        request_id = captured.request.id

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=77),
        text=f"/tio_responder {request_id} No puedo responder ahora.",
        answer=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="telegram unavailable"):
        await module.respond_command(message, bot)

    async with database.session() as session:
        stored = await session.get(TioOperatorRequest, request_id)

    assert stored is not None
    assert stored.status == "acknowledged"
    message.answer.assert_awaited_once()



@pytest.mark.asyncio
async def test_operator_ignores_bot_authored_vocative(database: Database) -> None:
    module = TioOperatorModule(
        database,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )
    bot = AsyncMock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=99, full_name="Another Bot", is_bot=True),
        chat=SimpleNamespace(id=-100, type="supergroup", title="Café Otaku"),
        message_id=48,
        text="Tío Otaku, responde.",
    )

    await module.capture_message(message, bot)

    bot.send_message.assert_not_awaited()
    async with database.session() as session:
        rows = list(await session.scalars(select(TioOperatorRequest)))

    assert rows == []


@pytest.mark.asyncio
async def test_operator_response_claim_is_single_use(database: Database) -> None:
    service = TioOperatorService()

    async with database.session() as session:
        captured = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=49,
            text="Tío Otaku, necesito una respuesta.",
        )
        request_id = captured.request.id

        first = await service.claim_response(session, request_id=request_id)
        second = await service.claim_response(session, request_id=request_id)

    assert first is True
    assert second is False

    async with database.session() as session:
        stored = await session.get(TioOperatorRequest, request_id)

    assert stored is not None
    assert stored.status == "responding"


@pytest.mark.asyncio
async def test_operator_response_claim_can_be_released(database: Database) -> None:
    service = TioOperatorService()

    async with database.session() as session:
        captured = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=50,
            text="Tío, después te escribo.",
        )
        request_id = captured.request.id
        assert await service.claim_response(session, request_id=request_id) is True
        assert await service.release_response(session, request_id=request_id) is True
        assert await service.claim_response(session, request_id=request_id) is True

    async with database.session() as session:
        stored = await session.get(TioOperatorRequest, request_id)

    assert stored is not None
    assert stored.status == "responding"


@pytest.mark.asyncio
async def test_operator_concurrent_replies_produce_one_delivery(tmp_path) -> None:
    from app.db.database import Database

    db_path = tmp_path / "tio-concurrent.sqlite3"
    seed = Database(f"sqlite+aiosqlite:///{db_path}")
    await seed.create_schema()

    async with seed.session() as session:
        captured = await TioOperatorService().capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=51,
            text="Tío Otaku, respondeme cuando puedas.",
        )
        request_id = captured.request.id

    await seed.close()
    database_a = Database(f"sqlite+aiosqlite:///{db_path}")
    database_b = Database(f"sqlite+aiosqlite:///{db_path}")
    bot = AsyncMock()

    module_a = TioOperatorModule(
        database_a,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )
    module_b = TioOperatorModule(
        database_b,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )

    def operator_message(text: str):
        return SimpleNamespace(
            chat=SimpleNamespace(type="private", id=77),
            from_user=SimpleNamespace(id=77),
            text=text,
            answer=AsyncMock(),
        )

    try:
        await __import__("asyncio").gather(
            module_a.respond_command(
                operator_message(f"/tio_responder {request_id} Primera respuesta."),
                bot,
            ),
            module_b.respond_command(
                operator_message(f"/tio_responder {request_id} Segunda respuesta."),
                bot,
            ),
        )
    finally:
        async with database_a.session() as session:
            stored = await session.get(TioOperatorRequest, request_id)
        await database_b.close()
        await database_a.close()

    assert bot.send_message.await_count == 1
    assert stored is not None
    assert stored.status == "resolved"


@pytest.mark.asyncio
async def test_operator_inbox_exposes_responding_request_for_manual_resolution(database: Database) -> None:
    service = TioOperatorService()
    module = TioOperatorModule(database, Settings(admin_user_id=77))

    async with database.session() as session:
        captured = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=52,
            text="Tío Otaku, el mensaje pudo haber salido.",
        )
        request_id = captured.request.id
        assert await service.claim_response(session, request_id=request_id) is True

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=77),
        answer=AsyncMock(),
    )

    await module.pending_command(message)

    assert message.answer.await_count == 1
    call = message.answer.await_args
    assert "respondiendo" in call.args[0]
    keyboard = call.kwargs["reply_markup"].inline_keyboard
    assert keyboard[0][0].callback_data == f"tio:request:view:{request_id}"
    assert keyboard[1][0].callback_data == f"tio:request:resolve:{request_id}"


def _owner_message(text: str):
    return SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=77),
        text=text,
        answer=AsyncMock(),
        edit_reply_markup=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_operator_context_command_is_read_only(database: Database) -> None:
    service = TioOperatorService()
    module = TioOperatorModule(database, Settings(admin_user_id=77))

    async with database.session() as session:
        captured = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=53,
            text="Tío Otaku, necesito contarte algo.",
        )
        request_id = captured.request.id

    message = _owner_message(f"/tio_ver {request_id}")
    await module.view_command(message)

    assert message.answer.await_count == 1
    rendered = message.answer.await_args.args[0]
    assert f"solicitud #{request_id}" in rendered
    assert "necesito contarte algo." in rendered
    assert f"/tio_responder {request_id} tu mensaje" in rendered

    async with database.session() as session:
        stored = await session.get(TioOperatorRequest, request_id)

    assert stored is not None
    assert stored.status == "pending"


@pytest.mark.asyncio
async def test_operator_context_callback_does_not_change_request_state(database: Database) -> None:
    service = TioOperatorService()
    module = TioOperatorModule(database, Settings(admin_user_id=77))

    async with database.session() as session:
        captured = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=54,
            text="Tío, necesito contexto.",
        )
        request_id = captured.request.id

    callback = SimpleNamespace(
        message=_owner_message("inbox"),
        from_user=SimpleNamespace(id=77),
        data=f"tio:request:view:{request_id}",
        answer=AsyncMock(),
    )
    await module.decide_request(callback)

    callback.answer.assert_awaited_once_with("Contexto mostrado.")
    callback.message.answer.assert_awaited_once()

    async with database.session() as session:
        stored = await session.get(TioOperatorRequest, request_id)

    assert stored is not None
    assert stored.status == "pending"


@pytest.mark.asyncio
async def test_operator_history_is_read_only_and_exposes_direct_navigation(database: Database) -> None:
    service = TioOperatorService()
    module = TioOperatorModule(
        database,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )

    async with database.session() as session:
        first = await service.capture(
            session,
            chat_id=-100,
            user_id=7,
            source_message_id=60,
            text="Tío Otaku, necesito contexto histórico.",
        )
        second = await service.capture(
            session,
            chat_id=-100,
            user_id=8,
            source_message_id=61,
            text="Tío, otra consulta.",
        )
        await service.decide(
            session,
            request_id=second.request.id,
            status="resolved",
        )

    message = _owner_message("/tio_historial")
    await module.history_command(message)

    assert message.answer.await_count == 1
    call = message.answer.await_args
    rendered = call.args[0]
    keyboard = call.kwargs["reply_markup"].inline_keyboard
    callback_data = [
        button.callback_data
        for row in keyboard
        for button in row
    ]

    assert f"#{second.request.id}" in rendered
    assert f"#{first.request.id}" in rendered
    assert f"tio:request:view:{second.request.id}" in callback_data
    assert f"tio:request:view:{first.request.id}" in callback_data

    async with database.session() as session:
        rows = list(await session.scalars(select(TioOperatorRequest).order_by(TioOperatorRequest.id.asc())))

    assert [row.status for row in rows] == ["pending", "resolved"]


@pytest.mark.asyncio
async def test_operator_history_supports_pagination(database: Database) -> None:
    service = TioOperatorService()
    module = TioOperatorModule(
        database,
        Settings(admin_user_id=77, authorized_chat_ids="-100"),
    )

    async with database.session() as session:
        for message_id in range(70, 92):
            await service.capture(
                session,
                chat_id=-100,
                user_id=7,
                source_message_id=message_id,
                text=f"Tío, consulta {message_id}.",
            )

    message = _owner_message("/tio_historial")
    await module.history_command(message)

    assert message.answer.await_count == 1
    first_render = message.answer.await_args.args[0]
    first_markup = message.answer.await_args.kwargs["reply_markup"].inline_keyboard
    first_callbacks = [button.callback_data for row in first_markup for button in row]

    assert "página 1" in first_render
    assert "Siguientes ➡️" in [button.text for row in first_markup for button in row]
    assert "tio:history:page:2" in first_callbacks

    callback_message = _owner_message("historial")
    callback = SimpleNamespace(
        message=callback_message,
        from_user=SimpleNamespace(id=77),
        data="tio:history:page:2",
        answer=AsyncMock(),
    )
    await module.history_page_callback(callback)

    callback_message.edit_text.assert_awaited_once()
    second_render = callback_message.edit_text.await_args.args[0]
    second_markup = callback_message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
    second_callbacks = [button.callback_data for row in second_markup for button in row]

    assert "página 2" in second_render
    assert "⬅️ Anteriores" in [button.text for row in second_markup for button in row]
    assert "tio:history:page:1" in second_callbacks
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_operator_history_rejects_invalid_pagination(database: Database) -> None:
    module = TioOperatorModule(database, Settings(admin_user_id=77))

    message = _owner_message("/tio_historial 0")
    await module.history_command(message)
    assert "página" in message.answer.await_args.args[0]

    callback = SimpleNamespace(
        message=_owner_message("historial"),
        from_user=SimpleNamespace(id=77),
        data="tio:history:page:0",
        answer=AsyncMock(),
    )
    await module.history_page_callback(callback)
    callback.answer.assert_awaited_once_with("Página inválida.", show_alert=True)
