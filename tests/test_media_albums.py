import pytest

from app.db.database import Database
from app.db.models import MediaAsset
from app.media.albums import MediaAlbumService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'albums.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_album_identity_is_unique_and_prompt_is_single_use(database):
    service = MediaAlbumService()

    async with database.session() as session:
        first, created = await service.get_or_create(
            session,
            source_chat_id=7,
            media_group_id="album-42",
            owner_user_id=99,
        )
        second, created_again = await service.get_or_create(
            session,
            source_chat_id=7,
            media_group_id="album-42",
            owner_user_id=99,
        )

        assert created is True
        assert created_again is False
        assert first.id == second.id
        assert await service.claim_prompt(session, first.id) is True
        assert await service.claim_prompt(session, first.id) is False


@pytest.mark.asyncio
async def test_album_items_are_ordered_by_source_message(database):
    service = MediaAlbumService()

    async with database.session() as session:
        album, _ = await service.get_or_create(
            session,
            source_chat_id=7,
            media_group_id="album-7",
            owner_user_id=99,
        )
        session.add_all(
            [
                MediaAsset(
                    telegram_file_id="file-b",
                    telegram_unique_id="unique-b",
                    source_chat_id=7,
                    source_message_id=20,
                    media_group_id="album-7",
                    status="cami_inbox",
                ),
                MediaAsset(
                    telegram_file_id="file-a",
                    telegram_unique_id="unique-a",
                    source_chat_id=7,
                    source_message_id=19,
                    media_group_id="album-7",
                    status="cami_inbox",
                ),
            ]
        )

    async with database.session() as session:
        items = await service.items(
            session,
            source_chat_id=7,
            media_group_id="album-7",
        )

    assert [item.source_message_id for item in items] == [19, 20]


def test_album_action_callback_is_small_and_explicit():
    from app.ui.media_keyboards import cami_album_actions

    markup = cami_album_actions(123)
    data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert data == ["cami:album:tag:123"]
    assert all(len(value) <= 64 for value in data)
