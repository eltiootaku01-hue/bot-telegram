from app.db.database import Database
from app.db.models import Chat, GameCardCollection, GameProfile, User
from app.game.card_service import CardCollectionService
from app.game.cards import card_for_character
from app.game.catalog import get_character
from sqlalchemy import select
import pytest


@pytest.mark.asyncio
async def test_card_service_grants_and_fuses_atomically(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cards.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add(User(id=1, first_name="Card"))
        session.add(Chat(id=-100, type="supergroup", title="Cards"))
        await session.flush()
        profile = GameProfile(user_id=1, chat_id=-100)
        session.add(profile)
        await session.flush()

        first = card_for_character(
            get_character("yor-forger"),
            seed="first-card",
        )
        second = card_for_character(
            get_character("nico-robin"),
            seed="second-card",
        )

        service = CardCollectionService()
        first_grant = await service.grant(session, profile_id=profile.id, card=first)
        second_grant = await service.grant(session, profile_id=profile.id, card=second)

        assert first_grant.copies == 1
        assert second_grant.copies == 1

    async with database.session(write=True) as session:
        profile = await session.scalar(
            select(GameProfile).where(
                GameProfile.user_id == 1,
                GameProfile.chat_id == -100,
            )
        )
        assert profile is not None
        service = CardCollectionService()
        result = await service.fuse(
            session,
            profile_id=profile.id,
            first_collection_id=1,
            second_collection_id=2,
            seed="ur-fusion",
        )

        assert result.card.is_fusion is True
        assert result.card.tier.value == "UR"

    async with database.session() as session:
        rows = list(
            await session.scalars(
                select(GameCardCollection)
                .where(GameCardCollection.profile_id == profile.id)
                .order_by(GameCardCollection.id.asc())
            )
        )

    assert len(rows) == 3
    assert rows[0].copies == 0
    assert rows[1].copies == 0
    assert rows[2].card_tier == "UR"
    assert rows[2].copies == 1

    await database.close()
