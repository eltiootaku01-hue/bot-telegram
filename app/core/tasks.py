from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class TaskSupervisor:
    """Owns long-lived background tasks and prevents silent task failures."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def start(self, name: str, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        if name in self._tasks and not self._tasks[name].done():
            coroutine.close()
            raise ValueError(f"Background task already running: {name}")

        task = asyncio.create_task(coroutine, name=name)
        self._tasks[name] = task
        task.add_done_callback(lambda completed: self._finish(name, completed))
        return task

    def _finish(self, name: str, task: asyncio.Task[Any]) -> None:
        self._tasks.pop(name, None)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            logger.exception("Background task failed: %s", name)

    async def stop(self, name: str) -> None:
        task = self._tasks.pop(name, None)
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def stop_all(self) -> None:
        tasks = list(self._tasks.items())
        self._tasks.clear()
        for _, task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)

    def running(self, name: str) -> bool:
        task = self._tasks.get(name)
        return task is not None and not task.done()

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tasks))
