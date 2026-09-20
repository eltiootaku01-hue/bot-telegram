from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.characters.models import CharacterIntent
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
    assert any("<b>Sunna:</b>" in text for text in edits)
    assert any(text in edits[-1] for text in ("Bien. Lo hiciste.", "Ganaste.", "Fue buena jugada.", "Me alegra."))
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


@pytest.mark.asyncio
async def test_gacha_open_callback_renders_gacha_panel() -> None:
    module = GameModule(None)
    edits = []
    answers = []

    async def edit_text(text, **kwargs):
        edits.append((text, kwargs))

    async def answer(text="", **kwargs):
        answers.append(text)

    callback = SimpleNamespace(
        id="cb-gacha",
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=7, type="private"),
            edit_text=edit_text,
        ),
        answer=answer,
    )

    await module.gacha_open(callback)

    assert edits
    assert edits[0][0] == "🎰 <b>Gacha de personajes</b>"
    assert answers == [""]


def test_game_reaction_is_authored_and_deterministic() -> None:
    module = GameModule(None)
    first = module._game_reaction(CharacterIntent.GAME_SUCCESS, 7)
    second = module._game_reaction(CharacterIntent.GAME_SUCCESS, 7)

    assert first
    assert first == second
    assert first in {"Bien. Lo hiciste.", "Ganaste.", "Fue buena jugada.", "Me alegra."}


@pytest.mark.asyncio
async def test_mystery_success_includes_authored_sunna_reaction(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'mystery-reaction.db'}")
    await database.create_schema()
    module = GameModule(database)

    async with database.session(write=True) as session:
        session.add_all(
            [
                User(id=9, first_name="Jugador"),
                Chat(id=-100, type="supergroup", title="Café Otaku"),
            ]
        )
        await session.flush()
        started = await module.mystery_service.start_round(
            session, chat_id=-100, day_key="2026-09-30"
        )

    edited = []
    answered = []

    async def edit_text(text, **kwargs):
        edited.append(text)

    async def answer(text, **kwargs):
        answered.append(text)

    callback = SimpleNamespace(
        data=f"game:mystery:{started.round.id}:{started.case.answer_index}",
        from_user=SimpleNamespace(id=9, first_name="Jugador"),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            edit_text=edit_text,
        ),
        answer=answer,
    )

    await module.mystery_answer(callback)

    assert edited
    assert any("<b>Sunna:</b>" in text for text in edited)
    assert any(value in edited[-1] for value in ("Bien. Lo hiciste.", "Ganaste.", "Fue buena jugada.", "Me alegra."))
    assert answered == ["¡Correcto! Ganaste el misterio. 🎉"]
    await database.close()
