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


@pytest.mark.asyncio
async def test_media_queue_summary_counts_pipeline_states(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'media-queue.db'}")
    await database.create_schema()
    library = MediaLibrary()

    async with database.session() as session:
        session.add_all(
            [
                MediaAsset(
                    telegram_file_id="q1",
                    source_chat_id=7,
                    source_message_id=1,
                    status="cami_inbox",
                ),
                MediaAsset(
                    telegram_file_id="q2",
                    source_chat_id=7,
                    source_message_id=2,
                    status="needs_tag",
                ),
                MediaAsset(
                    telegram_file_id="q3",
                    source_chat_id=7,
                    source_message_id=3,
                    status="scheduled",
                ),
                MediaAsset(
                    telegram_file_id="q4",
                    source_chat_id=7,
                    source_message_id=4,
                    status="delivery_unknown",
                ),
                MediaAsset(
                    telegram_file_id="q5",
                    source_chat_id=7,
                    source_message_id=5,
                    status="published",
                ),
            ]
        )

    async with database.session() as session:
        summary = await library.queue_summary(session)

    assert summary.inbox == 1
    assert summary.needs_tag == 1
    assert summary.waiting_schedule == 0
    assert summary.scheduled == 1
    assert summary.publishing == 0
    assert summary.delivery_unknown == 1
    assert summary.published == 1
    assert summary.oldest_actionable_at is not None
    await database.close()


@pytest.mark.asyncio
async def test_pending_returns_cami_inbox_assets(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'media-pending.db'}")
    await database.create_schema()
    library = MediaLibrary()

    async with database.session() as session:
        session.add_all(
            [
                MediaAsset(
                    telegram_file_id="p1",
                    source_chat_id=7,
                    source_message_id=11,
                    status="cami_inbox",
                ),
                MediaAsset(
                    telegram_file_id="p2",
                    source_chat_id=7,
                    source_message_id=12,
                    status="tagged",
                ),
            ]
        )

    async with database.session() as session:
        pending = await library.pending(session)

    assert [asset.telegram_file_id for asset in pending] == ["p1"]
    await database.close()

