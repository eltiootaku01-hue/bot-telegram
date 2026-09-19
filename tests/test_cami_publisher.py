import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
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
async def test_publish_claim_allows_only_one_concurrent_sender() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
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
            __import__("app.db.community_models", fromlist=["SetupSession"]).SetupSession(
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
        asset = await session.scalar(
            __import__("sqlalchemy", fromlist=["select"]).select(MediaAsset)
        )
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
