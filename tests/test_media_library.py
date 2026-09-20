import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import MediaAsset
from app.media.library import MediaLibrary


@pytest.mark.asyncio
async def test_find_existing_matches_stable_telegram_unique_id(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'media-identity.db'}")
    await database.create_schema()
    library = MediaLibrary()

    async with database.session() as session:
        asset = MediaAsset(
            telegram_file_id="file-old",
            telegram_unique_id="unique-image-1",
            source_chat_id=7,
            source_message_id=100,
            status="tagged",
        )
        session.add(asset)
        await session.flush()
        asset_id = asset.id

        existing = await library.find_existing(
            session,
            telegram_file_id="file-new",
            telegram_unique_id="unique-image-1",
            source_chat_id=7,
            source_message_id=999,
        )

        assert existing is not None
        assert existing.id == asset_id

    await database.close()


@pytest.mark.asyncio
async def test_find_existing_matches_source_message_as_final_fallback(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'media-source.db'}")
    await database.create_schema()
    library = MediaLibrary()

    async with database.session() as session:
        asset = MediaAsset(
            telegram_file_id="file-source",
            telegram_unique_id=None,
            source_chat_id=7,
            source_message_id=101,
            status="cami_inbox",
        )
        session.add(asset)
        await session.flush()
        asset_id = asset.id

        existing = await library.find_existing(
            session,
            telegram_file_id="other-file",
            telegram_unique_id=None,
            source_chat_id=7,
            source_message_id=101,
        )

        assert existing is not None
        assert existing.id == asset_id

    await database.close()


@pytest.mark.asyncio
async def test_update_metadata_can_join_outer_transaction(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'media-tx.db'}")
    await database.create_schema()
    library = MediaLibrary()

    async with database.session() as session:
        asset = MediaAsset(
            telegram_file_id="file-tx",
            source_chat_id=7,
            source_message_id=102,
            status="cami_inbox",
        )
        session.add(asset)
        await session.flush()

        await library.update_metadata(
            session,
            asset,
            status="tagged",
            tags="azul,uniforme",
            commit=False,
        )
        await session.rollback()

    async with database.session() as session:
        persisted = await session.scalar(
            select(MediaAsset).where(MediaAsset.telegram_file_id == "file-tx")
        )

    assert persisted is None
    await database.close()
