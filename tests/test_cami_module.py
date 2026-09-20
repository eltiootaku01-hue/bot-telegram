from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.models import AnimeWork, MediaAsset
from app.modules.cami_media.module import CamiMediaModule


class FakeState:
    def __init__(self, asset_id: int) -> None:
        self.data = {"asset_id": asset_id}
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.cleared = True
        self.data.clear()


@pytest.mark.asyncio
async def test_cami_metadata_text_targets_selected_asset_not_latest_pending(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cami-state.db'}")
    await database.create_schema()
    module = CamiMediaModule(
        database,
        Settings(admin_user_id=7),
    )

    async with database.session() as session:
        first = MediaAsset(
            telegram_file_id="file-first",
            source_chat_id=7,
            source_message_id=1,
            status="needs_tag",
        )
        second = MediaAsset(
            telegram_file_id="file-second",
            source_chat_id=7,
            source_message_id=2,
            status="needs_tag",
        )
        session.add_all([first, second])
        await session.flush()
        first_id = first.id
        second_id = second.id

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=7),
        from_user=SimpleNamespace(id=7),
        text="Asuna | Sword Art Online | conejita, azul | waifu",
        answer=answer,
    )
    state = FakeState(first_id)

    await module.receive_schedule_or_tags(message, state)

    async with database.session() as session:
        first_saved = await session.get(MediaAsset, first_id)
        second_saved = await session.get(MediaAsset, second_id)

    assert first_saved is not None
    assert first_saved.status == "tagged"
    assert first_saved.character_id == "asuna"
    assert first_saved.anime == "Sword Art Online"
    assert first_saved.tags == "conejita,azul"
    assert second_saved is not None
    assert second_saved.status == "needs_tag"
    assert answers
    assert state.cleared is True
    await database.close()


def test_cami_media_staff_uses_callback_actor_not_message_sender() -> None:
    from app.core.config import Settings

    module = CamiMediaModule.__new__(CamiMediaModule)
    module.settings = Settings(admin_user_id=77)

    callback_message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=999, is_bot=True),
    )

    assert module._is_media_staff(callback_message, user_id=77) is True
    assert module._is_media_staff(callback_message, user_id=88) is False


@pytest.mark.asyncio
async def test_catalog_command_exposes_only_published_matching_assets(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cami-catalog.db'}")
    await database.create_schema()
    module = CamiMediaModule(database, Settings(admin_user_id=7))

    async with database.session() as session:
        session.add_all(
            [
                MediaAsset(
                    telegram_file_id="published-1",
                    source_chat_id=7,
                    source_message_id=10,
                    status="published",
                    character_id="asuna",
                    anime="Sword Art Online",
                    tags="conejita,azul",
                    category="waifu",
                ),
                MediaAsset(
                    telegram_file_id="private-1",
                    source_chat_id=7,
                    source_message_id=11,
                    status="tagged",
                    character_id="asuna",
                    anime="Sword Art Online",
                    tags="conejita",
                    category="waifu",
                ),
                MediaAsset(
                    telegram_file_id="published-2",
                    source_chat_id=7,
                    source_message_id=12,
                    status="published_request",
                    character_id="asuna",
                    anime="Otra obra",
                    tags="rojo",
                    category="pedido",
                ),
            ]
        )

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=7),
        from_user=SimpleNamespace(id=7),
        text="/catalogo asuna",
        answer=answer,
    )

    await module.catalog_command(message)

    assert answers
    assert "Sword Art Online" in answers[0]
    assert "Otra obra" in answers[0]
    assert "file-" not in answers[0]
    await database.close()


@pytest.mark.asyncio
async def test_catalog_search_records_user_chat_world_scope(tmp_path) -> None:
    from app.db.world_models import WorldUsageStat
    from sqlalchemy import select

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cami-catalog-scope.db'}")
    await database.create_schema()
    module = CamiMediaModule(database, Settings(admin_user_id=7))

    async with database.session() as session:
        session.add(
            MediaAsset(
                telegram_file_id="published-scope",
                source_chat_id=7,
                source_message_id=20,
                status="published",
                character_id="asuna",
                anime="Sword Art Online",
                tags="azul",
                category="waifu",
            )
        )

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup", id=-100),
        from_user=SimpleNamespace(id=7),
        text="/catalogo asuna",
        answer=answer,
    )
    await module.catalog_command(message)

    async with database.session() as session:
        rows = list(
            await session.scalars(
                select(WorldUsageStat).where(
                    WorldUsageStat.entry_key == "catalog_search",
                    WorldUsageStat.scope_type == "user_chat",
                )
            )
        )

    assert rows
    assert rows[0].scope_id == "7:-100"
    await database.close()


@pytest.mark.asyncio
async def test_cami_media_long_anime_title_creates_bounded_local_work_id(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cami-anime-id.db'}")
    await database.create_schema()
    module = CamiMediaModule(database, Settings(admin_user_id=7))

    long_title = "A" * 255
    async with database.session() as session:
        asset = MediaAsset(
            telegram_file_id="file-long-anime",
            source_chat_id=7,
            source_message_id=30,
            status="needs_tag",
        )
        session.add(asset)
        await session.flush()
        asset_id = asset.id

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=7),
        from_user=SimpleNamespace(id=7),
        text=f"Hero | {long_title} | azul | waifu",
        answer=answer,
    )
    state = FakeState(asset_id)

    await module.receive_schedule_or_tags(message, state)

    async with database.session() as session:
        work = await session.scalar(
            select(AnimeWork)
        )

    assert work is not None
    assert len(work.id) <= 128
    assert work.title == long_title
    await database.close()
