from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.db.database import Database
from app.db.models import Chat, GameCollection, GameEncounter, GameProfile, PointTransaction, User
from app.modules.game.module import GameModule


@pytest.mark.asyncio
async def test_capture_callback_persists_progression(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'capture.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add(User(id=7, first_name="Jugador"))
        session.add(Chat(id=-100, type="supergroup", title="Café Otaku"))
        session.add(GameEncounter(
            id="encounter-1",
            chat_id=-100,
            character_id="anya",
            rarity="D",
            answer="Anya Forger",
            expires_at=utc_now() + timedelta(minutes=5),
            status="active",
        ))

    edits = []
    answers = []

    async def edit_text(text, **kwargs):
        edits.append(text)

    async def answer(text, **kwargs):
        answers.append(text)

    callback = SimpleNamespace(
        data="game:encounter:encounter-1:answer:0",
        from_user=SimpleNamespace(id=7, first_name="Jugador"),
        message=SimpleNamespace(chat=SimpleNamespace(id=-100), edit_text=edit_text),
        answer=answer,
    )

    await GameModule(database).encounter_answer(callback)

    async with database.session() as session:
        encounter = await session.get(GameEncounter, "encounter-1")
        profile = await session.scalar(
            select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
        )
        collection = await session.scalar(select(GameCollection))
        transaction = await session.scalar(select(PointTransaction))

    assert encounter.status == "captured"
    assert profile.points == 10
    assert collection.character_id == "anya"
    assert collection.copies == 1
    assert collection.experience == 25
    assert transaction.reference_id == "encounter-1"
    assert edits
    assert answers == ["¡CAPTURADA! 🎉"]
    await database.close()


@pytest.mark.asyncio
async def test_private_game_callbacks_reject_group_context() -> None:
    module = GameModule(None)
    answers = []

    async def answer(text, **kwargs):
        answers.append(text)

    callback = SimpleNamespace(
        id="cb-1",
        data="game:gacha:roll",
        from_user=SimpleNamespace(id=7, first_name="Jugador"),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
        ),
        answer=answer,
    )

    await module.gacha_roll(callback)
    await module.combat_action(callback)
    await module.game_hub(callback)
    await module.combat_open(callback)

    assert len(answers) == 4
    assert all("privado" in text for text in answers)
