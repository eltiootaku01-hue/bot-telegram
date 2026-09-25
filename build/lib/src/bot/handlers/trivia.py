from __future__ import annotations

import os
import random
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message
from PIL import Image, ImageFilter, ImageOps
from sqlalchemy import text

from app.db.database import Database
from app.multibot.vault_client import VaultClient

DEFAULT_POINTS = 10
DEFAULT_TIMEOUT_SECONDS = 90


class TriviaStates(StatesGroup):
    waiting_answer = State()


@dataclass(frozen=True)
class ActiveTrivia:
    round_id: str
    chat_id: int
    thread_id: int
    card_id: str
    answer: str
    points: int
    status: str


class TriviaRepository:
    """SQLite authority for active forum-thread trivia and exactly one winner."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def init(self) -> None:
        async with self.database.session(write=True) as session:
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS native_trivia_rounds (
                        round_id TEXT PRIMARY KEY,
                        chat_id INTEGER NOT NULL,
                        thread_id INTEGER NOT NULL,
                        card_id TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        points INTEGER NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        winner_user_id INTEGER,
                        winner_message_id INTEGER,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        expires_at TEXT NOT NULL
                    )
                    """
                )
            )
            await session.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_native_trivia_active_thread "
                    "ON native_trivia_rounds(chat_id, thread_id) "
                    "WHERE status='ACTIVE'"
                )
            )

    async def create(
        self,
        *,
        chat_id: int,
        thread_id: int,
        card_id: str,
        answer: str,
        points: int,
        expires_at: str,
    ) -> str | None:
        round_id = uuid.uuid4().hex
        normalized = " ".join(answer.casefold().strip().split())
        async with self.database.session(write=True) as session:
            result = await session.execute(
                text(
                    """
                    INSERT INTO native_trivia_rounds
                    (round_id, chat_id, thread_id, card_id, answer, points, status, expires_at)
                    VALUES
                    (:round_id, :chat_id, :thread_id, :card_id, :answer,
                     :points, 'ACTIVE', :expires_at)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "round_id": round_id,
                    "chat_id": chat_id,
                    "thread_id": thread_id,
                    "card_id": card_id,
                    "answer": normalized,
                    "points": points,
                    "expires_at": expires_at,
                },
            )
            return round_id if result.rowcount == 1 else None

    async def claim_first_correct(
        self,
        *,
        chat_id: int,
        thread_id: int,
        user_id: int,
        message_id: int,
        answer: str,
        now_iso: str,
    ) -> ActiveTrivia | None:
        normalized = " ".join(answer.casefold().strip().split())
        async with self.database.session(write=True) as session:
            result = await session.execute(
                text(
                    """
                    UPDATE native_trivia_rounds
                    SET status='WON',
                        winner_user_id=:user_id,
                        winner_message_id=:message_id
                    WHERE chat_id=:chat_id
                      AND thread_id=:thread_id
                      AND status='ACTIVE'
                      AND expires_at > :now
                      AND answer=:answer
                    RETURNING round_id, chat_id, thread_id, card_id, answer, points, status
                    """
                ),
                {
                    "chat_id": chat_id,
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "message_id": message_id,
                    "answer": normalized,
                    "now": now_iso,
                },
            )
            row = result.first()
            return ActiveTrivia(*row) if row else None

    async def reward_points(
        self,
        *,
        chat_id: int,
        user_id: int,
        points: int,
        round_id: str,
    ) -> None:
        async with self.database.session(write=True) as session:
            await session.execute(
                text(
                    """
                    INSERT INTO game_profiles
                    (user_id, chat_id, level, experience, points, coins, gacha_d_streak)
                    VALUES (:user_id, :chat_id, 1, :points, :points, 0, 0)
                    ON CONFLICT(user_id, chat_id) DO UPDATE SET
                        experience=game_profiles.experience + excluded.experience,
                        points=game_profiles.points + excluded.points,
                        updated_at=CURRENT_TIMESTAMP
                    """
                ),
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "points": points,
                },
            )
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS native_trivia_rewards (
                        round_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        chat_id INTEGER NOT NULL,
                        card_id TEXT NOT NULL,
                        points INTEGER NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                ),
            )
            await session.execute(
                text(
                    """
                    INSERT OR IGNORE INTO native_trivia_rewards
                    (round_id, user_id, chat_id, card_id, points)
                    VALUES (:round_id, :user_id, :chat_id, :card_id, :points)
                    """
                ),
                {
                    "round_id": round_id,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "card_id": "",
                    "points": points,
                },
            )


def _obscure(source: Path, mode: str) -> Path:
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        if mode == "pixel":
            small = image.resize((48, 72), Image.Resampling.BILINEAR)
            image = small.resize((512, 768), Image.Resampling.NEAREST)
        else:
            gray = ImageOps.grayscale(image)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            image = ImageOps.autocontrast(edges).convert("RGB")
        output = Path(tempfile.gettempdir()) / (
            f"native_trivia_{uuid.uuid4().hex}.webp"
        )
        image.save(output, "WEBP", quality=82)
        return output


def _answer_matches(candidate: str, expected: str) -> bool:
    return " ".join(candidate.casefold().strip().split()) == (
        " ".join(expected.casefold().strip().split())
    )


async def award_trivia_reward(
    repository: TriviaRepository,
    vault: VaultClient,
    *,
    winner: ActiveTrivia,
    chat_id: int,
    user_id: int,
) -> None:
    await repository.reward_points(
        chat_id=chat_id,
        user_id=user_id,
        points=winner.points,
        round_id=winner.round_id,
    )
    await vault.transfer(
        card_id=winner.card_id,
        from_type="bank",
        from_key="main-bank",
        to_type="user",
        to_key=str(user_id),
        quantity=1,
        actor_user_id=user_id,
        idempotency_key=f"native-trivia:{winner.round_id}",
    )


def build_trivia_router(database: Database, vault: VaultClient) -> Router:
    router = Router(name="sunna-native-trivia")
    repository = TriviaRepository(database)

    @router.message(Command("trivia"))
    async def start_trivia(message: Message, state: FSMContext) -> None:
        if (
            message.from_user is None
            or message.chat.type not in {"group", "supergroup"}
        ):
            await message.answer("La trivia nativa se inicia dentro de un grupo.")
            return
        thread_id = int(message.message_thread_id or 0)
        if thread_id <= 0:
            await message.answer("La trivia nativa requiere un Forum Topic.")
            return

        await repository.init()
        cards = await vault.catalog()
        available = [
            card
            for card in cards
            if card.get("asset_path") and card.get("character_name")
        ]
        if not available:
            await message.answer("CardVault no tiene cartas jugables.")
            return

        card = random.choice(available)
        source = Path(str(card["asset_path"]))
        if not source.is_file():
            await message.answer("La carta seleccionada no tiene un asset local disponible.")
            return

        points = max(
            int(card.get("collection_points") or DEFAULT_POINTS),
            DEFAULT_POINTS,
        )
        expires = datetime.now(timezone.utc) + timedelta(
            seconds=DEFAULT_TIMEOUT_SECONDS
        )
        round_id = await repository.create(
            chat_id=message.chat.id,
            thread_id=thread_id,
            card_id=str(card["id"]),
            answer=str(card["character_name"]),
            points=points,
            expires_at=expires.isoformat(),
        )
        if round_id is None:
            await message.answer("Ya hay una trivia activa en este thread.")
            return

        mode = os.getenv("TRIVIA_IMAGE_MODE", "silhouette").strip().casefold()
        if mode not in {"silhouette", "pixel"}:
            mode = "silhouette"
        obscured = _obscure(source, mode)
        try:
            await message.answer_photo(
                FSInputFile(obscured),
                caption=(
                    "🎴 <b>Trivia de Sunna</b>\n\n"
                    "¿Quién es?\n"
                    f"🏆 +{points} puntos\n"
                    f"⏱️ {DEFAULT_TIMEOUT_SECONDS}s"
                ),
            )
        finally:
            obscured.unlink(missing_ok=True)

        await state.set_state(TriviaStates.waiting_answer)
        await state.update_data(thread_id=thread_id, round_id=round_id)

    @router.message(TriviaStates.waiting_answer)
    async def answer_in_fsm(message: Message, state: FSMContext) -> None:
        if (
            message.from_user is None
            or message.text is None
            or message.chat.type not in {"group", "supergroup"}
        ):
            return
        thread_id = int(message.message_thread_id or 0)
        data = await state.get_data()
        if int(data.get("thread_id", -1)) != thread_id:
            return
        await resolve_answer(message, state)

    @router.message(F.message_thread_id)
    async def answer_active_thread(message: Message, state: FSMContext) -> None:
        if (
            message.from_user is None
            or message.text is None
            or message.chat.type not in {"group", "supergroup"}
            or message.text.startswith("/")
        ):
            return
        thread_id = int(message.message_thread_id or 0)
        if thread_id <= 0:
            return
        await resolve_answer(message, state)

    async def resolve_answer(message: Message, state: FSMContext) -> None:
        await repository.init()
        if message.text is None or message.from_user is None:
            return
        from datetime import datetime, timezone

        winner = await repository.claim_first_correct(
            chat_id=message.chat.id,
            thread_id=int(message.message_thread_id or 0),
            user_id=message.from_user.id,
            message_id=message.message_id,
            answer=message.text,
            now_iso=datetime.now(timezone.utc).isoformat(),
        )
        if winner is None:
            return

        try:
            await award_trivia_reward(
                repository,
                vault,
                winner=winner,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
            )
            card_text = f" y obtuvo la carta <code>{winner.card_id}</code>"
        except Exception:
            card_text = (
                " y los puntos fueron guardados; la carta quedó pendiente "
                "porque CardVault no pudo transferirla"
            )

        await message.answer(
            f"🎉 <b>{message.from_user.first_name}</b> acertó primero."
            f" +{winner.points} puntos{card_text}."
        )
        await state.clear()
