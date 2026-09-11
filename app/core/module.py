from abc import ABC, abstractmethod

from aiogram import Bot, Router

from app.core.tasks import TaskSupervisor


class BotModule(ABC):
    """Plugin boundary with isolated router and supervised background tasks."""

    name: str

    def __init__(self) -> None:
        self.router = Router(name=self.name)
        self.tasks = TaskSupervisor()

    @abstractmethod
    def setup(self) -> None:
        """Register handlers, filters and middleware owned by this module."""
        raise NotImplementedError

    async def on_startup(self, bot: Bot) -> None:
        """Optional long-lived resources/tasks for a module."""

    async def on_shutdown(self) -> None:
        """Always stop module-owned background tasks before process shutdown."""
        await self.tasks.stop_all()
