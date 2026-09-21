import asyncio

import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import (
    GameItemInventory,
    GameProfile,
    User,
    Chat,
    WaifuGiftClaim,
)
from app.game.models import Rarity
from app.game.waifu_gifts import (
    MAX_GIFT_RECIPIENTS,
    WaifuGiftService,
)


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'gifts.db'}")
    await database.create_schema()
    async with database.session() as session:
        session.add_all(
            [
                User(id=1, first_name="A"),
                User(id=2, first_name="B"),
                User(id=3, first_name="C"),
                User(id=4, first_name="D"),
                Chat(id=-100, type="supergroup", title="Café"),
            ]
        )
        await session.flush()
        for user_id in (1, 2, 3, 4):
            session.add(GameProfile(user_id=user_id, chat_id=-100))
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_one_gift_drop_has_at_most_three_recipients_and_one_claim_per_user(database):
    service = WaifuGiftService()

    async with database.session(write=True) as session:
        drop = await service.create_drop(
            session,
            chat_id=-100,
            day_key="2026-09-21",
            slot=0,
        )
        profiles = list(
            await session.scalars(
                select(GameProfile).where(GameProfile.chat_id == -100).order_by(GameProfile.user_id)
            )
        )
        results = []
        for profile in profiles[:4]:
            results.append(
                await service.claim(
                    session,
                    drop_id=drop.id,
                    user_id=profile.user_id,
                    chat_id=-100,
                    profile_id=profile.id,
                )
            )

        duplicate = await service.claim(
            session,
            drop_id=drop.id,
            user_id=profiles[1].user_id,
            chat_id=-100,
            profile_id=profiles[1].id,
        )

    assert sum(result is not None for result in results) == MAX_GIFT_RECIPIENTS
    assert results[-1] is None
    assert duplicate is None

    async with database.session() as session:
        claims = list(await session.scalars(select(WaifuGiftClaim)))
        inventory = list(await session.scalars(select(GameItemInventory)))

    assert len(claims) == 3
    assert len(inventory) == 3
    assert all(item.quantity == 1 for item in inventory)


@pytest.mark.asyncio
async def test_absorb_consumes_one_item_and_adds_exp_to_selected_waifu(database):
    service = WaifuGiftService()

    async with database.session(write=True) as session:
        profile = await session.scalar(select(GameProfile).where(GameProfile.user_id == 1))
        assert profile is not None
        from app.db.models import GameCollection

        session.add(
            GameCollection(
                profile_id=profile.id,
                character_id="anya",
                rarity=Rarity.D.value,
                level=1,
                experience=0,
                copies=1,
            )
        )
        session.add(
            GameItemInventory(
                profile_id=profile.id,
                item_key="dessert",
                quantity=2,
            )
        )

    async with database.session(write=True) as session:
        profile = await session.scalar(select(GameProfile).where(GameProfile.user_id == 1))
        assert profile is not None
        new_level = await service.absorb(
            session,
            profile_id=profile.id,
            character_id="anya",
            item_key="dessert",
        )

    assert new_level == 1

    async with database.session() as session:
        item = await session.scalar(select(GameItemInventory).where(GameItemInventory.profile_id == profile.id))
        collection = await session.scalar(
            select(GameCollection).where(
                GameCollection.profile_id == profile.id,
                GameCollection.character_id == "anya",
            )
        )

    assert item is not None and item.quantity == 1
    assert collection is not None and collection.experience == 40


@pytest.mark.asyncio
async def test_concurrent_gift_claims_allow_only_three_winners(tmp_path):
    database_a = Database(f"sqlite+aiosqlite:///{tmp_path / 'gift-race.db'}")
    database_b = Database(f"sqlite+aiosqlite:///{tmp_path / 'gift-race.db'}")
    await database_a.create_schema()

    async with database_a.session() as session:
        session.add_all(
            [
                User(id=10, first_name="A"),
                User(id=11, first_name="B"),
                User(id=12, first_name="C"),
                User(id=13, first_name="D"),
                Chat(id=-101, type="supergroup", title="Race"),
            ]
        )
        await session.flush()
        for user_id in (10, 11, 12, 13):
            session.add(GameProfile(user_id=user_id, chat_id=-101))
        drop = await WaifuGiftService().create_drop(
            session,
            chat_id=-101,
            day_key="2026-09-21",
            slot=0,
        )
        drop_id = drop.id

    service = WaifuGiftService()

    async def claim(database, user_id):
        async with database.session(write=True) as session:
            profile = await session.scalar(
                select(GameProfile).where(
                    GameProfile.user_id == user_id,
                    GameProfile.chat_id == -101,
                )
            )
            assert profile is not None
            return await service.claim(
                session,
                drop_id=drop_id,
                user_id=user_id,
                chat_id=-101,
                profile_id=profile.id,
            )

    results = await asyncio.gather(
        claim(database_a, 10),
        claim(database_b, 11),
        claim(database_a, 12),
        claim(database_b, 13),
    )

    assert sum(result is not None for result in results) == 3

    async with database_a.session() as session:
        claims = list(await session.scalars(select(WaifuGiftClaim).where(WaifuGiftClaim.drop_id == drop_id)))

    assert len(claims) == 3
    await database_a.close()
    await database_b.close()
