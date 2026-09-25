from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner, Message

from app.core.config import Settings


PUBLIC_COMMANDS_DISABLED = True


async def is_chat_staff(message: Message, bot: Bot) -> bool:
    """Return whether the sender is a real Telegram group admin/owner."""
    if message.from_user is None or message.chat.type not in {"group", "supergroup"}:
        return False
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))


def is_private(message: Message) -> bool:
    return message.chat.type == "private"


def is_authorized_community(settings: Settings, chat_id: int) -> bool:
    """Return whether a group/supergroup chat is explicitly authorized."""
    return any(
        settings.is_chat_allowed(chat_id, chat_type)
        for chat_type in ("group", "supergroup")
    )
