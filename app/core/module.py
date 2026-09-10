from abc import ABC, abstractmethod

from aiogram import Bot, Router


class BotModule(ABC):
    """Plugin boundary with optional startup/shutdown lifecycle hooks."""

    name: str

    def __init__(self) -> None:
        self.router = Router(name=self.name)

    @abstractmethod
    def setup(self) -> None:
        """Register handlers, filters and middleware owned by this module."""
        raise NotImplementedError

    async def on_startup(self, bot: Bot) -> None:
        """Optional long-lived tasks/resources for a module."""

    async def on_shutdown(self) -> None:
        """Optional cleanup hook."""
