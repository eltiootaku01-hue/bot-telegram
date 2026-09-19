from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.models import MediaAsset
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
