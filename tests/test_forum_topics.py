import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.community_models import ForumTopic
from app.db.database import Database
from app.services.forum_topics import ForumTopicService


@pytest.mark.asyncio
async def test_concurrent_topic_creation_cleans_the_loser_topic(tmp_path) -> None:
    db_path = tmp_path / "forum-topics.sqlite3"
    database_a = Database(f"sqlite+aiosqlite:///{db_path}")
    await database_a.create_schema()
    database_b = Database(f"sqlite+aiosqlite:///{db_path}")

    bot = AsyncMock()
    entered = 0
    both_entered = asyncio.Event()

    async def create_forum_topic(*, chat_id: int, name: str):
        nonlocal entered
        entered += 1
        if entered == 2:
            both_entered.set()
        await both_entered.wait()
        return SimpleNamespace(message_thread_id=101 + (entered * 101))

    bot.create_forum_topic.side_effect = create_forum_topic

    service_a = ForumTopicService(database_a)
    service_b = ForumTopicService(database_b)

    try:
        results = await asyncio.gather(
            service_a.ensure_topic(bot, -100, "noticias", bot_identity="chie"),
            service_b.ensure_topic(bot, -100, "noticias", bot_identity="chie"),
        )

        assert results[0] == results[1]
        assert results[0] in {202, 303}
        assert bot.create_forum_topic.await_count == 2
        assert bot.delete_forum_topic.await_count == 1

        async with database_a.session() as session:
            rows = list(
                await session.scalars(
                    select(ForumTopic).where(
                        ForumTopic.chat_id == -100,
                        ForumTopic.topic_key == "noticias",
                    )
                )
            )

        assert len(rows) == 1
        assert rows[0].thread_id == results[0]
    finally:
        await database_b.close()
        await database_a.close()
