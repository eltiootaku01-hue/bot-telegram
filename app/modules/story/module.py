from __future__ import annotations

from html import escape

from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.access import is_authorized_community
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.database import Database
from app.game.story import STORY_ARC_KEY, StoryService, StoryView
from app.services.world import WorldService
from app.ui.cafe_keyboards import story_keyboard


class StoryModule(BotModule):
    """Authored non-canonical story arc for the Café Otaku runtime."""

    name = "story"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.story = StoryService()
        self.world = WorldService()

    def setup(self) -> None:
        self.router.message.register(self.show, Command("historia"))
        self.router.callback_query.register(self.story_callback, F.data.startswith("cafe:story:"))

    @staticmethod
    def _render(view: StoryView) -> str:
        chapter = view.chapter
        cast = ", ".join(identity.value.title() for identity in chapter.characters)
        state = "🏁 Arco completado." if view.progress.completed else f"📖 Capítulo {chapter.number}/{len(StoryService.CHAPTERS)}"
        return "
".join(
            (
                "📖 <b>Historia del Café Otaku</b>",
                f"🧩 <b>{escape(chapter.title)}</b>",
                state,
                "",
                escape(chapter.scene),
                "",
                f"👥 <b>En escena:</b> {escape(cast)}",
                f"🎮 <b>Conexión con el juego:</b> {escape(chapter.gameplay_hook)}",
                "",
                "Esta historia es ficción de runtime. No modifica el canon de la obra.",
            )
        )

    async def _view(self, chat_id: int) -> StoryView:
        async with self.database.session(write=True) as session:
            return await self.story.current(session, chat_id=chat_id)

    async def show(self, message: Message) -> None:
        if message.chat.type not in {"group", "supergroup"}:
            await message.answer("📖 La historia del Café se recorre dentro de la comunidad.")
            return
        if not is_authorized_community(self._settings(), message.chat.id):
            return
        view = await self._view(message.chat.id)
        await message.answer(
            self._render(view),
            reply_markup=story_keyboard(view.progress.chapter, view.progress.completed),
        )
        if message.from_user is not None:
            await self._observe(message.chat.id, message.from_user.id, "story_view")

    async def story_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer("Historia inválida.", show_alert=True)
            return
        chat_id = callback.message.chat.id
        if callback.message.chat.type not in {"group", "supergroup"}:
            await callback.answer("La historia se recorre en la comunidad.", show_alert=True)
            return
        if not is_authorized_community(self._settings(), chat_id):
            await callback.answer("Esta comunidad no está autorizada.", show_alert=True)
            return

        data = (callback.data or "").split(":")
        if len(data) != 4 or data[0:3] != ["cafe", "story", "next"] or not data[3].isdigit():
            await callback.answer("Capítulo inválido.", show_alert=True)
            return

        expected_chapter = int(data[3])
        await callback.answer()

        async with self.database.session(write=True) as session:
            view, advanced = await self.story.advance(
                session,
                chat_id=chat_id,
                expected_chapter=expected_chapter,
            )

        if callback.message is not None:
            await callback.message.edit_text(
                self._render(view),
                reply_markup=story_keyboard(
                    view.progress.chapter,
                    view.progress.completed,
                ),
            )
        await self._observe(
            chat_id,
            callback.from_user.id,
            "story_advance" if advanced else "story_stale_button",
        )

    def _settings(self):
        from app.core.config import get_settings

        return get_settings()

    async def _observe(self, chat_id: int, user_id: int, action_key: str) -> None:
        try:
            async with self.database.session() as session:
                await self.world.observe_action(
                    session,
                    bot_identity=BotIdentity.CARI,
                    action_key=action_key,
                    user_id=user_id,
                    chat_id=chat_id,
                )
        except Exception:
            return
