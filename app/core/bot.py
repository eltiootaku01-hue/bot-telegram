from aiogram import Bot, Dispatcher

from app.core.config import Settings
from app.core.registry import ModuleRegistry
from app.db.database import Database
from app.middleware.member_sync import MemberSyncMiddleware
from app.modules.system.module import SystemModule


def build_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher, Database]:
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    database = Database(settings.database_url)

    # Database synchronization happens before handlers. It is deliberately
    # independent from the AI/brain layer so member data remains available
    # even when no LLM call is made.
    dispatcher.update.middleware(MemberSyncMiddleware(database))

    registry = ModuleRegistry(dispatcher)
    registry.register(SystemModule())

    return bot, dispatcher, database
