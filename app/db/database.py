from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db import community_models  # noqa: F401 - registers forum topic tables
from app.db import trivia_models  # noqa: F401 - registers trivia tables


def _ensure_compatibility(connection) -> None:
    """Apply small additive migrations that create_all cannot perform."""
    inspector = inspect(connection)
    media_columns = {column["name"] for column in inspector.get_columns("media_assets")}
    if "request_id" not in media_columns:
        connection.execute(text(
            "ALTER TABLE media_assets ADD COLUMN request_id BIGINT "
            "REFERENCES fan_requests(id) ON DELETE SET NULL"
        ))
    if "published_group_message_id" not in media_columns:
        connection.execute(text(
            "ALTER TABLE media_assets ADD COLUMN published_group_message_id BIGINT"
        ))
    if "published_page_message_id" not in media_columns:
        connection.execute(text(
            "ALTER TABLE media_assets ADD COLUMN published_page_message_id BIGINT"
        ))
    if "published_request_message_id" not in media_columns:
        connection.execute(text(
            "ALTER TABLE media_assets ADD COLUMN published_request_message_id BIGINT"
        ))

    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fan_request_source "
        "ON fan_requests(user_id, chat_id, source_message_id) "
        "WHERE source_message_id IS NOT NULL"
    ))


class Database:
    """Async SQLAlchemy gateway shared by Telegram, games and future web admin."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, future=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(_ensure_compatibility)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
