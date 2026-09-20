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
