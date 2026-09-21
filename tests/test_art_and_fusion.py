import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import Chat, GameCollection, GameProfile, User
from app.game.art_progression import art_prompt_spec, art_stage_for_level
from app.game.fusion import fuse_collection


@pytest.mark.parametrize(
    ("level", "style"),
    [
        (1, "chibi"),
        (5, "chibi"),
        (6, "anime"),
        (15, "anime"),
        (16, "anime premium"),
        (25, "anime premium"),
    ],
)
def test_art_stage_matches_level_band(level, style):
    assert art_stage_for_level(level).style == style


def test_art_prompt_is_deterministic_and_character_focused():
    first = art_prompt_spec(
        character_name="Anya Forger",
        anime="SPY x FAMILY",
        level=20,
        card_tier=__import__("app.game.models", fromlist=["CardTier"]).CardTier.UR,
    )
    second = art_prompt_spec(
        character_name="Anya Forger",
        anime="SPY x FAMILY",
        level=20,
        card_tier=__import__("app.game.models", fromlist=["CardTier"]).CardTier.UR,
    )
    assert first == second
    assert "Anya Forger" in first
    assert "SPY x FAMILY" in first
    assert "versión ultra" in first


@pytest.mark.asyncio
async def test_fusion_requires_level_25(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'fusion.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add(User(id=7, first_name="Test"))
        session.add(Chat(id=-100, type="supergroup", title="Test"))
        await session.flush()
        profile = GameProfile(user_id=7, chat_id=-100)
        session.add(profile)
        await session.flush()
        session.add(
            GameCollection(
                profile_id=profile.id,
                character_id="anya",
                rarity="D",
                level=24,
                experience=0,
                copies=10,
            )
        )

    async with database.session(write=True) as session:
        profile = await session.scalar(select(GameProfile).where(GameProfile.user_id == 7))
        assert profile is not None
        with pytest.raises(ValueError, match="nivel 25"):
            await fuse_collection(session, profile_id=profile.id, character_id="anya")

    await database.close()


@pytest.mark.asyncio
async def test_fusion_at_level_25_consumes_same_character_copies(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'fusion-ok.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add(User(id=8, first_name="Test"))
        session.add(Chat(id=-101, type="supergroup", title="Test"))
        await session.flush()
        profile = GameProfile(user_id=8, chat_id=-101)
        session.add(profile)
        await session.flush()
        session.add(
            GameCollection(
                profile_id=profile.id,
                character_id="anya",
                rarity="D",
                level=25,
                experience=0,
                copies=10,
            )
        )

    async with database.session(write=True) as session:
        profile = await session.scalar(select(GameProfile).where(GameProfile.user_id == 8))
        assert profile is not None
        result = await fuse_collection(
            session,
            profile_id=profile.id,
            character_id="anya",
        )

    assert result.from_rarity == "D"
    assert result.to_rarity == "C"
    assert result.consumed == 10

    async with database.session() as session:
        row = await session.scalar(
            select(GameCollection).where(
                GameCollection.profile_id == profile.id,
                GameCollection.character_id == "anya",
            )
        )

    assert row is not None
    assert row.rarity == "C"
    assert row.level == 1
    assert row.copies == 1

    await database.close()


def test_every_playable_avatar_has_explicit_art_direction() -> None:
    from app.game.art_directions import ART_DIRECTIONS, direction_for
    from app.game.catalog import CHARACTERS

    assert set(CHARACTERS).issubset(ART_DIRECTIONS)
    for character_id in CHARACTERS:
        direction = direction_for(character_id)
        assert direction.palette
        assert direction.expression
        assert direction.pose
        assert direction.environment
        assert direction.motif
