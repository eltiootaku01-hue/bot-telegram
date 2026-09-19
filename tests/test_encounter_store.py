import pytest

from app.core.time import utc_now
from app.db.database import Database
from app.db.models import GameEncounter
from app.game.encounter_store import EncounterStore


@pytest.mark.asyncio
async def test_finish_transitions_active_encounter_only_once() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    async with database.session() as session:
        encounter = GameEncounter(
            id="finish-once",
            chat_id=-100,
            character_id="anya",
            rarity="D",
            answer="anya",
            expires_at=utc_now(),
            status="active",
        )
        session.add(encounter)
        await session.flush()

        store = EncounterStore()
        first = await store.finish(session, "finish-once", "expired")
        second = await store.finish(session, "finish-once", "cancelled")

        assert first is True
        assert second is False
        await session.commit()

    async with database.session() as session:
        stored = await session.get(GameEncounter, "finish-once")

    assert stored is not None
    assert stored.status == "expired"
    await database.close()


@pytest.mark.asyncio
async def test_finish_rejects_non_terminal_status() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    async with database.session() as session:
        store = EncounterStore()
        with pytest.raises(ValueError, match="Unsupported encounter terminal status"):
            await store.finish(session, "missing", "active")

    await database.close()
