import asyncio

import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import Chat, GameCollection, GameGachaRoll, GameProfile, PointTransaction, RareDropApproval, User
from app.game.engine import GameEngine
from app.game.gacha import GACHA_COST_POINTS, GachaService
from app.game.models import Rarity


class FixedEngine(GameEngine):
    def __init__(self, rarity: Rarity) -> None:
        self.rarity = rarity

    def roll_gacha(self, seed: str | None = None) -> Rarity:
        return self.rarity


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'gacha.db'}")
    await database.create_schema()
    async with database.session() as session:
        session.add(User(id=7, first_name="Test"))
        session.add(Chat(id=-100, type="supergroup", title="Community"))
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_gacha_drops_public_character_and_charges_points(database):
    async with database.session() as session:
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS))
    service = GachaService(FixedEngine(Rarity.D))

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="gacha-1")
        await session.commit()

    assert result is not None
    assert result.granted is True
    assert result.approval is None
    assert result.character.id == "anya"
    assert result.remaining_points == 0

    async with database.session() as session:
        profile = await session.scalar(
            select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
        )
        collection = await session.scalar(
            select(GameCollection).where(GameCollection.character_id == "anya")
        )
        transaction = await session.scalar(
            select(PointTransaction).where(
                PointTransaction.user_id == 7,
                PointTransaction.chat_id == -100,
                PointTransaction.reference_type == "gacha",
                PointTransaction.reference_id == "gacha-1",
            )
        )

    assert profile is not None and profile.points == 0
    assert collection is not None and collection.copies == 1
    assert transaction is not None and transaction.amount == -GACHA_COST_POINTS


@pytest.mark.asyncio
async def test_gacha_high_rarity_creates_approval_without_granting_character(database):
    async with database.session() as session:
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS))
    service = GachaService(FixedEngine(Rarity.B))

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="gacha-rare")
        await session.commit()

    assert result is not None
    assert result.granted is False
    assert result.approval is not None
    assert result.character.rarity is Rarity.B

    async with database.session() as session:
        approval = await session.get(RareDropApproval, result.approval.id)
        collection = await session.scalar(
            select(GameCollection).where(GameCollection.character_id == result.character.id)
        )

    assert approval is not None and approval.status == "pending"
    assert collection is None


@pytest.mark.asyncio
async def test_gacha_roll_is_idempotent_for_same_reference(database):
    async with database.session() as session:
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS))

    service = GachaService(FixedEngine(Rarity.D))

    async with database.session() as session:
        first = await service.roll(session, user_id=7, chat_id=-100, seed="same")
        await session.commit()

    async with database.session() as session:
        second = await service.roll(session, user_id=7, chat_id=-100, seed="same")
        await session.commit()

    assert first is not None and second is not None
    assert first.character.id == second.character.id
    assert first.granted is True and second.granted is True

    async with database.session() as session:
        rolls = list(await session.scalars(select(GameGachaRoll).where(GameGachaRoll.roll_id == "same")))
        collection = await session.scalar(
            select(GameCollection).where(GameCollection.character_id == "anya")
        )
        transactions = list(
            await session.scalars(
                select(PointTransaction).where(
                    PointTransaction.reference_type == "gacha",
                    PointTransaction.reference_id == "same",
                )
            )
        )

    assert len(rolls) == 1
    assert collection is not None and collection.copies == 1
    assert len(transactions) == 1


@pytest.mark.asyncio
async def test_gacha_requires_enough_points(database):
    async with database.session() as session:
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS - 1))
    service = GachaService(FixedEngine(Rarity.D))

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="poor")

    assert result is None


@pytest.mark.asyncio
async def test_gacha_approval_can_be_refunded_once(database):
    async with database.session() as session:
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS))

    service = GachaService(FixedEngine(Rarity.B))

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="refund")
        await session.commit()
        approval_id = result.approval.id

    async with database.session() as session:
        approval = await session.get(RareDropApproval, approval_id)
        assert approval is not None
        from app.game.rare_approval import decide
        await decide(session, approval_id, False, commit=False)
        approval = await session.get(RareDropApproval, approval_id)
        assert approval is not None
        await service.finalize_approval(session, approval)
        await session.commit()

    async with database.session() as session:
        profile = await session.scalar(
            select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
        )
        refunds = list(
            await session.scalars(
                select(PointTransaction).where(
                    PointTransaction.reference_type == "gacha_refund",
                    PointTransaction.reference_id == str(approval_id),
                )
            )
        )

    assert profile is not None and profile.points == GACHA_COST_POINTS
    assert len(refunds) == 1


@pytest.mark.asyncio
async def test_gacha_approval_grants_rare_character_once(database):
    from app.game.rare_approval import decide

    async with database.session() as session:
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS))

    service = GachaService(FixedEngine(Rarity.B))

    async with database.session() as session:
        result = await service.roll(session, user_id=7, chat_id=-100, seed="approve")
        await session.commit()
        approval_id = result.approval.id

    async with database.session() as session:
        request = await decide(session, approval_id, True, commit=False)
        assert request is not None
        granted, balance = await service.finalize_approval(session, request)
        await session.commit()

    assert granted is True
    assert balance == 0

    async with database.session() as session:
        collection = await session.scalar(
            select(GameCollection).where(
                GameCollection.character_id == result.character.id,
            )
        )
        roll = await session.scalar(
            select(GameGachaRoll).where(GameGachaRoll.roll_id == "approve")
        )

    assert collection is not None
    assert collection.copies == 1
    assert roll is not None and roll.granted is True

    async with database.session() as session:
        request = await session.get(RareDropApproval, approval_id)
        assert request is not None
        second_granted, _ = await service.finalize_approval(session, request)
        await session.commit()

    assert second_granted is True


@pytest.mark.asyncio
async def test_gacha_reward_claim_is_single_use(database):
    service = GachaService(FixedEngine(Rarity.B))

    async with database.session() as session:
        roll = GameGachaRoll(
            roll_id="claim-once",
            user_id=7,
            chat_id=-100,
            rolled_rarity=Rarity.B.value,
            character_id="taiga",
            granted=False,
        )
        session.add(roll)
        await session.flush()
        roll_id = roll.id

        first = await service._claim_reward(session, roll_id)
        await session.commit()

    async with database.session() as session:
        second = await service._claim_reward(session, roll_id)
        await session.commit()

    assert first is True
    assert second is False



@pytest.mark.asyncio
async def test_gacha_reference_cannot_be_replayed_for_another_player_or_community(database):
    async with database.session() as session:
        session.add_all([
            User(id=8, first_name="Other"),
            Chat(id=-200, type="supergroup", title="Other Community"),
        ])
        await session.flush()
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS))
        session.add(GameProfile(user_id=8, chat_id=-200, points=GACHA_COST_POINTS))

    service = GachaService(FixedEngine(Rarity.D))

    async with database.session() as session:
        first = await service.roll(
            session,
            user_id=7,
            chat_id=-100,
            seed="owned-by-7",
        )
        await session.commit()

    assert first is not None

    async with database.session() as session:
        with pytest.raises(ValueError, match="another player or community"):
            await service.roll(
                session,
                user_id=8,
                chat_id=-200,
                seed="owned-by-7",
            )


@pytest.mark.asyncio
async def test_concurrent_same_gacha_reference_charges_and_grants_once(tmp_path):
    database_a = Database(f"sqlite+aiosqlite:///{tmp_path / 'gacha-race.db'}")
    database_b = Database(f"sqlite+aiosqlite:///{tmp_path / 'gacha-race.db'}")
    await database_a.create_schema()

    async with database_a.session() as session:
        session.add(User(id=11, first_name="Race"))
        session.add(Chat(id=-101, type="supergroup", title="Race Community"))
        await session.flush()
        session.add(GameProfile(user_id=11, chat_id=-101, points=GACHA_COST_POINTS))

    service = GachaService(FixedEngine(Rarity.D))

    async def roll(database):
        async with database.session(write=True) as session:
            return await service.roll(
                session,
                user_id=11,
                chat_id=-101,
                seed="race-reference",
            )

    first, second = await asyncio.gather(
        roll(database_a),
        roll(database_b),
    )

    assert first is not None
    assert second is not None
    assert first.character.id == second.character.id
    assert first.granted is True
    assert second.granted is True

    async with database_a.session() as session:
        rolls = list(
            await session.scalars(
                select(GameGachaRoll).where(GameGachaRoll.roll_id == "race-reference")
            )
        )
        transactions = list(
            await session.scalars(
                select(PointTransaction).where(
                    PointTransaction.reference_type == "gacha",
                    PointTransaction.reference_id == "race-reference",
                )
            )
        )
        collection = await session.scalar(
            select(GameCollection).where(GameCollection.character_id == "anya")
        )
        profile = await session.scalar(
            select(GameProfile).where(GameProfile.user_id == 11, GameProfile.chat_id == -101)
        )

    assert len(rolls) == 1
    assert len(transactions) == 1
    assert collection is not None
    assert collection.copies == 1
    assert profile is not None
    assert profile.points == 0

    await database_a.close()
    await database_b.close()
