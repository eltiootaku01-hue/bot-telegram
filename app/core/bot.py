from aiogram import Bot, Dispatcher

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.core.registry import ModuleRegistry
from app.db.database import Database
from app.middleware.member_sync import MemberSyncMiddleware
from app.modules.admin.module import AdminModule
from app.modules.chat.module import ChatModule
from app.modules.game.module import GameModule
from app.modules.media.module import MediaModule
from app.modules.system.module import SystemModule


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
    dispatcher.update.middleware(MemberSyncMiddleware(database))

    registry = ModuleRegistry(dispatcher)
    registry.register(SystemModule(identity))

    # Keep the first split conservative: each identity only loads the routers it owns.
    if identity is BotIdentity.CARI:
        registry.register(ChatModule())
    elif identity is BotIdentity.SUNNA:
        registry.register(GameModule(database))
        registry.register(MediaModule(database))
        registry.register(AdminModule(database))
    elif identity is BotIdentity.CAMI:
        registry.register(AdminModule(database))
    elif identity is BotIdentity.CHIE:
        # Chie starts as a lightweight coordination surface. Its services will grow
        # without forcing it to consume every group update handled by Cari/Sunna.
        pass

    registry.attach_lifecycle()
    return bot, dispatcher, database
