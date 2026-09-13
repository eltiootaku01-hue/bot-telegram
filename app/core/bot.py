from aiogram import Bot, Dispatcher

from app.brain.chat import BrainChatModule
from app.core.composition import BotComposition, ModuleSpec
from app.core.config import Settings
from app.core.errors import router as error_router
from app.core.identity import BotIdentity
from app.core.registry import ModuleRegistry
from app.core.social_runtime import SocialRuntimeModule
from app.db.database import Database
from app.middleware.member_sync import MemberSyncMiddleware
from app.modules.admin.module import AdminModule
from app.modules.cami_media.module import CamiMediaModule
from app.modules.cami_media.publisher import CamiMediaPublisher
from app.modules.chat.module import ChatModule
from app.modules.chie.module import ChieModule
from app.modules.game.module import GameModule
from app.modules.media.module import MediaModule
from app.modules.requests.module import RequestModule
from app.modules.system.module import SystemModule
from app.modules.trivia.module import TriviaModule


def _composition(database: Database, identity: BotIdentity, settings: Settings) -> BotComposition:
    shared = (
        ModuleSpec(
            "system",
            lambda: SystemModule(identity),
        ),
        ModuleSpec(
            "social_runtime",
            lambda: SocialRuntimeModule(database, identity),
        ),
        ModuleSpec(
            "brain_chat",
            lambda: BrainChatModule(identity, settings),
        ),
    )
    per_identity = (
        ModuleSpec("cari.chat", ChatModule, frozenset({BotIdentity.CARI})),
        ModuleSpec("sunna.game", lambda: GameModule(database), frozenset({BotIdentity.SUNNA})),
        ModuleSpec("sunna.trivia", lambda: TriviaModule(database), frozenset({BotIdentity.SUNNA})),
        ModuleSpec("sunna.media", lambda: MediaModule(database), frozenset({BotIdentity.SUNNA})),
        ModuleSpec("sunna.admin", lambda: AdminModule(database), frozenset({BotIdentity.SUNNA})),
        ModuleSpec("cami.media", lambda: CamiMediaModule(database), frozenset({BotIdentity.CAMI})),
        ModuleSpec("cami.publisher", lambda: CamiMediaPublisher(database), frozenset({BotIdentity.CAMI})),
        ModuleSpec("cami.admin", lambda: AdminModule(database), frozenset({BotIdentity.CAMI})),
        ModuleSpec("chie.core", lambda: ChieModule(database), frozenset({BotIdentity.CHIE})),
        ModuleSpec("chie.requests", lambda: RequestModule(database), frozenset({BotIdentity.CHIE})),
    )
    return BotComposition((*shared, *per_identity))


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
    dispatcher.include_router(error_router)

    registry = ModuleRegistry(dispatcher)
    for module in _composition(database, identity, settings).build(identity):
        registry.register(module)
    registry.attach_lifecycle()
    return bot, dispatcher, database
