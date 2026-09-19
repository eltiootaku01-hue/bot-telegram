import pytest

from app.db.database import Database
from app.db.models import RareDropApproval
from app.game.rare_approval import decide, propose


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_decide_is_single_winner_for_repeated_resolution(database):
    async with database.session() as session:
        request = await propose(
            session,
            character_id="taiga",
            rarity="B",
            target_user_id=7,
            target_chat_id=-100,
        )
        approval_id = request.id

    async with database.session() as session:
        first = await decide(session, approval_id, True)

    async with database.session() as session:
        second = await decide(session, approval_id, False)

    assert first is not None
    assert first.status == "approved"
    assert second is None

    async with database.session() as session:
        stored = await session.get(RareDropApproval, approval_id)

    assert stored is not None
    assert stored.status == "approved"
