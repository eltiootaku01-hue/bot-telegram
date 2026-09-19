from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.models import Chat, GameProfile, PointTransaction, User
from app.game.engine import GameEngine
from app.game.gacha import GACHA_COST_POINTS, GachaService


class FixedEngine(GameEngine):
    def __init__(self, rarity):
        self.rarity = rarity

    def roll_gacha(self, seed=None):
        return self.rarity


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'gacha.db'}")
    await database.create_schema()
    async with database.session() as session:
        session.add(User(id=7, first_name="Test"))
        session.add(Chat(id=-100, type="supergroup", title="Community"))
        await session.commit()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_gacha_drops_public_character_and_charges_points(database):
    service = GachaService(FixedEngine.__new__(FixedEngine))
    service.engine.rarity = __import__("app.game.models", fromlist=["Rarity"]).Rarity.D

    async with database.session() as session:
        profile = GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS)
        session.add(profile)
        await session.commit()
        profile_id = profile.id

    service.engine.rarity = __import__("app.game.models", fromlist=["Rarity"]).Rarity.D

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="gacha-1")
        await session.commit()

    assert result is not None
    assert result.granted is True
    assert result.approval is None
    assert result.character.id == "anya"
    assert result.remaining_points == 0

    async with database.session() as session:
        profile = await session.get(GameProfile, profile_id)
        transactions = list(
            await session.scalars(
                __import__("sqlalchemy", fromlist=["select"]).select(PointTransaction).where(
                    PointTransaction.user_id == 7,
                    PointTransaction.chat_id == -100,
                    PointTransaction.reference_type == "gacha",
                    PointTransaction.reference_id == "gacha-1",
                )
            )
        )

    assert profile is not None
    assert profile.points == 0
    assert len(transactions) == 1


@pytest.mark.asyncio
async def test_gacha_high_rarity_creates_approval_without_granting_character(database):
    from app.game.models import Rarity
    from app.db.models import GameCollection, RareDropApproval

    service = GachaService(FixedEngine.__new__(FixedEngine))
    service.engine.rarity = Rarity.B

    async with database.session() as session:
        profile = GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS)
        session.add(profile)
        await session.commit()

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="gacha-rare")
        await session.commit()

    assert result is not None
    assert result.granted is False
    assert result.approval is not None
    assert result.character.id == "taiga"

    async with database.session() as session:
        approval = await session.get(RareDropApproval, result.approval.id)
        collection = await session.scalar(
            __import__("sqlalchemy", fromlist=["select"]).select(GameCollection).where(
                GameCollection.character_id == "taiga"
            )
        )

    assert approval is not None
    assert approval.status == "pending"
    assert collection is None


@pytest.mark.asyncio
async def test_gacha_requires_enough_points(database):
    from app.game.models import Rarity

    service = GachaService(FixedEngine.__new__(FixedEngine))
    service.engine.rarity = Rarity.D

    async with database.session() as session:
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS - 1))
        await session.commit()

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="poor")

    assert result is None
