"""Registro en memoria de universos; no persiste datos en Fase 1C."""

from __future__ import annotations

from .models import UniverseDefinition


class DuplicateUniverseError(ValueError):
    pass


class UniverseNotFoundError(KeyError):
    pass


class UniverseRegistry:
    def __init__(self) -> None:
        self._universes: dict[str, UniverseDefinition] = {}

    def register(self, definition: UniverseDefinition) -> None:
        if definition.universe_id in self._universes:
            raise DuplicateUniverseError(f"universe already registered: {definition.universe_id}")
        self._universes[definition.universe_id] = definition

    def get(self, universe_id: str) -> UniverseDefinition:
        try:
            return self._universes[universe_id]
        except KeyError as error:
            raise UniverseNotFoundError(f"unknown universe: {universe_id}") from error

    def contains(self, universe_id: str) -> bool:
        return universe_id in self._universes

    def all(self) -> tuple[UniverseDefinition, ...]:
        return tuple(self._universes.values())
