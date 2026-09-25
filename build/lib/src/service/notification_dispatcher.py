from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from src.db.event_repository import EventRepository

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from pydantic import HttpUrl

logger = logging.getLogger("NotificationDispatcher")


class TelegramNotificationDispatcher:
    """Asynchronous Telegram notification queue with per-chat flood protection.

    Telegram documents a 20-messages/minute limit for bots in a group.  The
    dispatcher therefore spaces successful sends to the same target chat by at
    least three seconds, while still honoring TelegramRetryAfter when Telegram
    asks for a longer delay.
    """

    def __init__(
        self,
        bot_tokens: Mapping[str, str],
        target_chat_id: int,
        *,
        event_bot_map: Mapping[str, str] | None = None,
        min_interval_seconds: float = 3.0,
        max_retries: int = 3,
        event_repository: "EventRepository | None" = None,
    ) -> None:
        if target_chat_id == 0:
            raise ValueError("target_chat_id must be a non-zero Telegram chat id.")
        if min_interval_seconds <= 0:
            raise ValueError("min_interval_seconds must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.target_chat_id = target_chat_id
        self.bots: dict[str, Bot] = {
            name.strip().casefold(): Bot(token=token)
            for name, token in bot_tokens.items()
            if name.strip() and token.strip()
        }
        self.event_bot_map = {
            event.strip(): bot.strip().casefold()
            for event, bot in (event_bot_map or {}).items()
            if event.strip() and bot.strip()
        }
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self.event_repository = event_repository
        self._queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._is_running = False
        self._last_send_at = 0.0
        self._rate_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._is_running:
            return
        if not self.bots:
            raise RuntimeError("No Telegram bots are configured for the dispatcher.")
        self._is_running = True
        self._worker_task = asyncio.create_task(
            self._process_queue(),
            name="telegram-notification-dispatcher",
        )
        logger.info("NotificationDispatcher iniciado con %d bot(s).", len(self.bots))

    async def stop(self, drain_timeout: float = 10.0) -> None:
        """Drain queued notifications before cancelling the worker.

        The worker must remain running while queue.join() waits; setting
        _is_running to False first would make the worker exit after its
        current item and leave the rest of the queue permanently unfinished.
        """
        if drain_timeout < 0:
            raise ValueError("drain_timeout must be non-negative.")

        task = self._worker_task
        if task is not None and not task.done() and not self._queue.empty():
            pending = self._queue.qsize()
            logger.info(
                "Drenando cola de notificaciones (%d pendientes, timeout: %.1fs)...",
                pending,
                drain_timeout,
            )
            try:
                await asyncio.wait_for(self._queue.join(), timeout=drain_timeout)
                logger.info("Cola drenada exitosamente antes del apagado.")
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout de %.1fs alcanzado. Quedan %d elementos sin retirar "
                    "de la cola; los elementos en procesamiento también podrán "
                    "ser recuperados desde SQLite al reiniciar.",
                    drain_timeout,
                    self._queue.qsize(),
                )

        self._is_running = False
        self._worker_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        for bot in self.bots.values():
            await bot.session.close()
        logger.info("NotificationDispatcher detenido y sesiones de aiogram cerradas.")

    async def enqueue_notification(
        self,
        bot_name: str,
        thread_id: int,
        title: str,
        url: HttpUrl,
        author: str,
        event_id: str | None = None,
    ) -> None:
        bot_key = bot_name.strip().casefold()
        if bot_key not in self.bots:
            raise ValueError(f"Bot '{bot_name}' no está configurado en el dispatcher.")
        if thread_id <= 0:
            raise ValueError("thread_id must be positive.")

        await self._queue.put(
            {
                "bot_name": bot_key,
                "thread_id": thread_id,
                "title": title,
                "url": str(url),
                "author": author,
                "event_id": event_id,
            }
        )

    async def dispatch(self, thread_id: int, payload: object) -> None:
        """Adapter matching the FastAPI NotificationDispatcher contract."""
        event_type = getattr(payload, "event_type", "")
        bot_name = self.event_bot_map.get(event_type)
        if bot_name is None:
            raise RuntimeError(
                f"No Telegram bot mapping configured for event '{event_type}'."
            )
        await self.enqueue_notification(
            bot_name=bot_name,
            thread_id=thread_id,
            title=str(getattr(payload, "title", "")),
            url=getattr(payload, "url"),
            author=str(getattr(payload, "author", "Anónimo")),
            event_id=getattr(payload, "event_id", None),
        )

    async def _process_queue(self) -> None:
        while self._is_running:
            payload = await self._queue.get()
            try:
                await self._deliver(payload)
            except Exception:
                logger.exception("Unhandled notification delivery error.")
            finally:
                self._queue.task_done()

    async def _deliver(self, payload: dict[str, object]) -> None:
        bot = self.bots[str(payload["bot_name"])]
        text = self._render_message(payload)
        event_id = payload.get("event_id")
        attempts = 0

        while attempts <= self.max_retries:
            await self._wait_for_chat_rate_limit()
            try:
                message = await bot.send_message(
                    chat_id=self.target_chat_id,
                    message_thread_id=int(payload["thread_id"]),
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
                self._last_send_at = time.monotonic()
                if self.event_repository is not None and event_id:
                    telegram_message_id = getattr(message, "message_id", None)
                    if telegram_message_id is not None:
                        await self.event_repository.mark_delivered(
                            str(event_id), int(telegram_message_id)
                        )
                logger.info(
                    "Telegram notification delivered: bot=%s thread=%s",
                    payload["bot_name"],
                    payload["thread_id"],
                )
                return
            except TelegramRetryAfter as exc:
                attempts += 1
                logger.warning(
                    "Telegram flood control: waiting %ss (attempt %d/%d).",
                    exc.retry_after,
                    attempts,
                    self.max_retries,
                )
                if attempts > self.max_retries:
                    logger.error("Notification discarded after Telegram flood retries.")
                    if self.event_repository is not None and event_id:
                        await self.event_repository.record_attempt_failure(
                            str(event_id), str(exc), is_final=True
                        )
                    return
                await asyncio.sleep(exc.retry_after)
            except (TelegramNetworkError, TelegramServerError) as exc:
                attempts += 1
                if attempts > self.max_retries:
                    logger.error("Notification discarded after transient Telegram errors: %s", exc)
                    if self.event_repository is not None and event_id:
                        await self.event_repository.record_attempt_failure(
                            str(event_id), str(exc), is_final=True
                        )
                    return
                delay = min(2**attempts, 30)
                logger.warning(
                    "Transient Telegram error; retrying in %ss (attempt %d/%d): %s",
                    delay,
                    attempts,
                    self.max_retries,
                    exc,
                )
                if self.event_repository is not None and event_id:
                    await self.event_repository.record_attempt_failure(str(event_id), str(exc))
                await asyncio.sleep(delay)
            except TelegramAPIError as exc:
                logger.error("Non-retryable Telegram API error; notification discarded: %s", exc)
                if self.event_repository is not None and event_id:
                    await self.event_repository.record_attempt_failure(
                        str(event_id), str(exc), is_final=True
                    )
                return

    async def _wait_for_chat_rate_limit(self) -> None:
        async with self._rate_lock:
            elapsed = time.monotonic() - self._last_send_at
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

    @staticmethod
    def _render_message(payload: dict[str, object]) -> str:
        title = html.escape(str(payload["title"]))
        author = html.escape(str(payload["author"]))
        url = html.escape(str(payload["url"]), quote=True)
        return (
            f"<b>{title}</b>\n\n"
            f"👤 <b>Autor:</b> {author}\n"
            f"🔗 <a href=\"{url}\">Ver publicación</a>"
        )
