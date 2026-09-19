from __future__ import annotations

from app.brain.chat import BrainChatModule
from app.core.composition import BotComposition, ModuleSpec
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.social_runtime import SocialRuntimeModule
from app.db.database import Database
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


def _spec(name: str, factory, *identities: BotIdentity) -> ModuleSpec:
    return ModuleSpec(name=name, factory=factory, identities=frozenset(identities))


def build_bot_modules(
    database: Database,
    identity: BotIdentity,
    settings: Settings | None = None,
) -> list[BotModule]:
    """Compose shared and identity-specific bot capabilities from reusable modules."""

    shared = (
        _spec("system", lambda: SystemModule(identity)),
        _spec("social-runtime", lambda: SocialRuntimeModule(database, identity, settings=settings)),
    )
    identity_specific = (
        _spec("chat", lambda: ChatModule(database, identity=identity), *BotIdentity),
        _spec("game", lambda: GameModule(database, settings=settings), BotIdentity.SUNNA),
        _spec("trivia", lambda: TriviaModule(database), BotIdentity.SUNNA),
        _spec("media", lambda: MediaModule(database, settings=settings), BotIdentity.SUNNA),
        _spec("sunna-admin", lambda: AdminModule(database, settings=settings), BotIdentity.SUNNA),
        _spec("cami-media", lambda: CamiMediaModule(database, settings=settings), BotIdentity.CAMI),
        _spec("cami-publisher", lambda: CamiMediaPublisher(database, settings=settings), BotIdentity.CAMI),
        _spec("cami-admin", lambda: AdminModule(database, settings=settings), BotIdentity.CAMI),
        _spec("chie", lambda: ChieModule(database, settings=settings), BotIdentity.CHIE),
        _spec("requests", lambda: RequestModule(database), BotIdentity.CHIE),
        _spec("brain-chat", lambda: BrainChatModule(identity, settings=settings)),
    )

    composition = BotComposition((*shared, *identity_specific))
    return composition.build(identity)
