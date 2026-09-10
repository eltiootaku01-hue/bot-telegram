"""Destinos seguros para abrir una IA después de preparar contexto.

Los destinos son sólo accesos de navegador: este módulo no envía el contexto.
La lista es una allowlist deliberada para evitar que un dato recibido desde una
consulta pueda convertirse accidentalmente en una URL de navegación.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ContextDestination:
    destination_id: str
    display_name: str
    url: str


_DESTINATIONS = (
    ContextDestination("chatgpt", "ChatGPT", "https://chatgpt.com/"),
)


def list_context_destinations() -> tuple[ContextDestination, ...]:
    """Devuelve los destinos externos permitidos por BOT-IA."""
    return _DESTINATIONS


def get_context_destination(destination_id: str) -> ContextDestination:
    """Obtiene un destino permitido o falla sin abrir URLs arbitrarias."""
    for destination in _DESTINATIONS:
        if destination.destination_id == destination_id:
            parsed = urlparse(destination.url)
            if parsed.scheme != "https" or parsed.netloc != "chatgpt.com":
                raise ValueError("context destination is not an approved HTTPS destination")
            return destination
    raise KeyError(f"unknown context destination: {destination_id}")
