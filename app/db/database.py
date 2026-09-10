from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db import trivia_models  # noqa: F401 - registers trivia tables in metadata


class Database:
    """Async SQLAlchemy gateway shared by Telegram, games and future web admin."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, future=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
