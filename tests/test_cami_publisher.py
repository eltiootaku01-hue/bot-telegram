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
        Settings(authorized_chat_ids="-100", publish_page_chat_id=0),
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


@pytest.mark.asyncio
async def test_request_publication_ignores_archived_asset(tmp_path) -> None:
    from app.db.models import FanRequest

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'archived-request.db'}")
    await database.create_schema()
    bot = AsyncMock()
    publisher = CamiMediaPublisher(
        database,
        Settings(authorized_chat_ids="-100", publish_page_chat_id=0),
    )

    async with database.session() as session:
        from app.db.models import Chat, User

        session.add(
            SetupSession(
                user_id=1,
                chat_id=-100,
                bot_identity="chie",
                status="configured",
            )
        )
        session.add(User(id=7, first_name="Test"))
        session.add(Chat(id=-100, type="supergroup", title="Community"))
        await session.flush()
        request = FanRequest(
            user_id=7,
            chat_id=-100,
            description="test",
            points_cost=50,
            status="processing",
        )
        session.add(request)
        await session.flush()
        asset = MediaAsset(
            telegram_file_id="file-archived-request",
            source_chat_id=-200,
            source_message_id=2,
            request_id=request.id,
            status="archived",
            publish_group=True,
            publish_page=False,
        )
        session.add(asset)
        await session.flush()
        asset_id = asset.id
        request_id = request.id

    await publisher.publish_request(
        bot,
        {"asset_id": asset_id, "request_id": request_id},
    )

    bot.send_photo.assert_not_awaited()

    async with database.session() as session:
        saved = await session.get(MediaAsset, asset_id)

    assert saved is not None
    assert saved.status == "archived"
    await database.close()



@pytest.mark.asyncio
async def test_scheduled_publish_uses_persisted_target_community(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'target-community.db'}")
    await database.create_schema()
    bot = AsyncMock()
    bot.send_photo.return_value = SimpleNamespace(message_id=900)
    publisher = CamiMediaPublisher(
        database,
        Settings(authorized_chat_ids="-100,-200", publish_page_chat_id=0),
    )
    publisher.topics.get_thread_id = AsyncMock(return_value=55)

    async with database.session() as session:
        session.add(
            MediaAsset(
                telegram_file_id="targeted-file",
                source_chat_id=-999,
                source_message_id=3,
                status="scheduled",
                publish_group=True,
                publish_page=False,
                publish_destination="group",
                publish_group_chat_id=-200,
            )
        )

    async with database.session() as session:
        asset = await session.scalar(select(MediaAsset))
        assert asset is not None
        asset_id = asset.id

    await publisher.publish(bot, {"asset_id": asset_id, "destination": "group"})

    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.await_args.args[0] == -200

    async with database.session() as session:
        saved = await session.get(MediaAsset, asset_id)

    assert saved is not None
    assert saved.status == "published"
    assert saved.publish_group_chat_id == -200
    await database.close()


@pytest.mark.asyncio
async def test_request_publish_uses_request_community_not_latest_setup(tmp_path) -> None:
    from app.db.models import Chat, FanRequest, User

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'request-community.db'}")
    await database.create_schema()
    bot = AsyncMock()
    bot.send_photo.return_value = SimpleNamespace(message_id=901)
    publisher = CamiMediaPublisher(
        database,
        Settings(authorized_chat_ids="-100,-200", publish_page_chat_id=0),
    )
    publisher.topics.get_thread_id = AsyncMock(return_value=66)

    async with database.session() as session:
        session.add_all(
            [
                User(id=7, first_name="Requester"),
                Chat(id=-100, type="supergroup", title="Community One"),
                Chat(id=-200, type="supergroup", title="Community Two"),
            ]
        )
        await session.flush()
        request = FanRequest(
            user_id=7,
            chat_id=-200,
            description="request in two",
            points_cost=50,
            status="processing",
        )
        session.add(request)
        await session.flush()
        asset = MediaAsset(
            telegram_file_id="request-target-file",
            source_chat_id=-999,
            source_message_id=4,
            request_id=request.id,
            status="request_ready",
            publish_group=True,
            publish_page=False,
        )
        session.add(asset)
        await session.flush()
        asset_id = asset.id
        request_id = request.id

    await publisher.publish_request(
        bot,
        {"asset_id": asset_id, "request_id": request_id},
    )

    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.await_args.args[0] == -200

    async with database.session() as session:
        saved = await session.get(MediaAsset, asset_id)
        saved_request = await session.get(FanRequest, request_id)

    assert saved is not None
    assert saved.publish_group_chat_id == -200
    assert saved.status == "published_request"
    assert saved_request is not None
    assert saved_request.status == "completed"
    await database.close()



@pytest.mark.asyncio
async def test_scheduled_publish_refuses_unbound_asset_with_multiple_communities(tmp_path) -> None:
    from app.db.models import Chat

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'multi-community-unbound.db'}")
    await database.create_schema()
    bot = AsyncMock()
    publisher = CamiMediaPublisher(
        database,
        Settings(authorized_chat_ids="-100,-200", publish_page_chat_id=0),
    )

    async with database.session() as session:
        session.add_all(
            [
                Chat(id=-100, type="supergroup", title="Community One"),
                Chat(id=-200, type="supergroup", title="Community Two"),
                SetupSession(
                    user_id=1,
                    chat_id=-100,
                    bot_identity="chie",
                    status="configured",
                ),
                SetupSession(
                    user_id=2,
                    chat_id=-200,
                    bot_identity="chie",
                    status="configured",
                ),
                MediaAsset(
                    telegram_file_id="unbound-multi",
                    source_chat_id=-999,
                    source_message_id=5,
                    status="scheduled",
                    publish_group=True,
                    publish_page=False,
                    publish_destination="group",
                ),
            ]
        )
        await session.commit()

    async with database.session() as session:
        asset = await session.scalar(select(MediaAsset))
        assert asset is not None
        asset_id = asset.id

    with pytest.raises(RuntimeError, match="multiple Chie communities"):
        await publisher.publish(bot, {"asset_id": asset_id, "destination": "group"})

    bot.send_photo.assert_not_awaited()

    async with database.session() as session:
        saved = await session.get(MediaAsset, asset_id)

    assert saved is not None
    assert saved.status == "scheduled"
    assert saved.publish_group_chat_id is None
    await database.close()
