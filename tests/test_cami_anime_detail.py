from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.modules.cami_media.module import CamiMediaModule
from app.services.anime_catalog import AnimeCatalogService


@pytest.mark.asyncio
async def test_anime_detail_renders_local_metadata_and_characters() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    service = AnimeCatalogService()

    async with database.session() as session:
        await service.upsert_work(
            session,
            work_id="demo.work",
            title="Obra Demo",
            media_type="anime",
            status="verified",
            year_start=2020,
            genres=("Acción", "Aventura"),
            themes=("Viaje",),
            studio="Studio Demo",
            summary_short="Una historia de ejemplo.",
        )
        await service.add_character(
            session,
            character_id="demo.work:asuna",
            work_id="demo.work",
            name="Asuna",
            aliases=("Yuuki",),
        )

    module = CamiMediaModule(database, Settings(admin_user_id=77))
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=7),
        text="/anime_ficha Asuna",
        answer=answer,
    )

    await module.anime_detail_command(message)

    assert answers
    rendered = answers[0]
    assert "Obra Demo" in rendered
    assert "Asuna" in rendered
    assert "Yuuki" in rendered
    assert "Acción" in rendered
    assert "Studio Demo" in rendered
    assert "Una historia de ejemplo." in rendered
    assert "datos faltantes con IA" in rendered

    await database.close()


@pytest.mark.asyncio
async def test_anime_detail_lists_choices_when_search_is_ambiguous() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    service = AnimeCatalogService()

    async with database.session() as session:
        await service.upsert_work(session, work_id="alpha", title="Alpha")
        await service.upsert_work(session, work_id="alpha-2", title="Alpha 2")

    module = CamiMediaModule(database, Settings(admin_user_id=77))
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="group"),
        from_user=SimpleNamespace(id=7),
        text="/anime_ficha Alpha",
        answer=answer,
    )

    await module.anime_detail_command(message)

    assert answers
    assert "Afiná la búsqueda" in answers[0]
    assert "alpha" in answers[0]
    assert "alpha-2" in answers[0]

    await database.close()
