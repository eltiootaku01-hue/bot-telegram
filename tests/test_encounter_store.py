import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.db.database import Database
from app.db.models import GameAttempt, GameEncounter
from app.game.encounter_store import (
    MAX_ENCOUNTER_PARTICIPANTS,
    EncounterAttemptResult,
    EncounterStore,
)


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'encounters.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_encounter_allows_three_distinct_players_then_closes_registration(database):
    store = EncounterStore()

    async with database.session(write=True) as session:
        session.add(
            GameEncounter(
                id="three-users",
                chat_id=-100,
                character_id="anya",
                rarity="D",
                answer="Anya Forger",
                expires_at=utc_now() + timedelta(minutes=5),
                status="active",
            )
        )

        for user_id in (1, 2, 3):
            result = await store.claim_attempt(
                session,
                "three-users",
                user_id,
                "wrong",
            )
            assert result is EncounterAttemptResult.WRONG

        full = await store.claim_attempt(session, "three-users", 4, "wrong")
        duplicate = await store.claim_attempt(session, "three-users", 2, "wrong")

    assert full is EncounterAttemptResult.FULL
    assert duplicate is EncounterAttemptResult.ALREADY_ATTEMPTED

    async with database.session() as session:
        attempts = list(
            await session.scalars(
                select(GameAttempt).where(GameAttempt.encounter_id == "three-users")
            )
        )

    assert len(attempts) == MAX_ENCOUNTER_PARTICIPANTS


@pytest.mark.asyncio
async def test_encounter_wrong_attempt_never_allows_same_player_again(database):
    store = EncounterStore()

    async with database.session(write=True) as session:
        session.add(
            GameEncounter(
                id="one-user",
                chat_id=-100,
                character_id="anya",
                rarity="D",
                answer="Anya Forger",
                expires_at=utc_now() + timedelta(minutes=5),
                status="active",
            )
        )

        first = await store.claim_attempt(session, "one-user", 7, "wrong")
        second = await store.claim_attempt(session, "one-user", 7, "Anya Forger")

    assert first is EncounterAttemptResult.WRONG
    assert second is EncounterAttemptResult.ALREADY_ATTEMPTED


@pytest.mark.asyncio
async def test_concurrent_encounter_claims_cap_distinct_players_at_three(tmp_path):
    database_a = Database(f"sqlite+aiosqlite:///{tmp_path / 'encounter-race.db'}")
    database_b = Database(f"sqlite+aiosqlite:///{tmp_path / 'encounter-race.db'}")
    await database_a.create_schema()

    async with database_a.session() as session:
        session.add(
            GameEncounter(
                id="race",
                chat_id=-100,
                character_id="anya",
                rarity="D",
                answer="wrong",
                expires_at=utc_now() + timedelta(minutes=5),
                status="active",
            )
        )

    store = EncounterStore()

    async def claim(database, user_id):
        async with database.session(write=True) as session:
            return await store.claim_attempt(session, "race", user_id, "nope")

    results = await asyncio.gather(
        claim(database_a, 1),
        claim(database_b, 2),
        claim(database_a, 3),
        claim(database_b, 4),
    )

    assert sum(result is not EncounterAttemptResult.FULL for result in results) == 3
    assert results.count(EncounterAttemptResult.FULL) == 1

    async with database_a.session() as session:
        attempts = list(
            await session.scalars(
                select(GameAttempt).where(GameAttempt.encounter_id == "race")
            )
        )

    assert len(attempts) == 3
    await database_a.close()
    await database_b.close()
