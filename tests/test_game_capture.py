from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.characters.models import CharacterIntent
from app.db.database import Database
from app.db.models import Chat, GameAttempt, GameCollection, GameEncounter, GameProfile, PointTransaction, User
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
    edit_markups = []
    answers = []

    async def edit_text(text, **kwargs):
        edits.append(text)
        edit_markups.append(kwargs.get("reply_markup"))

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

    assert encounter.status == "active"
    assert profile.points == 30
    assert collection.character_id == "anya"
    assert collection.copies == 1
    assert collection.experience == 25
    assert transaction.reference_id == "encounter-1:7"
    assert edits
    assert edit_markups[-1] is not None
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
async def test_encounter_supports_three_distinct_captures_and_one_attempt_each(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'capture-three.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add_all([
            User(id=11, first_name="A"),
            User(id=12, first_name="B"),
            User(id=13, first_name="C"),
            User(id=14, first_name="D"),
            Chat(id=-100, type="supergroup", title="Café Otaku"),
        ])
        session.add(
            GameEncounter(
                id="encounter-three",
                chat_id=-100,
                character_id="anya",
                rarity="D",
                answer="Anya Forger",
                expires_at=utc_now() + timedelta(minutes=5),
                status="active",
            )
        )

    async def run_callback(user_id: int, callback_id: str) -> list[str]:
        answers: list[str] = []
        edits: list[str] = []

        async def answer(text, **kwargs):
            answers.append(text)

        async def edit_text(text, **kwargs):
            edits.append(text)

        callback = SimpleNamespace(
            id=callback_id,
            data="game:encounter:encounter-three:answer:0",
            from_user=SimpleNamespace(id=user_id, first_name=f"User{user_id}"),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=-100, type="supergroup"),
                edit_text=edit_text,
            ),
            answer=answer,
        )
        await GameModule(database).encounter_answer(callback)
        return answers + edits

    first = await run_callback(11, "three-1")
    second = await run_callback(12, "three-2")
    third = await run_callback(13, "three-3")

    async def fourth_answer(text, **kwargs):
        fourth_answers.append(text)

    fourth_answers: list[str] = []
    callback = SimpleNamespace(
        id="three-4",
        data="game:encounter:encounter-three:answer:0",
        from_user=SimpleNamespace(id=14, first_name="User14"),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            edit_text=AsyncMock(),
        ),
        answer=fourth_answer,
    )
    await GameModule(database).encounter_answer(callback)

    async with database.session() as session:
        encounter = await session.get(GameEncounter, "encounter-three")
        attempts = list(await session.scalars(
            select(GameAttempt).where(GameAttempt.encounter_id == "encounter-three")
        ))
        collections = list(await session.scalars(select(GameCollection)))
        transactions = list(await session.scalars(select(PointTransaction)))

    assert "¡CAPTURADA! 🎉" in first[0]
    assert "¡CAPTURADA! 🎉" in second[0]
    assert "¡CAPTURADA! 🎉" in third[0]
    assert fourth_answers == ["Este encuentro ya tiene sus 3 oportunidades ocupadas."]
    assert encounter is not None and encounter.status == "closed"
    assert len(attempts) == 3
    assert all(attempt.correct for attempt in attempts)
    assert len(collections) == 3
    assert len(transactions) == 3
    await database.close()
