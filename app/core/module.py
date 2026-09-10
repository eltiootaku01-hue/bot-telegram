from abc import ABC, abstractmethod

from aiogram import Router


class BotModule(ABC):
    """Small plugin boundary inspired by mature bot/cog systems."""

    name: str

    def __init__(self) -> None:
        self.router = Router(name=self.name)

    @abstractmethod
    def setup(self) -> None:
        """Register handlers, filters and middleware owned by this module."""
        raise NotImplementedError
