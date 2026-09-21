from __future__ import annotations

import asyncio
import logging

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.db.database import Database
from app.world.presenter import WorldPresenter
from app.world.service import WorldEventService
from app.world.tools import WorldToolPolicy

logger = logging.getLogger(__name__)


class WorldRuntime:
    """Independent event loop for the game world.

    It owns event lifecycle and tool policy, while a presenter adapter provides
    the actual Telegram transport. No character module is imported here.
    """

    def __init__(
        self,
        database: Database,
        presenter: WorldPresenter,
        *,
        settings: Settings | None = None,
        tools: WorldToolPolicy | None = None,
        poll_seconds: float = 5.0,
        stale_timeout_seconds: int = 300,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        self.database = database
        self.presenter = presenter
        self.settings = settings or get_settings()
        self.tools = tools or WorldToolPolicy()
        self.poll_seconds = poll_seconds
        self.stale_timeout_seconds = stale_timeout_seconds
        self.events = WorldEventService()
        self._stopping = asyncio.Event()

    async def run(self) -> None:
        logger.info("Independent game world runtime started")
        if not self.tools.allowed("world.state.read"):
            raise RuntimeError("world.state.read permission is required")
        if not self.tools.allowed("telegram.publish"):
            logger.info("telegram.publish is disabled; world runtime will remain idle")

        while not self._stopping.is_set():
            try:
                worked = await self.tick()
                if not worked:
                    try:
                        await asyncio.wait_for(
                            self._stopping.wait(),
                            timeout=self.poll_seconds,
                        )
                    except TimeoutError:
                        pass
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("World runtime cycle failed")

    async def tick(self) -> bool:
        if not self.tools.allowed("telegram.publish"):
            return False

        async with self.database.session() as session:
            await self.events.cancel_expired(session)
            await self.events.recover_stale(
                session,
                timeout_seconds=self.stale_timeout_seconds,
            )
            event = await self.events.claim_due(session)
        if event is None:
            return False

        if not is_authorized_community(self.settings, event.chat_id):
            async with self.database.session() as session:
                await self.events.cancel_event(
                    session,
                    event_id=event.event_id,
                    lock_time=self._lock_time(event),
                    reason="target community is not authorized",
                )
            return True

        try:
            result = await self.presenter.present(event)
        except Exception as exc:
            async with self.database.session() as session:
                await self.events.mark_delivery_unknown(
                    session,
                    event_id=event.event_id,
                    lock_time=self._lock_time(event),
                    error=str(exc),
                )
            logger.exception("World presentation failed event=%s", event.event_id)
            return True

        async with self.database.session() as session:
            completed = await self.events.complete(
                session,
                event_id=event.event_id,
                lock_time=self._lock_time(event),
                message_id=result.message_id,
            )
        if not completed:
            logger.warning(
                "World event completion fenced by another worker event=%s",
                event.event_id,
            )
        return True

    @staticmethod
    def _lock_time(event) -> object:
        return event._lock_time
    def stop(self) -> None:
        self._stopping.set()
