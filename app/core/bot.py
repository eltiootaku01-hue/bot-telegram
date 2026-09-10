from aiogram import Bot, Dispatcher

from app.core.config import Settings
from app.core.registry import ModuleRegistry
from app.db.database import Database
from app.middleware.member_sync import MemberSyncMiddleware
from app.modules.chat.module import ChatModule
from app.modules.game.module import GameModule
from app.modules.media.module import MediaModule
from app.modules.system.module import SystemModule


def build_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher, Database]:
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    database = Database(settings.database_url)

    dispatcher.update.middleware(MemberSyncMiddleware(database))

    registry = ModuleRegistry(dispatcher)
    registry.register(SystemModule())
    registry.register(ChatModule())
    registry.register(MediaModule())
    registry.register(GameModule())
    return bot, dispatcher, database
