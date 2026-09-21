import pytest

from app.db.database import Database
from app.db.models import Chat, GameProfile, User
from app.game.catalog import get_character
from app.game.progression import apply_capture_progression, stats_for_collection


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_capture_persists_individual_potential_and_reloads_same_stats(database):
    async with database.session() as session:
        session.add(User(id=700, first_name="Player"))
        session.add(Chat(id=-700, type="supergroup", title="Game"))
        await session.flush()
        profile = GameProfile(user_id=700, chat_id=-700)
        session.add(profile)
        await session.flush()

        collection, _ = await apply_capture_progression(
            session,
            profile_id=profile.id,
            character_id="yor-forger",
            rarity="S",
            potential_seed="capture-seed-700",
        )
        stats_before = stats_for_collection(get_character("yor-forger"), collection)
        saved_seed = collection.potential_seed
        collection_id = collection.id

    async with database.session() as session:
        restored = await session.get(type(collection), collection_id)
        assert restored is not None
        assert restored.potential_seed == saved_seed
        stats_after = stats_for_collection(get_character("yor-forger"), restored)

    assert stats_after == stats_before


def test_same_level_different_classes_have_materially_different_stats():
    character = get_character("yor-forger")

    low = stats_for_collection(
        character,
        type(
            "Collection",
            (),
            {
                "level": 20,
                "rarity": "D",
                "potential_seed": "same-potential",
                "evolution_stage": 3,
                "copies": 1,
                "experience": 0,
            },
        )(),
    )
    high = stats_for_collection(
        character,
        type(
            "Collection",
            (),
            {
                "level": 20,
                "rarity": "S",
                "potential_seed": "same-potential",
                "evolution_stage": 3,
                "copies": 1,
                "experience": 0,
            },
        )(),
    )

    assert high.level == low.level == 20
    assert high.rarity.value == "S"
    assert low.rarity.value == "D"
    assert high.max_hp > low.max_hp
    assert high.strength > low.strength
    assert high.defense > low.defense
    assert high.speed > low.speed
