"""Acceso controlado a secretos de runtime; nunca registra ni persiste valores."""

from __future__ import annotations

import os


class SecretLoader:
    """Carga secretos únicamente desde variables de entorno."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def get(self, name: str) -> str | None:
        value = self._environ.get(name)
        if value is None or not value.strip():
            return None
        return value

    def require(self, name: str) -> str:
        value = self.get(name)
        if value is None:
            raise RuntimeError(f"required secret is not configured: {name}")
        return value
