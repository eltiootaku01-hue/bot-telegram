from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.models import GameEncounter
from app.game.catalog import wild_characters
from app.game.encounters import encounter_options, new_encounter
from app.modules.world.presenter import WorldPresentationModule
from app.world.models import PresenterKind, WorldPresenterRef
from app.world.service import WorldEventService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'world-presenter.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_presenter_module_owns_only_its_identity_world_claims(database):
    module = WorldPresentationModule(
        database,
        BotIdentity.SUNNA,
        settings=Settings(authorized_chat_ids="-100"),
    )

    bot = AsyncMock()
    bot.send_message.return_value = SimpleNamespace(message_id=123)

    await module.on_startup(bot)

    assert module.runtime is not None
    assert module.runtime.presenter_key == "existing_bot:sunna"

    await module.on_shutdown()


@pytest.mark.asyncio
async def test_sunna_presenter_publishes_waifu_keyboard_and_records_message(database):
    character = wild_characters()[0]
    encounter = new_encounter(character)
    options = encounter_options(encounter)

    async with database.session() as session:
        record = GameEncounter(
            id=encounter.id,
            chat_id=-100,
            character_id=character.id,
            rarity=character.rarity.value,
            question=encounter.question,
            answer=encounter.answer,
            expires_at=encounter.expires_at,
        )
        session.add(record)
        await session.flush()
        await WorldEventService().schedule_waifu_arrival(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            encounter_id=encounter.id,
            character_id=character.id,
            character_name=character.name,
            text="¡Apareció!",
            options=tuple(options),
            dedupe_key=f"presenter-arrival:{encounter.id}",
        )
        await session.commit()

    async with database.session(write=True) as session:
        envelope = await WorldEventService().claim_due(session)

    module = WorldPresentationModule(
        database,
        BotIdentity.SUNNA,
        settings=Settings(authorized_chat_ids="-100"),
    )
    bot = AsyncMock()
    bot.send_message.return_value = SimpleNamespace(message_id=987)
    await module.on_startup(bot)

    assert module.runtime is not None
    result = await module.runtime.presenter.present(envelope)

    assert result.message_id == 987
    bot.send_message.assert_awaited_once()
    args = bot.send_message.await_args.args
    kwargs = bot.send_message.await_args.kwargs
    assert args[0] == -100
    assert args[1].startswith("🚨 ¡Apareció ")
    assert args[1].endswith("\n\n¡Apareció!")
    markup = kwargs["reply_markup"]
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert callbacks
    assert callbacks[0].startswith(f"game:encounter:{encounter.id}:answer:")

    async with database.session() as session:
        saved = await session.get(GameEncounter, encounter.id)

    assert saved is not None
    assert saved.message_id == 987

    await module.on_shutdown()
