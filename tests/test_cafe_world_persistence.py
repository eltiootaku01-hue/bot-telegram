# -*- coding: utf-8 -*-
"""WORLD-01-D persistence runtime invariants."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
from threading import Barrier
from pathlib import Path

import pytest

from bot_ia.interfaces.telegram_event_ledger import TelegramEventLedger
from bot_ia.persistence.cafe_world import (
    CafeParticipant,
    CafeSession,
    CafeWorldConflictError,
    CafeWorldStateError,
    CafeWorldStore,
    build_room_ref,
)


BASE_TIME = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)


def _expiry(hours: int = 1) -> datetime:
    return BASE_TIME + timedelta(hours=hours)


def _room(chat_id: str = "-100", thread_id: int = 42) -> str:
    return build_room_ref(chat_id, thread_id, "general")


def test_fresh_schema_uses_shared_host_and_isolated_social_version(
    tmp_path: Path,
) -> None:
    database = tmp_path / "config" / "bot_ia_events.sqlite3"
    store = CafeWorldStore(database)

    connection = sqlite3.connect(database)
    try:
        assert database == store.path
        assert int(
            connection.execute("PRAGMA application_id").fetchone()[0]
        ) == 0
        assert int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        ) == 0
        social_version = connection.execute(
            """
            SELECT version
            FROM social_world_schema_meta
            WHERE schema_name='cafe_world'
            """
        ).fetchone()
        assert social_version == (1,)

        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table'
                """
            )
        }
        assert {"CafeSession", "CafeParticipant"} <= tables
        assert "CafeRoom" not in tables
    finally:
        connection.close()


def test_telegram_header_ownership_is_preserved(
    tmp_path: Path,
) -> None:
    database = tmp_path / "config" / "bot_ia_events.sqlite3"
    TelegramEventLedger(database)
    CafeWorldStore(database)

    connection = sqlite3.connect(database)
    try:
        assert int(
            connection.execute("PRAGMA application_id").fetchone()[0]
        ) == TelegramEventLedger.APPLICATION_ID
        assert int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        ) == TelegramEventLedger.SCHEMA_VERSION
        assert connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name='telegram_events'
            """
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_schema_constraints_are_database_owned(tmp_path: Path) -> None:
    database = tmp_path / "config" / "bot_ia_events.sqlite3"
    store = CafeWorldStore(database)
    result = store.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )

    connection = store._connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO CafeSession(
                    session_id, room_ref, status,
                    created_at, last_activity_at, expires_at,
                    closed_at, version
                ) VALUES (?, ?, 'ACTIVE', ?, ?, ?, NULL, 1)
                """,
                (
                    "3f4d5f46-3b8e-4af8-9c6f-4bb1e0c1e11a",
                    result.session.room_ref,
                    BASE_TIME.isoformat(),
                    BASE_TIME.isoformat(),
                    _expiry().isoformat(),
                ),
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO CafeParticipant(
                    participant_id, session_id, actor_key,
                    membership_state, joined_at, last_seen_at,
                    left_at, version
                ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, NULL, 1)
                """,
                (
                    "6b84c1b8-8f63-4871-a3c5-5703e93a6a4b",
                    result.session.session_id,
                    "telegram:123",
                    BASE_TIME.isoformat(),
                    BASE_TIME.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_join_creates_session_and_participant(tmp_path: Path) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    result = store.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )

    assert result.session.status == "ACTIVE"
    assert result.session.version == 1
    assert result.participant.membership_state == "ACTIVE"
    assert result.participant.version == 1
    assert result.session.room_ref == _room()


def test_join_is_idempotent_for_active_actor(tmp_path: Path) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    first = store.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )
    second = store.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME + timedelta(seconds=5),
    )

    assert second.session.session_id == first.session.session_id
    assert second.participant.participant_id == first.participant.participant_id
    assert second.participant.version == 2
    assert second.session.version == 2


def test_leave_is_historical_and_idempotent(tmp_path: Path) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    joined = store.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )

    left = store.leave(
        joined.participant.participant_id,
        "telegram:123",
        now=BASE_TIME + timedelta(seconds=10),
    )
    repeated = store.leave(
        joined.participant.participant_id,
        "telegram:123",
        now=BASE_TIME + timedelta(seconds=20),
    )

    assert left.membership_state == "LEFT"
    assert left.left_at == (BASE_TIME + timedelta(seconds=10)).isoformat()
    assert left.version == 2
    assert repeated == left
    assert store.list_active_participants(joined.session.session_id) == ()


def test_session_expiry_transitions_memberships_atomically(
    tmp_path: Path,
) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    joined_a = store.join(
        _room(),
        "telegram:123",
        expires_at=BASE_TIME + timedelta(seconds=30),
        now=BASE_TIME,
    )
    joined_b = store.join(
        _room(),
        "telegram:456",
        expires_at=BASE_TIME + timedelta(seconds=30),
        now=BASE_TIME + timedelta(seconds=1),
    )

    expired = store.expire_session(
        joined_a.session.session_id,
        now=BASE_TIME + timedelta(seconds=31),
    )
    assert expired.status == "EXPIRED"
    assert expired.closed_at is None
    assert expired.version == 3

    participants = {
        joined_a.participant.participant_id:
        store.get_participant(joined_a.participant.participant_id),
        joined_b.participant.participant_id:
        store.get_participant(joined_b.participant.participant_id),
    }
    assert {
        participant.membership_state
        for participant in participants.values()
    } == {"EXPIRED"}
    assert all(
        participant.left_at is None
        for participant in participants.values()
    )


def test_get_active_session_opportunistically_expires_due_session(
    tmp_path: Path,
) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    joined = store.join(
        _room(),
        "telegram:123",
        expires_at=BASE_TIME + timedelta(seconds=5),
        now=BASE_TIME,
    )

    assert (
        store.get_active_session(
            _room(),
            now=BASE_TIME + timedelta(seconds=6),
        )
        is None
    )
    assert store.get_session(joined.session.session_id).status == "EXPIRED"


def test_close_session_is_terminal_and_expires_active_members(
    tmp_path: Path,
) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    joined = store.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )

    closed = store.close_session(
        joined.session.session_id,
        expected_version=joined.session.version,
        now=BASE_TIME + timedelta(minutes=1),
    )
    assert closed.status == "CLOSED"
    assert closed.closed_at == (
        BASE_TIME + timedelta(minutes=1)
    ).isoformat()
    assert store.list_active_participants(joined.session.session_id) == ()
    assert (
        store.get_participant(joined.participant.participant_id)
        .membership_state
        == "EXPIRED"
    )

    with pytest.raises(CafeWorldStateError):
        store.close_session(
            joined.session.session_id,
            now=BASE_TIME + timedelta(minutes=2),
        )
    with pytest.raises(CafeWorldStateError):
        store.expire_session(
            joined.session.session_id,
            now=BASE_TIME + timedelta(hours=2),
        )


def test_leave_rejects_stale_version(tmp_path: Path) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    joined = store.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )
    left = store.leave(
        joined.participant.participant_id,
        "telegram:123",
        expected_version=1,
        now=BASE_TIME + timedelta(seconds=1),
    )
    assert left.version == 2

    with pytest.raises(CafeWorldConflictError):
        store.leave(
            joined.participant.participant_id,
            "telegram:123",
            expected_version=1,
            now=BASE_TIME + timedelta(seconds=2),
        )


def test_foreign_key_is_enabled_for_every_store_connection(
    tmp_path: Path,
) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    connection = store._connection()
    try:
        assert connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO CafeParticipant(
                    participant_id, session_id, actor_key,
                    membership_state, joined_at, last_seen_at,
                    left_at, version
                ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, NULL, 1)
                """,
                (
                    "f75b8d30-e1a9-4647-94ad-4d07dfd571b6",
                    "1ab1b8a0-7e1a-4ae0-85c8-2390e6c3aead",
                    "telegram:999",
                    BASE_TIME.isoformat(),
                    BASE_TIME.isoformat(),
                ),
            )
    finally:
        connection.rollback()
        connection.close()


def test_persistence_survives_independent_connections(
    tmp_path: Path,
) -> None:
    database = tmp_path / "bot_ia_events.sqlite3"
    store_a = CafeWorldStore(database)
    joined = store_a.join(
        _room(),
        "telegram:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )
    store_a.close()

    store_b = CafeWorldStore(database)
    assert store_b.get_session(joined.session.session_id) == joined.session
    assert (
        store_b.get_participant(joined.participant.participant_id)
        == joined.participant
    )


def test_concurrent_joins_same_room_same_actor_across_independent_stores(
    tmp_path: Path,
) -> None:
    database = tmp_path / "bot_ia_events.sqlite3"
    stores = [CafeWorldStore(database) for _ in range(8)]
    barrier = Barrier(len(stores))

    def join_one(store: CafeWorldStore) -> tuple[str, str]:
        barrier.wait()
        result = store.join(
            _room(),
            "telegram:777",
            expires_at=_expiry(),
            now=BASE_TIME,
        )
        return result.session.session_id, result.participant.participant_id

    with ThreadPoolExecutor(max_workers=len(stores)) as pool:
        outcomes = list(pool.map(join_one, stores))

    assert len({session_id for session_id, _ in outcomes}) == 1
    assert len({participant_id for _, participant_id in outcomes}) == 1

    connection = sqlite3.connect(database)
    try:
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM CafeSession
            WHERE room_ref=? AND status='ACTIVE'
            """,
            (_room(),),
        ).fetchone() == (1,)
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM CafeParticipant
            WHERE actor_key=?
              AND membership_state='ACTIVE'
            """,
            ("telegram:777",),
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_concurrent_joins_same_room_different_actors_share_one_session(
    tmp_path: Path,
) -> None:
    database = tmp_path / "bot_ia_events.sqlite3"
    stores = [CafeWorldStore(database) for _ in range(6)]
    barrier = Barrier(len(stores))

    def join_one(index: int) -> str:
        barrier.wait()
        result = stores[index].join(
            _room(),
            f"telegram:{1000 + index}",
            expires_at=_expiry(),
            now=BASE_TIME,
        )
        return result.session.session_id

    with ThreadPoolExecutor(max_workers=len(stores)) as pool:
        session_ids = list(
            pool.map(join_one, range(len(stores)))
        )

    assert len(set(session_ids)) == 1
    store = stores[0]
    participants = store.list_active_participants(
        store.get_active_session(
            _room(),
            now=BASE_TIME,
        ).session_id
    )
    assert len(participants) == 6


def test_concurrent_join_does_not_create_second_session_after_expiry(
    tmp_path: Path,
) -> None:
    database = tmp_path / "bot_ia_events.sqlite3"
    stores = [CafeWorldStore(database) for _ in range(4)]
    first = stores[0].join(
        _room(),
        "telegram:1",
        expires_at=BASE_TIME + timedelta(seconds=1),
        now=BASE_TIME,
    )
    barrier = Barrier(len(stores))

    def join_after_expiry(store: CafeWorldStore) -> str:
        barrier.wait()
        return store.join(
            _room(),
            "telegram:2",
            expires_at=BASE_TIME + timedelta(hours=2),
            now=BASE_TIME + timedelta(seconds=2),
        ).session.session_id

    with ThreadPoolExecutor(max_workers=len(stores)) as pool:
        ids = list(pool.map(join_after_expiry, stores))

    assert len(set(ids)) == 1
    assert ids[0] != first.session.session_id
    connection = sqlite3.connect(database)
    try:
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM CafeSession
            WHERE room_ref=? AND status='ACTIVE'
            """,
            (_room(),),
        ).fetchone() == (1,)
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM CafeSession
            WHERE room_ref=? AND status='EXPIRED'
            """,
            (_room(),),
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_actor_key_is_not_tcg_user_identity(tmp_path: Path) -> None:
    store = CafeWorldStore(tmp_path / "bot_ia_events.sqlite3")
    result = store.join(
        _room(),
        "discord:123",
        expires_at=_expiry(),
        now=BASE_TIME,
    )
    assert result.participant.actor_key == "discord:123"


def test_room_reference_contains_router_identity_without_cafe_room_table() -> None:
    room_ref = build_room_ref("-100", 42, "general")
    assert room_ref == "telegram:-100:topic:42:general"


def test_cafe_models_have_exact_contract_fields() -> None:
    from dataclasses import fields

    assert [field.name for field in fields(CafeSession)] == [
        "session_id",
        "room_ref",
        "status",
        "created_at",
        "last_activity_at",
        "expires_at",
        "closed_at",
        "version",
    ]
    assert [field.name for field in fields(CafeParticipant)] == [
        "participant_id",
        "session_id",
        "actor_key",
        "membership_state",
        "joined_at",
        "last_seen_at",
        "left_at",
        "version",
    ]


