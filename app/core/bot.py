from aiogram import Bot, Dispatcher

from app.core.bot_composition import build_bot_modules
from app.core.config import Settings
from app.core.errors import router as error_router
from app.core.identity import BotIdentity
from app.core.registry import ModuleRegistry
from app.db.database import Database
from app.middleware.access_control import ChatAccessMiddleware
from app.middleware.member_sync import MemberSyncMiddleware


def build_dispatcher(settings: Settings, identity: BotIdentity) -> tuple[Bot, Dispatcher, Database]:
    token = settings.token_for(identity.value)
    if not token:
        raise ValueError(
            f"No Telegram token configured for {identity.value!r}. "
            f"Set BOT_TOKEN_{identity.value.upper()} or the legacy BOT_TOKEN."
        )

    bot = Bot(token=token)
    dispatcher = Dispatcher()
    database = Database(settings.database_url)
    dispatcher.update.middleware(ChatAccessMiddleware(settings))
    dispatcher.update.middleware(MemberSyncMiddleware(database))
    dispatcher.include_router(error_router)

    registry = ModuleRegistry(dispatcher)
    for module in build_bot_modules(database, identity, settings):
        registry.register(module)
    registry.attach_lifecycle()
    return bot, dispatcher, database
