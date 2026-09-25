# -*- coding: utf-8 -*-
"""Enrutamiento local entre Café SFW y Cantina +18."""

from __future__ import annotations

from dataclasses import dataclass


MATURE_KEYWORDS = frozenset({
    "nsfw",
    "whisky",
    "whiskey",
    "vodka",
    "ron",
    "tequila",
    "sex",
    "erotica",
    "erótico",
    "erotico",
    "picante",
    "adulto",
    "apuestas",
    "apuesta",
    "blackjack",
    "21",
})

CANTINA_WAITRESSES = ("Scarlet", "Chloé")


@dataclass(frozen=True, slots=True)
class RoomTransition:
    target: str
    waitress: str
    message: str


def is_mature_request(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    return any(keyword in normalized for keyword in MATURE_KEYWORDS)


def sfw_transition(text: str, *, waitress: str = "Cami") -> RoomTransition | None:
    if not is_mature_request(text):
        return None
    selected = "Cari" if str(waitress).casefold() == "cari" else "Cami"
    return RoomTransition(
        target="#cantina-18",
        waitress="Scarlet",
        message=(
            f"{selected}: ¡P-Perdón! Para bebidas tan picantes debes ir a la "
            "Cantina +18 y hablar con Scarlet o Chloé. 💗"
        ),
    )


def mature_game_host(game: str) -> str:
    value = str(game or "").casefold().strip()
    if value in {"21", "blackjack", "apuestas", "apuesta"}:
        return "Scarlet"
    return "Chloé"


def mature_game_message(game: str) -> str:
    host = mature_game_host(game)
    return (
        f"🍷 Cantina +18 · {host} supervisa la mesa de {game}. "
        "Las apuestas y partidas maduras se gestionan en #mesa-de-apuestas-21."
    )
