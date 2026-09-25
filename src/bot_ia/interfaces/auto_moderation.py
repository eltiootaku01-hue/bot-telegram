# -*- coding: utf-8 -*-
"""Auto-moderación prioritaria para mantener separadas las zonas SFW y maduras.

El módulo no intenta interpretar imágenes con un modelo local: clasifica señales
textuales/metadatos disponibles y deja el bloqueo de contenido ilegal explícito
por delante de cualquier otra respuesta del bot.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


LEGAL_SAFETY_TERMS = frozenset({
    "loli",
    "lolita",
    "lolicon",
    "shota",
    "shotacon",
    "minor",
    "minor-aged",
    "underage",
    "under-aged",
    "menor",
    "menores",
    "preteen",
    "pre-teen",
    "child",
    "children",
    "infantil",
    "infante",
    "niña",
    "niño",
    "nina",
    "nino",
})

SEVERE_PROFANITY = frozenset({
    "fuck",
    "fucking",
    "motherfucker",
    "shit",
    "bitch",
    "cunt",
    "puto",
    "puta",
    "putísima",
    "putisima",
    "mierda",
    "joder",
    "cabron",
    "cabrón",
    "coño",
})

EXPLICIT_TERMS = frozenset({
    "nsfw",
    "porn",
    "porno",
    "pornografia",
    "pornografía",
    "sex",
    "sexo",
    "sexual",
    "xxx",
    "desnudo",
    "desnuda",
    "desnudos",
    "desnudas",
    "genital",
    "genitales",
    "erotica",
    "erótica",
    "erotico",
    "erótico",
})

CARI_LEGAL_MESSAGE = (
    "Disculpe, cliente-sama, pero ese contenido no está permitido. "
    "Evite que cierren el Café."
)
CARI_PROFANITY_MESSAGE = (
    "¡Uy! Ese lenguaje está muy fuerte... Si quieres expresar molestia, "
    "¿qué tal si dices '¡Tonto!'? ¿Sí? 😉✨"
)
CANTINA_REDIRECT_MESSAGE = (
    "☕ Cari: Ese contenido no corresponde a la zona SFW. "
    "Si buscas contenido permitido para adultos, dirígete a #cantina-18 "
    "con Scarlet o Chloé."
)


@dataclass(frozen=True, slots=True)
class ModerationDecision:
    action: str
    reason: str
    message: str
    waitress: str = "Cari"
    target_room: str | None = None


def _normalize(text: object) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = "".join(
        char for char in value
        if unicodedata.category(char) not in {"Cc", "Cf", "Cs"}
    )
    return " ".join(value.split())


def _tokens(text: object) -> set[str]:
    return set(re.findall(r"[a-záéíóúüñ0-9]+(?:-[a-záéíóúüñ0-9]+)?", _normalize(text)))


def _has_term(text: object, terms: frozenset[str]) -> bool:
    normalized = _normalize(text)
    tokens = _tokens(normalized)
    return any(term in tokens or re.search(rf"(?<![a-záéíóúüñ0-9]){re.escape(term)}(?![a-záéíóúüñ0-9])", normalized) for term in terms)


def moderate(
    text: object,
    *,
    room_key: str = "general",
    image_tags: tuple[str, ...] = (),
) -> ModerationDecision:
    """Clasifica antes de ejecutar comandos, callbacks o respuestas."""
    combined = " ".join([_normalize(text), *(_normalize(tag) for tag in image_tags)])
    if _has_term(combined, LEGAL_SAFETY_TERMS):
        return ModerationDecision("ban", "illegal_minor_related", CARI_LEGAL_MESSAGE)
    if room_key in {"general", "tcg_collection", "pedidos_sfw", "noticias_otaku"} and _has_term(combined, EXPLICIT_TERMS):
        return ModerationDecision("delete_redirect", "explicit_in_sfw", CANTINA_REDIRECT_MESSAGE, waitress="Scarlet", target_room="#cantina-18")
    if _has_term(combined, SEVERE_PROFANITY):
        return ModerationDecision("delete_warn", "severe_profanity", CARI_PROFANITY_MESSAGE)
    return ModerationDecision("allow", "clean", "")


def moderation_action_priority(decision: ModerationDecision) -> int:
    return {"allow": 0, "delete_warn": 20, "delete_redirect": 30, "ban": 100}.get(decision.action, 50)
