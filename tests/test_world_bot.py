from app.bots.world import WORLD_BOT_PRESENTER, build_world_bot
from app.core.config import Settings
from app.world.models import PresenterKind, WorldPresenterRef


def test_worldbot_uses_a_neutral_world_presenter_reference() -> None:
    assert WORLD_BOT_PRESENTER == WorldPresenterRef("world", PresenterKind.WORLD_BOT)


def test_worldbot_never_becomes_an_existing_character_presenter() -> None:
    assert WORLD_BOT_PRESENTER.kind is PresenterKind.WORLD_BOT
    assert WORLD_BOT_PRESENTER.key == "world"


async def test_worldbot_builder_uses_only_world_presentation_components() -> None:
    settings = Settings(
        bot_token_world="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bot, database, catalog, presenter = build_world_bot(settings)
    try:
        assert presenter.presenter_ref == WORLD_BOT_PRESENTER
        assert presenter.presenter_key == "world_bot:world"
        assert catalog.name == "world-catalog"
    finally:
        await database.close()
        await bot.session.close()
