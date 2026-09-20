from aiogram import Bot
import logging

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.community_models import ForumTopic
from app.db.database import Database

logger = logging.getLogger(__name__)


DEFAULT_TOPICS = {
    "comandos": "🤖 COMANDOS DE LA COMUNIDAD",
    "bienvenida": "👋 BIENVENIDAS",
    "reglas": "📜 REGLAS DE LA COMUNIDAD",
    "noticias": "📰 NOTICIAS",
    "undiacomohoy": "📅 UN DÍA COMO HOY",
    "recomendaciondiaria": "⭐ RECOMENDACIÓN DIARIA",
    "curiosidades": "💡 CURIOSIDADES",
    "estrenos": "🎬 ESTRENOS",
    "memes": "😂 MEMES",
    "material": "🖼️ MATERIAL",
    "anime": "🎌 ANIME",
    "debates": "💭 DEBATES",
    "trivia": "🧠 ANIME TRIVIA",
    "misterios": "🕵️ MISTERIOS DE CAMI",
    "waifumon": "🎴 WAIFUMON",
    "puntos": "💰 CANJEO DE PUNTOS",
    "pedidos": "🖼️ PEDIDOS DE IMÁGENES",
}


class ForumTopicService:
    """Keeps stable Telegram forum thread ids out of feature modules."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_thread_id(self, chat_id: int, topic_key: str) -> int | None:
        async with self.database.session() as session:
            row = await session.scalar(
                select(ForumTopic).where(
                    ForumTopic.chat_id == chat_id,
                    ForumTopic.topic_key == topic_key,
                    ForumTopic.enabled.is_(True),
                )
            )
            return row.thread_id if row else None

    async def ensure_topic(
        self,
        bot: Bot,
        chat_id: int,
        topic_key: str,
        *,
        title: str | None = None,
        bot_identity: str = "",
    ) -> int:
        existing = await self.get_thread_id(chat_id, topic_key)
        if existing is not None:
            return existing

        topic_title = title or DEFAULT_TOPICS.get(topic_key, topic_key)
        try:
            topic = await bot.create_forum_topic(chat_id=chat_id, name=topic_title)
        except TelegramForbiddenError as exc:
            raise RuntimeError(
                "No puedo crear temas: el bot necesita ser administrador del supergrupo "
                "con permiso para gestionar temas."
            ) from exc
        except TelegramBadRequest as exc:
            raise RuntimeError(
                "El chat debe ser un supergrupo con modo foro activado para crear temas."
            ) from exc

        async with self.database.session() as session:
            session.add(
                ForumTopic(
                    chat_id=chat_id,
                    topic_key=topic_key,
                    title=topic_title,
                    thread_id=topic.message_thread_id,
                    bot_identity=bot_identity,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await self.get_thread_id(chat_id, topic_key)
                try:
                    await bot.delete_forum_topic(
                        chat_id=chat_id,
                        message_thread_id=topic.message_thread_id,
                    )
                except (TelegramBadRequest, TelegramForbiddenError) as exc:
                    logger.warning(
                        "Could not remove orphan forum topic chat=%s key=%s thread=%s: %s",
                        chat_id,
                        topic_key,
                        topic.message_thread_id,
                        exc,
                    )
                if existing is not None:
                    return existing
                raise
        return topic.message_thread_id
