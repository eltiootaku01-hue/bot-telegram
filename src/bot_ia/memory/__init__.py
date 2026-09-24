# -*- coding: utf-8 -*-
"""Memoria persistente local, autorizada y separada del canon."""
from .models import MemoryMatch, MemoryStatus, MemoryType, PersistentMemoryRecord
from .store import MemoryStorageError, MemoryStore

__all__ = ["MemoryMatch", "MemoryStatus", "MemoryStorageError", "MemoryStore", "MemoryType", "PersistentMemoryRecord"]
