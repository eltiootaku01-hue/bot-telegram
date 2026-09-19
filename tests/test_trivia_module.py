import pytest

from unittest.mock import AsyncMock

from app.core.config import Settings
from app.db.database import Database
from app.modules.trivia.module import TriviaModule


@pytest.mark.asyncio
async def test_publish_skips_unauthorized_community_before_database_work() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    module = TriviaModule(database, Settings(authorized_chat_ids="-100123"))

    module._bot = AsyncMock()

    assert await module._publish(-100999) is False
    module._bot.send_message.assert_not_awaited()

    await database.close()
