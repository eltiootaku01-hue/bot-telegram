from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.database import Database
from app.db.models import GameEncounter
from app.ui.game_keyboards import encounter_keyboard
from app.world.models import WorldEventType, WorldPresenterRef
from app.world.presenter import WorldPresentationRejected, WorldPresenter
from app.world.runtime import WorldRuntime


class WorldPresentationModule(BotModule):
    """Bridge one Telegram presenter identity to the independent world runtime."""

    name = "world-runtime"

    def __init__(
        self,
        database: Database,
        identity: BotIdentity | None = None,
        settings: Settings | None = None,
        presenter: WorldPresenterRef | None = None,
    ) -> None:
        super().__init__()
        if presenter is None:
            if identity is None:
                raise ValueError("identity or presenter must be provided")
            presenter = WorldPresenterRef(identity.value, kind="existing_bot")
        self.database = database
        self.identity = identity
        self.settings = settings
        self.presenter_ref = presenter
        self.runtime: WorldRuntime | None = None

    @property
    def presenter_key(self) -> str:
        return f"{self.presenter_ref.kind.value}:{self.presenter_ref.key}"

    def setup(self) -> None:
        return None

    async def on_startup(self, bot: Bot) -> None:
        async def send(event) -> int:
            if (
                event.presenter.key != self.presenter_ref.key
                or event.presenter.kind != self.presenter_ref.kind
            ):
                raise WorldPresentationRejected(
                    f"World event addressed to presenter "
                    f"{event.presenter.kind.value}:{event.presenter.key!s}, "
                    f"but this process owns {self.presenter_key}"
                )

            reply_markup = None
            if event.event_type is WorldEventType.WAIFU_ARRIVAL:
                encounter_id = str(event.payload.get("encounter_id") or "")
                raw_options = event.payload.get("options")
                if not encounter_id or not isinstance(raw_options, list) or not raw_options:
                    raise WorldPresentationRejected(
                        f"Waifu arrival event #{event.event_id} has invalid interaction payload"
                    )
                options = [str(value) for value in raw_options]
                reply_markup = encounter_keyboard(encounter_id, options)

            try:
                sent = await bot.send_message(
                    event.chat_id,
                    event.render_text(),
                    reply_markup=reply_markup,
                )
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                raise WorldPresentationRejected(
                    f"Telegram rejected world event #{event.event_id}: {exc}"
                ) from exc

            if event.event_type is WorldEventType.WAIFU_ARRIVAL:
                encounter_id = str(event.payload.get("encounter_id") or "")
                async with self.database.session() as session:
                    encounter = await session.get(GameEncounter, encounter_id)
                    if encounter is not None and encounter.message_id is None:
                        encounter.message_id = sent.message_id
                        await session.commit()

            return sent.message_id

        presenter = WorldPresenter(send)
        self.runtime = WorldRuntime(
            self.database,
            presenter,
            settings=self.settings,
            presenter_key=self.presenter_key,
        )
        task_name = f"world-runtime-{self.presenter_ref.kind.value}-{self.presenter_ref.key}"
        self.tasks.start(task_name, self.runtime.run())

    async def on_shutdown(self) -> None:
        if self.runtime is not None:
            self.runtime.stop()
        await super().on_shutdown()
