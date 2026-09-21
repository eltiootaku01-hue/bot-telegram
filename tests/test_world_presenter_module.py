from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.modules.world.presenter import WorldPresentationModule


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'world-presenter.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_presenter_module_owns_only_its_identity_world_claims(database):
    module = WorldPresentationModule(
        database,
        BotIdentity.SUNNA,
        settings=Settings(authorized_chat_ids="-100"),
    )

    bot = AsyncMock()
    bot.send_message.return_value = SimpleNamespace(message_id=123)

    await module.on_startup(bot)

    assert module.runtime is not None
    assert module.runtime.presenter_key == "existing_bot:sunna"

    await module.on_shutdown()
