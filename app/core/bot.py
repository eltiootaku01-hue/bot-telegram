from aiogram import Bot, Dispatcher

from app.core.config import Settings
from app.core.registry import ModuleRegistry
from app.modules.system.module import SystemModule


def build_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()

    registry = ModuleRegistry(dispatcher)
    registry.register(SystemModule())

    return bot, dispatcher
