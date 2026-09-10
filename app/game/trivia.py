from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import MemberRepository
from app.db.trivia_models import TriviaAttempt, TriviaRound


@dataclass(frozen=True, slots=True)
class TriviaQuestion:
    question: str
    options: tuple[str, ...]
    answer_index: int
    explanation: str
    points: int


QUESTIONS: tuple[TriviaQuestion, ...] = (
    TriviaQuestion("¿En qué anime aparece Levi Ackerman?", ("Naruto", "Shingeki no Kyojin", "Bleach", "Black Clover"), 1, "Levi es capitán del Cuerpo de Exploración en Shingeki no Kyojin.", 20),
    TriviaQuestion("¿Cómo se llama la hermana menor de Tanjiro Kamado?", ("Nezuko", "Shinobu", "Kanao", "Mitsuri"), 0, "Nezuko es la hermana menor de Tanjiro.", 20),
    TriviaQuestion("¿Qué objeto utiliza Usagi Tsukino para transformarse en Sailor Moon?", ("Un anillo", "Un broche", "Una espada", "Un reloj"), 1, "El broche es uno de los objetos emblemáticos de sus transformaciones.", 15),
    TriviaQuestion("¿Quién es el protagonista de One Punch Man?", ("Genos", "Garou", "Saitama", "King"), 2, "Saitama derrota a sus enemigos de un solo golpe.", 15),
    TriviaQuestion("¿Quién acompaña normalmente a Pikachu en la serie clásica?", ("Ash", "Luffy", "Gon", "Ichigo"), 0, "Ash Ketchum es el compañero más conocido de Pikachu.", 10),
)


class TriviaService:
    """Deterministic anime quiz engine; answering never calls an LLM/API."""

    def choose_question(self) -> TriviaQuestion:
        return random.choice(QUESTIONS)

    async def start_round(self, session: AsyncSession, chat_id: int, *, duration_seconds: int = 90) -> tuple[TriviaRound, TriviaQuestion] | None:
        active = await session.scalar(select(TriviaRound).where(
            TriviaRound.chat_id == chat_id,
            TriviaRound.status == "active",
            TriviaRound.expires_at > datetime.utcnow(),
        ))
        if active is not None:
            return None
        question = self.choose_question()
        round_row = TriviaRound(
            chat_id=chat_id,
            question=question.question,
            options=json.dumps(question.options, ensure_ascii=False),
            answer_index=question.answer_index,
            explanation=question.explanation,
            points=question.points,
            expires_at=datetime.utcnow() + timedelta(seconds=duration_seconds),
        )
        session.add(round_row)
        try:
            async with session.begin_nested():
                await session.flush()
        except IntegrityError:
            return None
        await session.commit()
        await session.refresh(round_row)
        return round_row, question

    async def answer(
        self,
        session: AsyncSession,
        round_id: int,
        user_id: int,
        option_index: int,
        *,
        chat_id: int | None = None,
    ) -> tuple[str, int | None]:
        round_row = await session.get(TriviaRound, round_id)
        if round_row is None or round_row.status != "active":
            return "expired", None
        if chat_id is not None and round_row.chat_id != chat_id:
            return "wrong_chat", None
        if datetime.utcnow() >= round_row.expires_at:
            round_row.status = "expired"
            await session.commit()
            return "expired", None
        if option_index < 0 or option_index >= len(json.loads(round_row.options)):
            return "invalid", None
        try:
            session.add(TriviaAttempt(round_id=round_id, user_id=user_id, option_index=option_index))
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return "already_answered", None
        if option_index != round_row.answer_index:
            await session.commit()
            return "wrong", None
        claimed = await session.execute(update(TriviaRound).where(
            TriviaRound.id == round_id, TriviaRound.status == "active"
        ).values(status="won", winner_user_id=user_id, won_at=datetime.utcnow()))
        if claimed.rowcount != 1:
            await session.rollback()
            return "lost_race", None
        balance = await MemberRepository().add_points(
            session,
            user_id=user_id,
            chat_id=round_row.chat_id,
            amount=round_row.points,
            reason="Trivia anime",
            reference_type="trivia",
            reference_id=str(round_id),
        )
        return "correct", balance
