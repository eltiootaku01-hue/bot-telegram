# -*- coding: utf-8 -*-
"""Hardening local: mutexes no bloqueantes y sanitización de entradas."""

from __future__ import annotations

from contextlib import contextmanager
import re
import threading
import unicodedata
from collections.abc import Iterator, Iterable


CONTROL_CHARACTERS = frozenset(
    codepoint
    for codepoint in range(0x00, 0x20)
    if codepoint not in {0x09, 0x0A}
)


def sanitize_control_text(value: object, *, max_length: int = 512) -> str:
    """Normaliza texto y elimina caracteres de control peligrosos."""
    if max_length <= 0:
        raise ValueError("max_length debe ser > 0")
    text = unicodedata.normalize("NFKC", str(value or ""))
    # Eliminar de forma explícita NUL y ESC antes del filtrado general.
    # Esto mantiene el contrato de hardening incluso si cambia la tabla
    # de categorías Unicode en una futura refactorización.
    text = text.replace("\x00", "").replace("\x1b", "")
    text = "".join(
        character
        for character in text
        if ord(character) not in CONTROL_CHARACTERS
        and unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )
    text = re.sub(r"[ \t\n]+", " ", text).strip()
    return text[:max_length]


def normalize_tag(value: object) -> str:
    """Normaliza una etiqueta sin crear etiquetas nuevas."""
    return sanitize_control_text(value, max_length=128).casefold()


def whitelist_tag(value: object, allowed_tags: Iterable[str]) -> str:
    """Devuelve únicamente el tag exacto existente en la whitelist."""
    candidate = normalize_tag(value)
    if not candidate:
        return ""
    for allowed in allowed_tags:
        clean = sanitize_control_text(allowed, max_length=128).strip()
        if clean and clean.casefold() == candidate:
            return clean
    return ""


class MutexGuard:
    """Mutex por clave; las solicitudes concurrentes se descartan sin esperar."""

    def __init__(self) -> None:
        self._registry_lock = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def _get_lock(self, key: str) -> threading.Lock:
        normalized = sanitize_control_text(key, max_length=256).casefold()
        if not normalized:
            raise ValueError("Mutex key no puede estar vacío")
        with self._registry_lock:
            return self._locks.setdefault(normalized, threading.Lock())

    def try_acquire(self, key: str) -> bool:
        return self._get_lock(key).acquire(blocking=False)

    def release(self, key: str) -> None:
        self._get_lock(key).release()

    @contextmanager
    def enter(self, key: str) -> Iterator[bool]:
        lock = self._get_lock(key)
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()
