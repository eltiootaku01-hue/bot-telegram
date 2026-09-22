import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.models import CardDefinition, CardRollClaim, Chat, GameCardCollection, GameProfile, User
from app.game.card_definitions import CardDefinitionService


class FixedRng:
    def choice(self, values):
        return values[0]


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_create_definition_matches_requested_json_contract(database):
    service = CardDefinitionService(Settings(), rng=FixedRng())

    async with database.session(write=True) as session:
        card = await service.create_definition(
            session,
            character_name="Asuna (Verano)",
            character_id="asuna",
            anime_origin="Sword Art Online",
            rarity="SSR",
            source_provider="IA (PixAI/Midjourney)",
            collection_points=150,
            image_filename="asuna_summer_ssr.jpg",
        )

    assert card.character_id == "asuna"
    assert card.character_name == "Asuna (Verano)"
    assert card.anime_origin == "Sword Art Online"
    assert card.rarity == "SSR"
    assert card.image_url == "assets/cards/asuna_summer_ssr.jpg"
    assert card.source_provider == "IA (PixAI/Midjourney)"
    assert card.collection_points == 150
    assert card.active is True
    assert card.id.startswith("asuna-asuna-verano-ssr-") or card.id.startswith("asuna-ssr-")


@pytest.mark.asyncio
async def test_new_active_definition_enters_roll_pool_immediately(database):
    service = CardDefinitionService(Settings(), rng=FixedRng())

    async with database.session(write=True) as session:
        session.add_all(
            [
                User(id=7, first_name="Player"),
                Chat(id=-100, type="supergroup", title="Community"),
                CardDefinition(
                id="rem-sleeping-sr-01",
                character_id="rem",
                character_name="Rem (Dormida)",
                anime_origin="Re:Zero",
                rarity="SR",
                image_url="assets/cards/rem_sleeping_sr.jpg",
                source_provider="IA (PixAI/Midjourney)",
                collection_points=150,
                    active=True,
                ),
            ]
        )

    async with database.session(write=True) as session:
        result = await service.roll(
            session,
            user_id=7,
            chat_id=-100,
            source_message_id=123,
        )

    assert result is not None
    assert result.definition.id == "rem-sleeping-sr-01"
    assert result.copies == 1
    assert result.already_claimed is False

    async with database.session() as session:
        collection = await session.scalar(select(GameCardCollection))
        claim = await session.scalar(select(CardRollClaim))
        profile = await session.scalar(select(GameProfile))

    assert collection is not None
    assert collection.card_id == "definition:rem-sleeping-sr-01"
    assert collection.card_tier == "SR"
    assert collection.copies == 1
    assert claim is not None
    assert profile is not None


@pytest.mark.asyncio
async def test_replayed_roll_message_is_idempotent(database):
    service = CardDefinitionService(Settings(), rng=FixedRng())

    async with database.session(write=True) as session:
        session.add_all(
            [
                User(id=7, first_name="Player"),
                Chat(id=-100, type="supergroup", title="Community"),
                CardDefinition(
                    id="asuna-summer-ssr-02",
                    character_id="asuna",
                    character_name="Asuna (Verano)",
                    anime_origin="Sword Art Online",
                    rarity="SSR",
                    image_url="assets/cards/asuna_summer_ssr.jpg",
                    source_provider="IA (PixAI/Midjourney)",
                    collection_points=150,
                    active=True,
                ),
            ]
        )

    async with database.session(write=True) as session:
        first = await service.roll(session, user_id=7, chat_id=-100, source_message_id=456)

    async with database.session(write=True) as session:
        second = await service.roll(session, user_id=7, chat_id=-100, source_message_id=456)

    assert first is not None
    assert second is not None
    assert first.definition.id == second.definition.id
    assert first.copies == 1
    assert second.copies == 1
    assert second.already_claimed is True

    async with database.session() as session:
        claims = list(await session.scalars(select(CardRollClaim)))
        collections = list(await session.scalars(select(GameCardCollection)))

    assert len(claims) == 1
    assert len(collections) == 1
    assert collections[0].copies == 1


@pytest.mark.asyncio
async def test_inactive_definition_is_not_rolled(database):
    service = CardDefinitionService(Settings(), rng=FixedRng())

    async with database.session(write=True) as session:
        session.add(
            CardDefinition(
                id="disabled-card",
                character_id="x",
                character_name="Disabled",
                anime_origin="Test",
                rarity="C",
                image_url="assets/cards/disabled.jpg",
                source_provider="test",
                collection_points=0,
                active=False,
            )
        )

    async with database.session(write=True) as session:
        result = await service.roll(
            session,
            user_id=8,
            chat_id=-101,
            source_message_id=1,
        )

    assert result is None


def test_image_validation_rejects_wrong_magic_bytes():
    from app.game.card_definitions import validate_image_bytes

    with pytest.raises(ValueError, match="coincide"):
        validate_image_bytes(b"not-an-image", "image/jpeg")



@pytest.mark.asyncio
async def test_create_definition_rejects_path_traversal_filename(database):
    service = CardDefinitionService(Settings())

    async with database.session(write=True) as session:
        with pytest.raises(ValueError, match="asset"):
            await service.create_definition(
                session,
                character_name="Unsafe",
                character_id="unsafe",
                anime_origin="Test",
                rarity="C",
                source_provider="test",
                collection_points=0,
                image_filename="../unsafe.jpg",
            )
