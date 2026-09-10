from aiogram import Bot, Dispatcher

from app.core.config import Settings
from app.core.registry import ModuleRegistry
from app.db.database import Database
from app.middleware.member_sync import MemberSyncMiddleware
from app.modules.game.module import GameModule
from app.modules.system.module import SystemModule


def build_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher, Database]:
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    database = Database(settings.database_url)

    # Persistence stays below the AI/brain layer so member activity and game
    # state remain available even when an update never reaches an LLM.
    dispatcher.update.middleware(MemberSyncMiddleware(database))

    registry = ModuleRegistry(dispatcher)
    registry.register(SystemModule())
    registry.register(GameModule())
    return bot, dispatcher, database
