from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.models import CardDefinition, GameCardCollection, GameProfile, User, Chat
from app.modules.game.module import GameModule


@pytest.mark.asyncio
async def test_roll_command_claims_uploaded_card_and_sends_image(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'roll.db'}")
    await database.create_schema()
    asset_dir = Path(tmp_path / "assets")
    asset_dir.mkdir()
    image_path = asset_dir / "rem_sleeping_sr.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0fake")

    async with database.session(write=True) as session:
        session.add_all(
            [
                User(id=7, first_name="Player"),
                Chat(id=-100, type="supergroup", title="Community"),
                CardDefinition(
                    id="rem-sleeping-sr-01",
                    character_id="rem",
                    character_name="<Rem> & Dormida",
                    anime_origin="Re:Zero <test>",
                    rarity="SR",
                    image_url="assets/cards/rem_sleeping_sr.jpg",
                    source_provider="IA (PixAI/Midjourney)",
                    collection_points=150,
                    active=True,
                ),
            ]
        )

    module = GameModule(
        database,
        Settings(card_assets_dir=str(asset_dir)),
    )
    module._observe_action = AsyncMock()

    answers = []

    async def answer_photo(file, caption):
        answers.append((file, caption))

    async def answer(text):
        answers.append((None, text))

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=7, first_name="Player"),
        message_id=321,
        answer_photo=answer_photo,
        answer=answer,
    )

    await module.roll_card(message)

    assert len(answers) == 1
    sent_file, caption = answers[0]
    assert sent_file is not None
    assert "&lt;Rem&gt; &amp; Dormida" in caption
    assert "Re:Zero &lt;test&gt;" in caption
    assert "SR" in caption
    assert "×1" in caption

    async with database.session() as session:
        profile = await session.scalar(select(GameProfile))
        collection = await session.scalar(select(GameCardCollection))

    assert profile is not None
    assert collection is not None
    assert collection.card_id == "definition:rem-sleeping-sr-01"
    assert collection.copies == 1
    module._observe_action.assert_awaited_once_with("card_roll", 7, -100)

    await database.close()


@pytest.mark.asyncio
async def test_cards_view_renders_custom_definition_without_catalog_lookup(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cards-view.db'}")
    await database.create_schema()

    async with database.session(write=True) as session:
        user = User(id=8, first_name="Viewer")
        chat = Chat(id=-100, type="supergroup", title="Community")
        session.add_all([user, chat])
        await session.flush()
        profile = GameProfile(user_id=8, chat_id=-100)
        session.add(profile)
        await session.flush()
        session.add(
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
            )
        )
        session.add(
            GameCardCollection(
                profile_id=profile.id,
                card_id="definition:asuna-summer-ssr-02",
                character_id="asuna",
                card_tier="SSR",
                variant="custom",
                outfit="admin_upload",
                copies=1,
            )
        )

    module = GameModule(database, Settings())
    edit = AsyncMock()
    source = SimpleNamespace(edit_text=edit)

    await module._show_cards(source, user_id=8, chat_id=-100, page=1)

    rendered = edit.await_args.args[0]
    assert "Asuna (Verano)" in rendered
    assert "SSR" in rendered
    assert "Personalizada" in rendered
    await database.close()
