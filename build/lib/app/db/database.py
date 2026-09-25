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
from app.db import world_models  # noqa: F401 - registers world observation tables
from app.db import card_vault_models  # noqa: F401 - registers Ciudad Animals world tables


def _add_column_if_missing(connection, table: str, column: str, definition: str, existing: set[str]) -> None:
    """Apply one additive migration safely when several bot processes start together."""
    if column in existing:
        return
    try:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
    except OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise



def _migrate_game_collection_remove_evolution_stage(connection) -> None:
    """Rebuild the legacy collection table without persisted evolution state."""
    columns = {column["name"] for column in inspect(connection).get_columns("game_collection")}
    if "evolution_stage" not in columns:
        return

    connection.execute(text("DROP TRIGGER IF EXISTS trg_game_collection_validate_insert"))
    connection.execute(text("DROP TRIGGER IF EXISTS trg_game_collection_validate_update"))
    connection.execute(text("""
        CREATE TABLE game_collection__p0 (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL REFERENCES game_profiles(id) ON DELETE CASCADE,
            character_id VARCHAR(100) NOT NULL,
            rarity VARCHAR(32) NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            copies INTEGER NOT NULL DEFAULT 1,
            experience INTEGER NOT NULL DEFAULT 0,
            potential_seed VARCHAR(128),
            obtained_at DATETIME NOT NULL,
            CONSTRAINT uq_collection_character UNIQUE (profile_id, character_id),
            CONSTRAINT ck_game_collection_level_bounds CHECK (level >= 1 AND level <= 30),
            CONSTRAINT ck_game_collection_copies_positive CHECK (copies >= 1),
            CONSTRAINT ck_game_collection_experience_nonnegative CHECK (experience >= 0)
        )
    """))
    connection.execute(text("""
        INSERT INTO game_collection__p0 (
            id, profile_id, character_id, rarity, level, copies, experience,
            potential_seed, obtained_at
        )
        SELECT
            id, profile_id, character_id, rarity, level, copies, experience,
            potential_seed, obtained_at
        FROM game_collection
    """))
    connection.execute(text("DROP TABLE game_collection"))
    connection.execute(text("ALTER TABLE game_collection__p0 RENAME TO game_collection"))
    connection.execute(text("""
        INSERT OR REPLACE INTO sqlite_sequence(name, seq)
        VALUES ('game_collection', COALESCE((SELECT MAX(id) FROM game_collection), 0))
    """))

def _ensure_compatibility(connection) -> None:
    """Apply small additive migrations that create_all cannot perform."""
    inspector = inspect(connection)
    card_columns = {column["name"] for column in inspector.get_columns("card_definitions")}
    _add_column_if_missing(connection, "card_definitions", "card_code", "VARCHAR(32)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "asset_path", "VARCHAR(1024)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "thumbnail_path", "VARCHAR(1024)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "asset_sha256", "VARCHAR(64)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "coin_value", "INTEGER DEFAULT 0", card_columns)
    _add_column_if_missing(connection, "card_definitions", "telegram_protected", "BOOLEAN DEFAULT 1", card_columns)
    _add_column_if_missing(connection, "card_definitions", "custom_emoji_id", "VARCHAR(255)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "telegram_file_id", "VARCHAR(512)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "telegram_file_unique_id", "VARCHAR(255)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "asset_width", "INTEGER", card_columns)
    _add_column_if_missing(connection, "card_definitions", "asset_height", "INTEGER", card_columns)
    _add_column_if_missing(connection, "card_definitions", "asset_mime_type", "VARCHAR(128)", card_columns)
    _add_column_if_missing(connection, "card_definitions", "phash", "VARCHAR(64)", card_columns)

    media_columns = {column["name"] for column in inspector.get_columns("media_assets")}
    _add_column_if_missing(connection, "media_assets", "request_id", "BIGINT REFERENCES fan_requests(id) ON DELETE SET NULL", media_columns)
    _add_column_if_missing(connection, "media_assets", "published_group_message_id", "BIGINT", media_columns)
    _add_column_if_missing(connection, "media_assets", "published_page_message_id", "BIGINT", media_columns)
    _add_column_if_missing(connection, "media_assets", "published_request_message_id", "BIGINT", media_columns)
    _add_column_if_missing(connection, "media_assets", "publish_group_chat_id", "BIGINT", media_columns)
    _add_column_if_missing(connection, "media_assets", "media_group_id", "VARCHAR(128)", media_columns)

    profile_columns = {column["name"] for column in inspect(connection).get_columns("game_profiles")}
    _add_column_if_missing(connection, "game_profiles", "gacha_d_streak", "INTEGER NOT NULL DEFAULT 0", profile_columns)

    gacha_roll_columns = {column["name"] for column in inspect(connection).get_columns("game_gacha_rolls")}
    _add_column_if_missing(connection, "game_gacha_rolls", "pity_triggered", "BOOLEAN NOT NULL DEFAULT 0", gacha_roll_columns)
    _add_column_if_missing(connection, "game_gacha_rolls", "card_id", "VARCHAR(255)", gacha_roll_columns)
    _add_column_if_missing(connection, "game_gacha_rolls", "card_variant", "VARCHAR(16)", gacha_roll_columns)

    chat_columns = {column["name"] for column in inspect(connection).get_columns("chats")}
    _add_column_if_missing(connection, "chats", "last_human_message_at", "DATETIME", chat_columns)
    _add_column_if_missing(connection, "chats", "last_bot_message_at", "DATETIME", chat_columns)
    _add_column_if_missing(connection, "chats", "last_social_event_at", "DATETIME", chat_columns)

    trivia_columns = {column["name"] for column in inspect(connection).get_columns("trivia_rounds")}
    _add_column_if_missing(connection, "trivia_rounds", "message_id", "BIGINT", trivia_columns)

    game_collection_columns = {column["name"] for column in inspect(connection).get_columns("game_collection")}
    _add_column_if_missing(
        connection,
        "game_collection",
        "potential_seed",
        "VARCHAR(128)",
        game_collection_columns,
    )
    _migrate_game_collection_remove_evolution_stage(connection)

    event_columns = {column["name"] for column in inspect(connection).get_columns("domain_events")}
    _add_column_if_missing(connection, "domain_events", "heartbeat_at", "DATETIME", event_columns)
    job_columns = {column["name"] for column in inspect(connection).get_columns("durable_jobs")}
    _add_column_if_missing(connection, "durable_jobs", "heartbeat_at", "DATETIME", job_columns)

    verification_columns = {
        column["name"] for column in inspect(connection).get_columns("human_verifications")
    }
    _add_column_if_missing(connection, "human_verifications", "expires_at", "DATETIME", verification_columns)
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_human_verification_expiry "
            "ON human_verifications(status, expires_at)"
        )
    )

    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_media_asset_unique_id "
        "ON media_assets(telegram_unique_id) "
        "WHERE telegram_unique_id IS NOT NULL"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_media_asset_source_message "
        "ON media_assets(source_chat_id, source_message_id)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_media_asset_group "
        "ON media_assets(source_chat_id, media_group_id) "
        "WHERE media_group_id IS NOT NULL"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_card_definition_phash "
        "ON card_definitions(phash) WHERE phash IS NOT NULL"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_card_definition_telegram_unique_id "
        "ON card_definitions(telegram_file_unique_id) WHERE telegram_file_unique_id IS NOT NULL"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_card_definition_code "
        "ON card_definitions(card_code) WHERE card_code IS NOT NULL"
    ))
    connection.execute(text(
        "CREATE TRIGGER IF NOT EXISTS trg_transaction_history_no_update "
        "BEFORE UPDATE ON transaction_history "
        "BEGIN SELECT RAISE(ABORT, 'transaction_history is immutable'); END"
    ))
    connection.execute(text(
        "CREATE TRIGGER IF NOT EXISTS trg_transaction_history_no_delete "
        "BEFORE DELETE ON transaction_history "
        "BEGIN SELECT RAISE(ABORT, 'transaction_history is immutable'); END"
    ))
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
    _ensure_sqlite_invariant_triggers(connection)


def _ensure_sqlite_invariant_triggers(connection) -> None:
    """Backfill critical invariants for SQLite tables created by older versions."""
    triggers = (
        (
            "trg_game_profiles_validate_insert",
            "game_profiles",
            "INSERT",
            """
            WHEN NEW.level < 1
              OR NEW.experience < 0
              OR NEW.points < 0
              OR NEW.coins < 0
              OR NEW.gacha_d_streak < 0
            BEGIN
                SELECT RAISE(ABORT, 'invalid game profile invariant');
            END
            """,
        ),
        (
            "trg_game_profiles_validate_update",
            "game_profiles",
            "UPDATE OF level, experience, points, coins, gacha_d_streak",
            """
            WHEN NEW.level < 1
              OR NEW.experience < 0
              OR NEW.points < 0
              OR NEW.coins < 0
              OR NEW.gacha_d_streak < 0
            BEGIN
                SELECT RAISE(ABORT, 'invalid game profile invariant');
            END
            """,
        ),
        (
            "trg_game_collection_validate_insert",
            "game_collection",
            "INSERT",
            """
            WHEN NEW.level < 1
              OR NEW.level > 30
              OR NEW.copies < 1
              OR NEW.experience < 0
            BEGIN
                SELECT RAISE(ABORT, 'invalid game collection invariant');
            END
            """,
        ),
        (
            "trg_game_collection_validate_update",
            "game_collection",
            "UPDATE OF level, copies, experience",
            """
            WHEN NEW.level < 1
              OR NEW.level > 30
              OR NEW.copies < 1
              OR NEW.experience < 0
            BEGIN
                SELECT RAISE(ABORT, 'invalid game collection invariant');
            END
            """,
        ),
        (
            "trg_point_transaction_validate_insert",
            "point_transactions",
            "INSERT",
            """
            WHEN NEW.amount = 0
            BEGIN
                SELECT RAISE(ABORT, 'point transaction amount cannot be zero');
            END
            """,
        ),
        (
            "trg_point_transaction_validate_update",
            "point_transactions",
            "UPDATE OF amount",
            """
            WHEN NEW.amount = 0
            BEGIN
                SELECT RAISE(ABORT, 'point transaction amount cannot be zero');
            END
            """,
        ),
        (
            "trg_point_transaction_validate_reference_insert",
            "point_transactions",
            "INSERT",
            """
            WHEN (NEW.reference_type IS NULL AND NEW.reference_id IS NOT NULL)
              OR (NEW.reference_type IS NOT NULL AND NEW.reference_id IS NULL)
            BEGIN
                SELECT RAISE(ABORT, 'point transaction reference pair must be complete');
            END
            """,
        ),
        (
            "trg_point_transaction_validate_reference_update",
            "point_transactions",
            "UPDATE OF reference_type, reference_id",
            """
            WHEN (NEW.reference_type IS NULL AND NEW.reference_id IS NOT NULL)
              OR (NEW.reference_type IS NOT NULL AND NEW.reference_id IS NULL)
            BEGIN
                SELECT RAISE(ABORT, 'point transaction reference pair must be complete');
            END
            """,
        ),
        (
            "trg_game_encounter_validate_status_insert",
            "game_encounters",
            "INSERT",
            """
            WHEN NEW.status NOT IN ('active', 'captured', 'closed', 'expired', 'cancelled')
            BEGIN
                SELECT RAISE(ABORT, 'invalid game encounter status');
            END
            """,
        ),
        (
            "trg_game_encounter_validate_status_update",
            "game_encounters",
            "UPDATE OF status",
            """
            WHEN NEW.status NOT IN ('active', 'captured', 'closed', 'expired', 'cancelled')
            BEGIN
                SELECT RAISE(ABORT, 'invalid game encounter status');
            END
            """,
        ),
        (
            "trg_rare_drop_approval_validate_status_insert",
            "rare_drop_approvals",
            "INSERT",
            """
            WHEN NEW.status NOT IN ('pending', 'approved', 'rejected')
            BEGIN
                SELECT RAISE(ABORT, 'invalid rare drop approval status');
            END
            """,
        ),
        (
            "trg_rare_drop_approval_validate_status_update",
            "rare_drop_approvals",
            "UPDATE OF status",
            """
            WHEN NEW.status NOT IN ('pending', 'approved', 'rejected')
            BEGIN
                SELECT RAISE(ABORT, 'invalid rare drop approval status');
            END
            """,
        ),
        (
            "trg_fan_request_validate_points_insert",
            "fan_requests",
            "INSERT",
            """
            WHEN NEW.points_cost < 0
            BEGIN
                SELECT RAISE(ABORT, 'fan request points cost cannot be negative');
            END
            """,
        ),
        (
            "trg_fan_request_validate_points_update",
            "fan_requests",
            "UPDATE OF points_cost",
            """
            WHEN NEW.points_cost < 0
            BEGIN
                SELECT RAISE(ABORT, 'fan request points cost cannot be negative');
            END
            """,
        ),
        (
            "trg_trivia_round_validate_insert",
            "trivia_rounds",
            "INSERT",
            """
            WHEN NEW.status NOT IN ('active', 'publishing', 'won', 'expired', 'failed', 'delivery_unknown', 'cancelled')
              OR NEW.answer_index < 0
              OR NEW.points <= 0
            BEGIN
                SELECT RAISE(ABORT, 'invalid trivia round invariant');
            END
            """,
        ),
        (
            "trg_trivia_round_validate_update",
            "trivia_rounds",
            "UPDATE OF status, answer_index, points",
            """
            WHEN NEW.status NOT IN ('active', 'won', 'expired', 'failed', 'cancelled')
              OR NEW.answer_index < 0
              OR NEW.points <= 0
            BEGIN
                SELECT RAISE(ABORT, 'invalid trivia round invariant');
            END
            """,
        ),
        (
            "trg_detector_usage_validate_insert",
            "waifu_detector_daily_usage",
            "INSERT",
            """
            WHEN NEW.uses < 0 OR NEW.uses > 3
            BEGIN
                SELECT RAISE(ABORT, 'detector daily usage out of bounds');
            END
            """,
        ),
        (
            "trg_detector_usage_validate_update",
            "waifu_detector_daily_usage",
            "UPDATE OF uses",
            """
            WHEN NEW.uses < 0 OR NEW.uses > 3
            BEGIN
                SELECT RAISE(ABORT, 'detector daily usage out of bounds');
            END
            """,
        ),
        (
            "trg_daily_mission_validate_insert",
            "game_daily_mission_progress",
            "INSERT",
            """
            WHEN NEW.progress < 0 OR NEW.target <= 0
            BEGIN
                SELECT RAISE(ABORT, 'daily mission invariant violated');
            END
            """,
        ),
        (
            "trg_daily_mission_validate_update",
            "game_daily_mission_progress",
            "UPDATE OF progress, target",
            """
            WHEN NEW.progress < 0 OR NEW.target <= 0
            BEGIN
                SELECT RAISE(ABORT, 'daily mission invariant violated');
            END
            """,
        ),
    )
    for name, table, operation, body in triggers:
        connection.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
        connection.execute(
            text(
                f"CREATE TRIGGER {name} "
                f"BEFORE {operation} ON {table} "
                f"{body}"
            )
        )


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
    """Emit an explicit BEGIN, optionally acquiring the SQLite write lock early."""
    mode = connection.get_execution_options().get("sqlite_txn_mode", "DEFERRED")
    if mode not in {"DEFERRED", "IMMEDIATE", "EXCLUSIVE"}:
        raise ValueError(f"Unsupported SQLite transaction mode: {mode}")
    connection.exec_driver_sql(f"BEGIN {mode}")


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
    async def session(self, *, write: bool = False) -> AsyncIterator[AsyncSession]:
        """Open one transaction boundary and commit only after all work succeeds."""
        async with self.sessions() as session:
            try:
                if write and self.engine.dialect.name == "sqlite":
                    await session.connection(execution_options={"sqlite_txn_mode": "IMMEDIATE"})
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        await self.engine.dispose()
