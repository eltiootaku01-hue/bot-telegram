# -*- coding: utf-8 -*-
"""Registro en memoria de universos; no persiste datos en Fase 1C."""

from __future__ import annotations

import threading

from .models import UniverseDefinition


class DuplicateUniverseError(ValueError):
    pass


class UniverseNotFoundError(KeyError):
    pass


class UniverseRegistry:
    def __init__(self) -> None:
        self._universes: dict[str, UniverseDefinition] = {}
        self._lock = threading.RLock()

    def register(self, definition: UniverseDefinition) -> None:
        with self._lock:
            if definition.universe_id in self._universes:
                raise DuplicateUniverseError(f"universe already registered: {definition.universe_id}")
            self._universes[definition.universe_id] = definition

    def get(self, universe_id: str) -> UniverseDefinition:
        with self._lock:
            try:
                return self._universes[universe_id]
            except KeyError as error:
                raise UniverseNotFoundError(f"unknown universe: {universe_id}") from error

    def contains(self, universe_id: str) -> bool:
        with self._lock:
            return universe_id in self._universes

    def all(self) -> tuple[UniverseDefinition, ...]:
        with self._lock:
            return tuple(self._universes.values())
