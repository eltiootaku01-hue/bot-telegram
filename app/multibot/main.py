from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import get_settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.middleware.access_control import ChatAccessMiddleware
from app.middleware.member_sync import MemberSyncMiddleware
from app.multibot.config import MultiBotConfig
from app.multibot.dialogues.manager import DialogueManager
from app.multibot.filters import BotIdentityFilter
from app.multibot.handlers import cami, cari, chie, sunna
from app.multibot.vault_client import VaultClient

logger = logging.getLogger(__name__)


def build_bots(config: MultiBotConfig) -> dict[BotIdentity, Bot]:
    return {
        identity: Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        for identity, token in config.tokens().items()
    }


async def build_dispatcher(
    config: MultiBotConfig,
) -> tuple[Dispatcher, dict[BotIdentity, Bot], Database]:
    bots = build_bots(config)
    bot_ids: dict[BotIdentity, int] = {}
    for identity, bot in bots.items():
        me = await bot.get_me()
        bot_ids[identity] = me.id

    settings = get_settings()
    dialogues_path = Path(settings.dialogues_path)
    if not dialogues_path.is_absolute():
        dialogues_path = Path.cwd() / dialogues_path
    dialogues = DialogueManager(str(dialogues_path))
    vault = VaultClient(config.vault_api_url, config.vault_api_token)

    database = Database(settings.database_url)
    await database.create_schema()

    dp = Dispatcher()
    dp.update.middleware(ChatAccessMiddleware(settings))
    dp.update.middleware(MemberSyncMiddleware(database))

    for identity, builder in (
        (BotIdentity.SUNNA, sunna.build_router),
        (BotIdentity.CARI, cari.build_router),
        (BotIdentity.CAMI, cami.build_router),
        (BotIdentity.CHIE, chie.build_router),
    ):
        identity_filter = BotIdentityFilter(identity, bot_ids)
        if identity is BotIdentity.SUNNA:
            router = builder(
                identity_filter=identity_filter,
                vault=vault,
                dialogues=dialogues,
                bank_key=config.default_bank_key,
            )
        elif identity is BotIdentity.CARI:
            router = builder(
                identity_filter=identity_filter,
                dialogues=dialogues,
                vault=vault,
            )
        elif identity is BotIdentity.CAMI:
            router = builder(
                identity_filter=identity_filter,
                vault=vault,
            )
        else:
            router = builder(
                identity_filter=identity_filter,
                vault=vault,
                dialogues=dialogues,
                database=database,
                master_user_id=settings.master_user_id,
                bank_key=config.default_bank_key,
            )
        dp.include_router(router)

    return dp, bots, database


async def run() -> None:
    config = MultiBotConfig.from_env()
    dp, bots, database = await build_dispatcher(config)
    logger.info(
        "Starting multibot polling for %s",
        ", ".join(identity.value for identity in bots),
    )
    try:
        await dp.start_polling(
            *bots.values(),
            allowed_updates=dp.resolve_used_update_types(),
            handle_as_tasks=True,
        )
    finally:
        await database.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
