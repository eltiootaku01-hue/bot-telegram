from types import SimpleNamespace

import pytest

from app.db.database import Database
from app.modules.cafe.module import CafeModule


@pytest.mark.asyncio
async def test_cafe_menu_is_authored_and_contains_core_services() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    module = CafeModule(database)

    answers: list[str] = []

    async def answer(text: str, **kwargs) -> None:
        answers.append(text)
        assert kwargs["reply_markup"] is not None

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=7),
        answer=answer,
    )

    await module.cafe(message)

    assert answers
    text = answers[0]
    assert "Café Otaku" in text
    assert "Zona de juegos" in text
    assert "Archivo y publicaciones" in text
    assert "Recepción y reglas" in text
    assert "/recomendacion" in text
    assert "Misterio diario" in text

    await database.close()


@pytest.mark.asyncio
async def test_recommendation_is_deterministic_per_day_and_chat() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    module = CafeModule(database)

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=7),
        answer=answer,
    )

    await module.recommendation(message)
    first = answers[-1]
    await module.recommendation(message)
    second = answers[-1]

    assert first == second
    assert "Recomendación de Cari" in first
    assert "Sin spoilers" in first

    await database.close()


@pytest.mark.asyncio
async def test_cafe_mystery_publishes_authored_case_and_buttons() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    module = CafeModule(database)

    answers: list[tuple[str, object]] = []

    async def answer(text: str, **kwargs) -> None:
        answers.append((text, kwargs.get("reply_markup")))

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=7),
        answer=answer,
    )

    await module.mystery(message)

    assert answers
    text, markup = answers[0]
    assert "Misterio del Café" in text
    assert "no añade hechos al canon" in text
    assert markup is not None
    assert len(markup.inline_keyboard) >= 2
    assert all(
        button.callback_data and button.callback_data.startswith("cafe:mystery:")
        for row in markup.inline_keyboard
        for button in row
    )

    await database.close()


@pytest.mark.asyncio
async def test_cafe_event_persists_and_reuses_daily_state() -> None:
    from types import SimpleNamespace

    from sqlalchemy import select

    from app.db.models import CafeDailyEventRound

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    module = CafeModule(database)

    sent_ids = iter((501, 502))

    async def answer(text: str, **kwargs):
        return SimpleNamespace(message_id=next(sent_ids), chat=SimpleNamespace(id=-100))

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=7),
        answer=answer,
    )

    await module.event_command(message)
    await module.event_command(message)

    async with database.session() as session:
        rows = list(await session.scalars(select(CafeDailyEventRound)))

    assert len(rows) == 1
    assert rows[0].status == "published"
    assert rows[0].message_id == 501

    await database.close()
