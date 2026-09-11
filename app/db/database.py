import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db import community_models  # noqa: F401 - registers forum topic tables
from app.db import social_models  # noqa: F401 - registers social wake tables
from app.db import trivia_models  # noqa: F401 - registers trivia tables


def _add_column_if_missing(connection, table: str, column: str, definition: str, existing: set[str]) -> None:
    """Apply one additive migration safely when several bot processes start together."""
    if column in existing:
        return
    try:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
    except OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def _ensure_compatibility(connection) -> None:
    """Apply small additive migrations that create_all cannot perform."""
    inspector = inspect(connection)
    media_columns = {column["name"] for column in inspector.get_columns("media_assets")}
    _add_column_if_missing(connection, "media_assets", "request_id", "BIGINT REFERENCES fan_requests(id) ON DELETE SET NULL", media_columns)
    _add_column_if_missing(connection, "media_assets", "published_group_message_id", "BIGINT", media_columns)
    _add_column_if_missing(connection, "media_assets", "published_page_message_id", "BIGINT", media_columns)
    _add_column_if_missing(connection, "media_assets", "published_request_message_id", "BIGINT", media_columns)

    event_columns = {column["name"] for column in inspector.get_columns("domain_events")}
    _add_column_if_missing(connection, "domain_events", "heartbeat_at", "DATETIME", event_columns)
    job_columns = {column["name"] for column in inspect(connection).get_columns("durable_jobs")}
    _add_column_if_missing(connection, "durable_jobs", "heartbeat_at", "DATETIME", job_columns)

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
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_point_transaction_reference "
        "ON point_transactions(user_id, chat_id, reference_type, reference_id) "
        "WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL"
    ))


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Tune SQLite for the four bot processes sharing one local database."""
    # aiosqlite inherits sqlite3's legacy transaction mode. Explicit BEGIN is
    # required so SAVEPOINTs remain part of the enclosing transaction instead
    # of becoming independently committed work.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


def _begin_sqlite_transaction(connection) -> None:
    """Emit an explicit BEGIN for every SQLAlchemy transaction on SQLite."""
    connection.exec_driver_sql("BEGIN")


class Database:
    """Async SQLAlchemy gateway shared by Telegram, games and future web admin."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, future=True)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _configure_sqlite_connection)
            event.listen(self.engine.sync_engine, "begin", _begin_sqlite_transaction)
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
