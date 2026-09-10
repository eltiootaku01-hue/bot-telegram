import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db import community_models  # noqa: F401 - registers forum topic tables
from app.db import trivia_models  # noqa: F401 - registers trivia tables


def _add_column_if_missing(connection, table: str, column: str, definition: str, existing: set[str]) -> None:
    """Apply one additive migration safely when several bot processes start together."""
    if column in existing:
        return
    try:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
    except OperationalError as exc:
        # Another bot process may have completed the same additive migration between
        # inspect() and ALTER TABLE. SQLite has no IF NOT EXISTS for ADD COLUMN.
        if "duplicate column name" not in str(exc).lower():
            raise


def _ensure_compatibility(connection) -> None:
    """Apply small additive migrations that create_all cannot perform."""
    inspector = inspect(connection)
    media_columns = {column["name"] for column in inspector.get_columns("media_assets")}
    _add_column_if_missing(
        connection,
        "media_assets",
        "request_id",
        "BIGINT REFERENCES fan_requests(id) ON DELETE SET NULL",
        media_columns,
    )
    _add_column_if_missing(
        connection,
        "media_assets",
        "published_group_message_id",
        "BIGINT",
        media_columns,
    )
    _add_column_if_missing(
        connection,
        "media_assets",
        "published_page_message_id",
        "BIGINT",
        media_columns,
    )
    _add_column_if_missing(
        connection,
        "media_assets",
        "published_request_message_id",
        "BIGINT",
        media_columns,
    )

    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fan_request_source "
        "ON fan_requests(user_id, chat_id, source_message_id) "
        "WHERE source_message_id IS NOT NULL"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_game_encounter_chat "
        "ON game_encounters(chat_id) WHERE status = 'active'"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_trivia_round_chat "
        "ON trivia_rounds(chat_id) WHERE status = 'active'"
    ))


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Tune SQLite for the four bot processes sharing one local database."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


class Database:
    """Async SQLAlchemy gateway shared by Telegram, games and future web admin."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, future=True)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _configure_sqlite_connection)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        """Initialize the shared schema safely when multiple bots start together."""
        for attempt in range(3):
            try:
                async with self.engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                    await connection.run_sync(_ensure_compatibility)
                return
            except OperationalError as exc:
                message = str(exc).lower()
                concurrent_schema_race = (
                    "already exists" in message and "table" in message
                ) or "database is locked" in message or "database table is locked" in message
                if not concurrent_schema_race or attempt == 2:
                    raise
                await asyncio.sleep(0.1 * (2**attempt))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
