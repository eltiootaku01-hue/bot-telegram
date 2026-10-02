# -*- coding: utf-8 -*-
"""Runtime persistence for the Café Otaku Social World."""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Iterator
from urllib.parse import quote
from uuid import UUID, uuid4

from bot_ia.paths import PROJECT_ROOT


CAFE_WORLD_DB_PATH = PROJECT_ROOT / "config" / "bot_ia_events.sqlite3"
SOCIAL_SCHEMA_VERSION = 1
SOCIAL_SCHEMA_NAME = "cafe_world"
BUSY_TIMEOUT_MS = 15_000
TELEGRAM_EVENT_LEDGER_APPLICATION_ID = 0x54474556

SESSION_ACTIVE = "ACTIVE"
SESSION_EXPIRED = "EXPIRED"
SESSION_CLOSED = "CLOSED"
SESSION_STATES = frozenset(
    {SESSION_ACTIVE, SESSION_EXPIRED, SESSION_CLOSED}
)

MEMBERSHIP_ACTIVE = "ACTIVE"
MEMBERSHIP_LEFT = "LEFT"
MEMBERSHIP_EXPIRED = "EXPIRED"
MEMBERSHIP_STATES = frozenset(
    {MEMBERSHIP_ACTIVE, MEMBERSHIP_LEFT, MEMBERSHIP_EXPIRED}
)

_ACTOR_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+:[^:\\s:]+$")


class CafeWorldPersistenceError(RuntimeError):
    """Base error for Social World persistence failures."""


class CafeWorldConfigurationError(CafeWorldPersistenceError):
    """Social World persistence configuration/schema is invalid."""


class CafeWorldNotFoundError(CafeWorldPersistenceError):
    """Requested Social World record does not exist."""


class CafeWorldConflictError(CafeWorldPersistenceError):
    """Optimistic concurrency or database constraint conflict."""


class CafeWorldStateError(CafeWorldPersistenceError):
    """Requested state transition is not valid."""


class CafeWorldAuthorizationError(CafeWorldPersistenceError):
    """The caller does not own the requested participant membership."""


@dataclass(frozen=True, slots=True)
class CafeSession:
    session_id: str
    room_ref: str
    status: str
    created_at: str
    last_activity_at: str
    expires_at: str
    closed_at: str | None
    version: int


@dataclass(frozen=True, slots=True)
class CafeParticipant:
    participant_id: str
    session_id: str
    actor_key: str
    membership_state: str
    joined_at: str
    last_seen_at: str
    left_at: str | None
    version: int


@dataclass(frozen=True, slots=True)
class CafeJoinResult:
    session: CafeSession
    participant: CafeParticipant


def build_room_ref(
    chat_id: str,
    message_thread_id: int,
    room_key: str,
) -> str:
    """Build a canonical server-derived Telegram Room reference."""
    clean_chat_id = str(chat_id).strip()
    clean_room_key = str(room_key).strip()
    try:
        thread_id = int(message_thread_id)
    except (TypeError, ValueError) as error:
        raise ValueError("message_thread_id must be an integer") from error
    if not clean_chat_id:
        raise ValueError("chat_id is required")
    if thread_id < 0:
        raise ValueError("message_thread_id cannot be negative")
    if not clean_room_key:
        raise ValueError("room_key is required")
    return (
        "telegram:"
        + quote(clean_chat_id, safe="")
        + ":topic:"
        + str(thread_id)
        + ":"
        + quote(clean_room_key, safe="")
    )


def _validate_actor_key(actor_key: str) -> str:
    value = str(actor_key).strip()
    if not _ACTOR_KEY_PATTERN.fullmatch(value):
        raise ValueError("actor_key must use <platform>:<platform_user_id>")
    return value


def _utc_datetime(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return result.astimezone(timezone.utc)


def _timestamp(value: datetime | None) -> str:
    return _utc_datetime(value).isoformat()


def _parse_timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(str(value))
    except ValueError as error:
        raise CafeWorldPersistenceError("invalid_persisted_timestamp") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise CafeWorldPersistenceError("invalid_persisted_timestamp")
    return result.astimezone(timezone.utc)


def _uuid_text(value: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError, TypeError) as error:
        raise CafeWorldPersistenceError("invalid_persisted_uuid") from error
    return str(parsed)


class CafeWorldStore:
    """Owns only CafeSession and CafeParticipant on the shared event host."""

    def __init__(
        self,
        database_path: str | Path | None = None,
    ) -> None:
        self.path = (
            Path(database_path).expanduser().resolve()
            if database_path is not None
            else CAFE_WORLD_DB_PATH.resolve()
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self.path,
                timeout=BUSY_TIMEOUT_MS / 1000,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute(
                f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}"
            )
            connection.execute("PRAGMA foreign_keys=ON")
            fk_enabled = int(
                connection.execute(
                    "PRAGMA foreign_keys"
                ).fetchone()[0]
            )
            if fk_enabled != 1:
                raise CafeWorldConfigurationError(
                    "foreign_keys_not_enabled"
                )
            mode = str(
                connection.execute(
                    "PRAGMA journal_mode=WAL"
                ).fetchone()[0]
            ).lower()
            if mode != "wal":
                raise CafeWorldConfigurationError(
                    "wal_not_available"
                )
            connection.execute("PRAGMA synchronous=NORMAL")
            return connection
        except CafeWorldConfigurationError:
            if connection is not None:
                connection.close()
            raise
        except (OSError, sqlite3.DatabaseError) as error:
            if connection is not None:
                connection.close()
            raise CafeWorldPersistenceError(
                "social_world_database_unavailable"
            ) from error

    @contextmanager
    def _transaction(
        self,
        *,
        immediate: bool = True,
    ) -> Iterator[sqlite3.Connection]:
        connection = self._connection()
        try:
            connection.execute(
                "BEGIN IMMEDIATE" if immediate else "BEGIN"
            )
            yield connection
            connection.execute("COMMIT")
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.DatabaseError:
                pass
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._transaction(immediate=True) as connection:
            self._validate_shared_host_metadata(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS social_world_schema_meta (
                    schema_name TEXT PRIMARY KEY,
                    version INTEGER NOT NULL CHECK(version >= 0),
                    updated_at TEXT NOT NULL
                )
                """
            )
            row = connection.execute(
                """
                SELECT version
                FROM social_world_schema_meta
                WHERE schema_name=?
                """,
                (SOCIAL_SCHEMA_NAME,),
            ).fetchone()
            if row is None:
                self._create_schema_v1(connection)
                connection.execute(
                    """
                    INSERT INTO social_world_schema_meta(
                        schema_name, version, updated_at
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        SOCIAL_SCHEMA_NAME,
                        SOCIAL_SCHEMA_VERSION,
                        _timestamp(None),
                    ),
                )
                return

            version = int(row["version"])
            if version > SOCIAL_SCHEMA_VERSION:
                raise CafeWorldConfigurationError(
                    "social_world_schema_is_newer"
                )
            if version < SOCIAL_SCHEMA_VERSION:
                if version != 0:
                    raise CafeWorldConfigurationError(
                        "unsupported_social_world_schema"
                    )
                self._create_schema_v1(connection)
                connection.execute(
                    """
                    UPDATE social_world_schema_meta
                    SET version=?, updated_at=?
                    WHERE schema_name=?
                    """,
                    (
                        SOCIAL_SCHEMA_VERSION,
                        _timestamp(None),
                        SOCIAL_SCHEMA_NAME,
                    ),
                )
                return

            self._verify_schema_v1(connection)

    @staticmethod
    def _validate_shared_host_metadata(
        connection: sqlite3.Connection,
    ) -> None:
        application_id = int(
            connection.execute(
                "PRAGMA application_id"
            ).fetchone()[0]
        )
        user_version = int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        )
        if application_id not in {
            0,
            TELEGRAM_EVENT_LEDGER_APPLICATION_ID,
        }:
            raise CafeWorldConfigurationError(
                "shared_event_host_belongs_to_unknown_application"
            )
        if user_version not in {0, 1}:
            raise CafeWorldConfigurationError(
                "shared_event_host_has_unsupported_version"
            )

    @staticmethod
    def _create_schema_v1(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS CafeSession (
                session_id TEXT PRIMARY KEY NOT NULL,
                room_ref TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('ACTIVE', 'EXPIRED', 'CLOSED')),
                created_at TEXT NOT NULL,
                last_activity_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                closed_at TEXT,
                version INTEGER NOT NULL CHECK(version >= 1),
                CHECK(
                    (status = 'CLOSED' AND closed_at IS NOT NULL)
                    OR
                    (status != 'CLOSED' AND closed_at IS NULL)
                )
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                ux_CafeSession_active_room
            ON CafeSession(room_ref)
            WHERE status='ACTIVE'
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                ix_CafeSession_active_expiry
            ON CafeSession(expires_at)
            WHERE status='ACTIVE'
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS CafeParticipant (
                participant_id TEXT PRIMARY KEY NOT NULL,
                session_id TEXT NOT NULL,
                actor_key TEXT NOT NULL,
                membership_state TEXT NOT NULL
                    CHECK(
                        membership_state IN ('ACTIVE', 'LEFT', 'EXPIRED')
                    ),
                joined_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                left_at TEXT,
                version INTEGER NOT NULL CHECK(version >= 1),
                CHECK(
                    (membership_state = 'LEFT' AND left_at IS NOT NULL)
                    OR
                    (membership_state != 'LEFT' AND left_at IS NULL)
                ),
                FOREIGN KEY(session_id)
                    REFERENCES CafeSession(session_id)
                    ON DELETE RESTRICT
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                ux_CafeParticipant_active_actor
            ON CafeParticipant(session_id, actor_key)
            WHERE membership_state='ACTIVE'
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                ix_CafeParticipant_session_state
            ON CafeParticipant(session_id, membership_state)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                ix_CafeParticipant_actor_key
            ON CafeParticipant(actor_key)
            """
        )

    @staticmethod
    def _verify_schema_v1(connection: sqlite3.Connection) -> None:
        required_tables = {"CafeSession", "CafeParticipant"}
        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name IN ('CafeSession', 'CafeParticipant')
                """
            )
        }
        if tables != required_tables:
            raise CafeWorldConfigurationError(
                "social_world_schema_incomplete"
            )

        required_indexes = {
            "ux_CafeSession_active_room",
            "ix_CafeSession_active_expiry",
            "ux_CafeParticipant_active_actor",
            "ix_CafeParticipant_session_state",
            "ix_CafeParticipant_actor_key",
        }
        indexes = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='index'
                  AND name LIKE 'ux_CafeSession_%'
                UNION ALL
                SELECT name
                FROM sqlite_master
                WHERE type='index'
                  AND name LIKE 'ix_CafeSession_%'
                UNION ALL
                SELECT name
                FROM sqlite_master
                WHERE type='index'
                  AND name LIKE 'ux_CafeParticipant_%'
                UNION ALL
                SELECT name
                FROM sqlite_master
                WHERE type='index'
                  AND name LIKE 'ix_CafeParticipant_%'
                """
            )
        }
        if not required_indexes <= indexes:
            raise CafeWorldConfigurationError(
                "social_world_schema_indexes_incomplete"
            )

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> CafeSession:
        status = str(row["status"])
        if status not in SESSION_STATES:
            raise CafeWorldPersistenceError("invalid_persisted_session_status")
        version = int(row["version"])
        if version < 1:
            raise CafeWorldPersistenceError("invalid_persisted_session_version")
        _parse_timestamp(row["created_at"])
        _parse_timestamp(row["last_activity_at"])
        _parse_timestamp(row["expires_at"])
        if row["closed_at"] is not None:
            _parse_timestamp(row["closed_at"])
        return CafeSession(
            session_id=_uuid_text(row["session_id"]),
            room_ref=str(row["room_ref"]),
            status=status,
            created_at=str(row["created_at"]),
            last_activity_at=str(row["last_activity_at"]),
            expires_at=str(row["expires_at"]),
            closed_at=(
                None
                if row["closed_at"] is None
                else str(row["closed_at"])
            ),
            version=version,
        )

    @staticmethod
    def _participant_from_row(row: sqlite3.Row) -> CafeParticipant:
        state = str(row["membership_state"])
        if state not in MEMBERSHIP_STATES:
            raise CafeWorldPersistenceError(
                "invalid_persisted_membership_state"
            )
        version = int(row["version"])
        if version < 1:
            raise CafeWorldPersistenceError(
                "invalid_persisted_membership_version"
            )
        _parse_timestamp(row["joined_at"])
        _parse_timestamp(row["last_seen_at"])
        if row["left_at"] is not None:
            _parse_timestamp(row["left_at"])
        return CafeParticipant(
            participant_id=_uuid_text(row["participant_id"]),
            session_id=_uuid_text(row["session_id"]),
            actor_key=_validate_actor_key(row["actor_key"]),
            membership_state=state,
            joined_at=str(row["joined_at"]),
            last_seen_at=str(row["last_seen_at"]),
            left_at=(
                None
                if row["left_at"] is None
                else str(row["left_at"])
            ),
            version=version,
        )

    def _find_active_session_locked(
        self,
        connection: sqlite3.Connection,
        room_ref: str,
    ) -> CafeSession | None:
        row = connection.execute(
            """
            SELECT *
            FROM CafeSession
            WHERE room_ref=? AND status='ACTIVE'
            """,
            (room_ref,),
        ).fetchone()
        return None if row is None else self._session_from_row(row)

    def _expire_session_locked(
        self,
        connection: sqlite3.Connection,
        session: CafeSession,
        now_text: str,
    ) -> CafeSession:
        current = _parse_timestamp(now_text)
        expires = _parse_timestamp(session.expires_at)
        if current < expires:
            raise CafeWorldStateError("session_not_due")

        cursor = connection.execute(
            """
            UPDATE CafeSession
            SET status='EXPIRED',
                version=version+1
            WHERE session_id=?
              AND status='ACTIVE'
              AND expires_at<=?
            """,
            (session.session_id, now_text),
        )
        if cursor.rowcount != 1:
            raise CafeWorldConflictError("session_expiry_conflict")

        connection.execute(
            """
            UPDATE CafeParticipant
            SET membership_state='EXPIRED',
                left_at=NULL,
                version=version+1
            WHERE session_id=?
              AND membership_state='ACTIVE'
            """,
            (session.session_id,),
        )
        row = connection.execute(
            "SELECT * FROM CafeSession WHERE session_id=?",
            (session.session_id,),
        ).fetchone()
        if row is None:
            raise CafeWorldPersistenceError("session_disappeared")
        return self._session_from_row(row)

    def join(
        self,
        room_ref: str,
        actor_key: str,
        *,
        expires_at: datetime,
        now: datetime | None = None,
    ) -> CafeJoinResult:
        clean_room_ref = str(room_ref).strip()
        if not clean_room_ref:
            raise ValueError("room_ref is required")
        clean_actor_key = _validate_actor_key(actor_key)
        current = _utc_datetime(now)
        expiry = _utc_datetime(expires_at)
        if expiry <= current:
            raise ValueError("expires_at must be later than now")
        now_text = current.isoformat()
        expires_text = expiry.isoformat()

        with self._transaction(immediate=True) as connection:
            session = self._find_active_session_locked(
                connection,
                clean_room_ref,
            )
            if session is not None:
                if _parse_timestamp(session.expires_at) <= current:
                    session = self._expire_session_locked(
                        connection,
                        session,
                        now_text,
                    )
                    session = None

            session_created = session is None
            if session is None:
                session_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO CafeSession(
                        session_id, room_ref, status,
                        created_at, last_activity_at, expires_at,
                        closed_at, version
                    ) VALUES (?, ?, 'ACTIVE', ?, ?, ?, NULL, 1)
                    """,
                    (
                        session_id,
                        clean_room_ref,
                        now_text,
                        now_text,
                        expires_text,
                    ),
                )
                session = self._session_from_row(
                    connection.execute(
                        """
                        SELECT *
                        FROM CafeSession
                        WHERE session_id=?
                        """,
                        (session_id,),
                    ).fetchone()
                )

            participant_row = connection.execute(
                """
                SELECT *
                FROM CafeParticipant
                WHERE session_id=?
                  AND actor_key=?
                  AND membership_state='ACTIVE'
                """,
                (session.session_id, clean_actor_key),
            ).fetchone()

            if participant_row is None:
                participant_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO CafeParticipant(
                        participant_id, session_id, actor_key,
                        membership_state, joined_at, last_seen_at,
                        left_at, version
                    ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, NULL, 1)
                    """,
                    (
                        participant_id,
                        session.session_id,
                        clean_actor_key,
                        now_text,
                        now_text,
                    ),
                )
            else:
                participant = self._participant_from_row(participant_row)
                connection.execute(
                    """
                    UPDATE CafeParticipant
                    SET last_seen_at=?,
                        version=version+1
                    WHERE participant_id=?
                      AND membership_state='ACTIVE'
                    """,
                    (now_text, participant.participant_id),
                )

            if not session_created:
                connection.execute(
                    """
                    UPDATE CafeSession
                    SET last_activity_at=?,
                        version=version+1
                    WHERE session_id=? AND status='ACTIVE'
                    """,
                    (now_text, session.session_id),
                )

            session_row = connection.execute(
                """
                SELECT *
                FROM CafeSession
                WHERE session_id=?
                """,
                (session.session_id,),
            ).fetchone()
            participant_row = connection.execute(
                """
                SELECT *
                FROM CafeParticipant
                WHERE session_id=?
                  AND actor_key=?
                  AND membership_state='ACTIVE'
                """,
                (session.session_id, clean_actor_key),
            ).fetchone()
            if session_row is None or participant_row is None:
                raise CafeWorldPersistenceError(
                    "join_state_disappeared"
                )
            return CafeJoinResult(
                session=self._session_from_row(session_row),
                participant=self._participant_from_row(participant_row),
            )

    def get_session(
        self,
        session_id: str,
    ) -> CafeSession:
        clean_id = str(session_id).strip()
        with closing(self._connection()) as connection:
            row = connection.execute(
                "SELECT * FROM CafeSession WHERE session_id=?",
                (clean_id,),
            ).fetchone()
        if row is None:
            raise CafeWorldNotFoundError("session_not_found")
        return self._session_from_row(row)

    def get_active_session(
        self,
        room_ref: str,
        *,
        now: datetime | None = None,
    ) -> CafeSession | None:
        clean_room_ref = str(room_ref).strip()
        current = _utc_datetime(now)
        now_text = current.isoformat()
        with self._transaction(immediate=True) as connection:
            session = self._find_active_session_locked(
                connection,
                clean_room_ref,
            )
            if session is None:
                return None
            if _parse_timestamp(session.expires_at) <= current:
                self._expire_session_locked(
                    connection,
                    session,
                    now_text,
                )
                return None
            return session

    def get_participant(
        self,
        participant_id: str,
    ) -> CafeParticipant:
        clean_id = str(participant_id).strip()
        with closing(self._connection()) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM CafeParticipant
                WHERE participant_id=?
                """,
                (clean_id,),
            ).fetchone()
        if row is None:
            raise CafeWorldNotFoundError("participant_not_found")
        return self._participant_from_row(row)

    def list_active_participants(
        self,
        session_id: str,
    ) -> tuple[CafeParticipant, ...]:
        clean_id = str(session_id).strip()
        with closing(self._connection()) as connection:
            rows = connection.execute(
                """
                SELECT participant.*
                FROM CafeParticipant AS participant
                JOIN CafeSession AS session
                  ON session.session_id=participant.session_id
                WHERE participant.session_id=?
                  AND participant.membership_state='ACTIVE'
                  AND session.status='ACTIVE'
                ORDER BY participant.joined_at, participant.participant_id
                """,
                (clean_id,),
            ).fetchall()
        return tuple(
            self._participant_from_row(row)
            for row in rows
        )

    def leave(
        self,
        participant_id: str,
        actor_key: str,
        *,
        expected_version: int | None = None,
        now: datetime | None = None,
    ) -> CafeParticipant:
        clean_id = str(participant_id).strip()
        clean_actor_key = _validate_actor_key(actor_key)
        now_text = _timestamp(now)

        with self._transaction(immediate=True) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM CafeParticipant
                WHERE participant_id=?
                """,
                (clean_id,),
            ).fetchone()
            if row is None:
                raise CafeWorldNotFoundError("participant_not_found")
            participant = self._participant_from_row(row)
            if participant.actor_key != clean_actor_key:
                raise CafeWorldAuthorizationError(
                    "participant_actor_mismatch"
                )
            if (
                expected_version is not None
                and participant.version != int(expected_version)
            ):
                raise CafeWorldConflictError(
                    "participant_version_conflict"
                )
            if participant.membership_state != MEMBERSHIP_ACTIVE:
                return participant

            session_row = connection.execute(
                """
                SELECT *
                FROM CafeSession
                WHERE session_id=?
                """,
                (participant.session_id,),
            ).fetchone()
            if session_row is None:
                raise CafeWorldPersistenceError(
                    "participant_session_missing"
                )
            session = self._session_from_row(session_row)
            if session.status != SESSION_ACTIVE:
                raise CafeWorldStateError(
                    "active_participant_in_terminal_session"
                )

            cursor = connection.execute(
                """
                UPDATE CafeParticipant
                SET membership_state='LEFT',
                    last_seen_at=?,
                    left_at=?,
                    version=version+1
                WHERE participant_id=?
                  AND actor_key=?
                  AND membership_state='ACTIVE'
                  AND version=?
                """,
                (
                    now_text,
                    now_text,
                    participant.participant_id,
                    clean_actor_key,
                    participant.version,
                ),
            )
            if cursor.rowcount != 1:
                raise CafeWorldConflictError(
                    "participant_leave_conflict"
                )

            connection.execute(
                """
                UPDATE CafeSession
                SET last_activity_at=?,
                    version=version+1
                WHERE session_id=? AND status='ACTIVE'
                """,
                (now_text, session.session_id),
            )

            updated_row = connection.execute(
                """
                SELECT *
                FROM CafeParticipant
                WHERE participant_id=?
                """,
                (participant.participant_id,),
            ).fetchone()
            if updated_row is None:
                raise CafeWorldPersistenceError(
                    "participant_disappeared"
                )
            return self._participant_from_row(updated_row)

    def expire_session(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> CafeSession:
        clean_id = str(session_id).strip()
        current = _utc_datetime(now)
        now_text = current.isoformat()

        with self._transaction(immediate=True) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM CafeSession
                WHERE session_id=?
                """,
                (clean_id,),
            ).fetchone()
            if row is None:
                raise CafeWorldNotFoundError("session_not_found")
            session = self._session_from_row(row)
            if session.status == SESSION_EXPIRED:
                return session
            if session.status != SESSION_ACTIVE:
                raise CafeWorldStateError("invalid_session_transition")
            return self._expire_session_locked(
                connection,
                session,
                now_text,
            )

    def close_session(
        self,
        session_id: str,
        *,
        expected_version: int | None = None,
        now: datetime | None = None,
    ) -> CafeSession:
        clean_id = str(session_id).strip()
        now_text = _timestamp(now)

        with self._transaction(immediate=True) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM CafeSession
                WHERE session_id=?
                """,
                (clean_id,),
            ).fetchone()
            if row is None:
                raise CafeWorldNotFoundError("session_not_found")
            session = self._session_from_row(row)
            if (
                expected_version is not None
                and session.version != int(expected_version)
            ):
                raise CafeWorldConflictError(
                    "session_version_conflict"
                )
            if session.status != SESSION_ACTIVE:
                raise CafeWorldStateError("invalid_session_transition")

            cursor = connection.execute(
                """
                UPDATE CafeSession
                SET status='CLOSED',
                    last_activity_at=?,
                    closed_at=?,
                    version=version+1
                WHERE session_id=?
                  AND status='ACTIVE'
                  AND version=?
                """,
                (
                    now_text,
                    now_text,
                    session.session_id,
                    session.version,
                ),
            )
            if cursor.rowcount != 1:
                raise CafeWorldConflictError(
                    "session_close_conflict"
                )

            # A closed session cannot retain an ACTIVE membership. The
            # membership history is preserved and becomes EXPIRED; no rows
            # are deleted.
            connection.execute(
                """
                UPDATE CafeParticipant
                SET membership_state='EXPIRED',
                    left_at=NULL,
                    version=version+1
                WHERE session_id=?
                  AND membership_state='ACTIVE'
                """,
                (session.session_id,),
            )
            updated_row = connection.execute(
                """
                SELECT *
                FROM CafeSession
                WHERE session_id=?
                """,
                (session.session_id,),
            ).fetchone()
            if updated_row is None:
                raise CafeWorldPersistenceError(
                    "session_disappeared"
                )
            return self._session_from_row(updated_row)

    def close(self) -> None:
        """Store operations use short-lived connections and need no pool."""
        return None
