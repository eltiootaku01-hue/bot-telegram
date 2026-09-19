import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import MediaAsset
from app.modules.cami_media.publisher import CamiMediaPublisher


def test_cami_publisher_builds_a_safe_caption() -> None:
    class Asset:
        character_id = "asuna-kirigaya"
        anime = "Sword & Art"
        tags = "waifu, conejita"

    caption = CamiMediaPublisher._caption(Asset())
    assert "asuna kirigaya" in caption
    assert "Sword &amp; Art" in caption
    assert "#waifu" in caption
    assert "#conejita" in caption


@pytest.mark.asyncio
async def test_publish_claim_allows_only_one_concurrent_sender(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'publisher.db'}")
    await database.create_schema()
    bot = AsyncMock()
    bot.send_photo.return_value = SimpleNamespace(message_id=123)
    publisher = CamiMediaPublisher(
        database,
        Settings(publish_page_chat_id=0),
    )
    publisher.topics.get_thread_id = AsyncMock(return_value=77)

    async with database.session() as session:
        session.add(
            SetupSession(
                user_id=1,
                chat_id=-100,
                bot_identity="chie",
                status="configured",
            )
        )
        session.add(
            MediaAsset(
                telegram_file_id="file-1",
                source_chat_id=-200,
                source_message_id=1,
                status="scheduled",
                publish_group=True,
                publish_page=False,
            )
        )

    async with database.session() as session:
        asset = await session.scalar(select(MediaAsset))
        assert asset is not None
        asset_id = asset.id

    await asyncio.gather(
        publisher.publish(bot, {"asset_id": asset_id, "destination": "group"}),
        publisher.publish(bot, {"asset_id": asset_id, "destination": "group"}),
    )

    async with database.session() as session:
        asset = await session.get(MediaAsset, asset_id)

    assert asset is not None
    assert asset.status == "published"
    assert asset.published_group_message_id == 123
    assert bot.send_photo.await_count == 1
    await database.close()


@pytest.mark.asyncio
async def test_publish_rejects_unauthorized_group_before_claim(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'publisher-unauthorized.db'}")
    await database.create_schema()
    bot = AsyncMock()
    publisher = CamiMediaPublisher(
        database,
        Settings(authorized_chat_ids="-100123", publish_page_chat_id=0),
    )

    async with database.session() as session:
        session.add(
            SetupSession(
                user_id=1,
                chat_id=-100999,
                bot_identity="chie",
                status="configured",
            )
        )
        asset = MediaAsset(
            telegram_file_id="file-unauthorized",
            source_chat_id=-200,
            source_message_id=2,
            status="scheduled",
            publish_group=True,
            publish_page=False,
        )
        session.add(asset)
        await session.flush()
        asset_id = asset.id

    with pytest.raises(RuntimeError, match="not authorized"):
        await publisher.publish(bot, {"asset_id": asset_id, "destination": "group"})

    bot.send_photo.assert_not_awaited()

    async with database.session() as session:
        saved = await session.get(MediaAsset, asset_id)

    assert saved is not None
    assert saved.status == "scheduled"
    await database.close()
