from __future__ import annotations

from datetime import timedelta, timezone
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import ChatPermissions, Message

from app.core.access import is_chat_staff
from app.core.module import BotModule
from app.core.time import utc_now
from app.db.database import Database
from app.db.models import ModerationAction


class ModerationModule(BotModule):
    """Explicit moderator tools for Cari; no automatic AI moderation."""

    name = "moderation"
    SILENCE_MINUTES = 10

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database

    def setup(self) -> None:
        self.router.message.register(self.warn, Command("advertir"))
        self.router.message.register(self.silence, Command("silenciar"))
        self.router.message.register(self.unsilence, Command("desilenciar"))
        self.router.message.register(self.kick, Command("expulsar"))

    async def warn(self, message: Message, bot: Bot) -> None:
        target = await self._prepare_action(message, bot, require_restrict=False)
        if target is None:
            return
        target_user, reason = target
        await self._record(
            message,
            target_user.id,
            "warn",
            reason,
            None,
        )
        name = escape(target_user.full_name)
        suffix = f" Motivo: {escape(reason)}" if reason else ""
        await message.answer(f"⚠️ <b>Advertencia</b> para <b>{name}</b>.{suffix}")

    async def silence(self, message: Message, bot: Bot) -> None:
        target = await self._prepare_action(message, bot, require_restrict=True)
        if target is None:
            return
        target_user, reason = target
        until = utc_now() + timedelta(minutes=self.SILENCE_MINUTES)
        telegram_until = until.replace(tzinfo=timezone.utc)
        try:
            await bot.restrict_chat_member(
                message.chat.id,
                target_user.id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_audios=False,
                    can_send_documents=False,
                    can_send_photos=False,
                    can_send_videos=False,
                    can_send_video_notes=False,
                    can_send_voice_notes=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                ),
                use_independent_chat_permissions=True,
                until_date=telegram_until,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            await message.answer(
                "😰 No pude silenciar al integrante. Revisá que Cari tenga permiso para restringir miembros."
            )
            return

        await self._record(message, target_user.id, "silence", reason, until)
        name = escape(target_user.full_name)
        await message.answer(
            f"🔇 <b>{name}</b> quedó silenciado durante {self.SILENCE_MINUTES} minutos."
        )

    async def unsilence(self, message: Message, bot: Bot) -> None:
        target = await self._prepare_action(message, bot, require_restrict=True)
        if target is None:
            return
        target_user, reason = target
        try:
            await bot.restrict_chat_member(
                message.chat.id,
                target_user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
                use_independent_chat_permissions=True,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            await message.answer(
                "😰 No pude retirar el silencio. Revisá que Cari tenga permiso para restringir miembros."
            )
            return

        await self._record(message, target_user.id, "unsilence", reason, None)
        await message.answer(f"🔊 <b>{escape(target_user.full_name)}</b> ya puede volver a escribir.")

    async def kick(self, message: Message, bot: Bot) -> None:
        target = await self._prepare_action(message, bot, require_restrict=True)
        if target is None:
            return
        target_user, reason = target
        try:
            await bot.ban_chat_member(message.chat.id, target_user.id)
            await bot.unban_chat_member(message.chat.id, target_user.id)
        except (TelegramBadRequest, TelegramForbiddenError):
            await message.answer(
                "😰 No pude expulsar al integrante. Revisá que Cari tenga permiso para restringir miembros."
            )
            return

        await self._record(message, target_user.id, "kick", reason, None)
        await message.answer(f"🚪 <b>{escape(target_user.full_name)}</b> fue expulsado de la comunidad.")

    async def _prepare_action(
        self,
        message: Message,
        bot: Bot,
        *,
        require_restrict: bool,
    ):
        if message.chat.type not in {"group", "supergroup"}:
            return None
        if not await is_chat_staff(message, bot):
            return None
        reply = message.reply_to_message
        if reply is None or reply.from_user is None:
            await message.answer("↩️ Respondé al mensaje de la persona que querés moderar.")
            return None
        target = reply.from_user
        if target.is_bot:
            await message.answer("🤖 No modero cuentas de bots con estas herramientas.")
            return None
        if target.id == message.from_user.id:
            await message.answer("😰 No podés aplicar esta acción sobre vos mismo.")
            return None

        member = await bot.get_chat_member(message.chat.id, target.id)
        status = getattr(member, "status", None)
        status = getattr(status, "value", status)
        if str(status).casefold() in {"administrator", "creator"}:
            await message.answer("🔒 No se puede moderar a un administrador con estas herramientas.")
            return None

        if require_restrict:
            bot_member = await bot.get_chat_member(message.chat.id, (await bot.get_me()).id)
            if not getattr(bot_member, "can_restrict_members", False):
                await message.answer("😰 Cari no tiene permiso para restringir miembros.")
                return None

        parts = (message.text or "").split(maxsplit=1)
        reason = parts[1].strip() if len(parts) == 2 else ""
        return target, reason

    async def _record(
        self,
        message: Message,
        target_user_id: int,
        action: str,
        reason: str,
        until_at,
    ) -> None:
        async with self.database.session(write=True) as session:
            session.add(
                ModerationAction(
                    chat_id=message.chat.id,
                    target_user_id=target_user_id,
                    moderator_user_id=message.from_user.id,
                    action=action,
                    reason=reason,
                    until_at=until_at,
                )
            )
