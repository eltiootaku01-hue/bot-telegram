# -*- coding: utf-8 -*-
"""Supervisión preventiva de publicaciones del SuperAdmin (Cami Guard)."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import unicodedata
from urllib.parse import urlparse

SUPERADMIN_USERNAME = "tiootakuu"
SUPERADMIN_ENV = "TELEGRAM_SUPERADMIN_ID"
DEFAULT_REACTIONS = ("☕", "✨", "❤️", "😂", "👍")
SENSITIVE_IMAGE_TAGS = frozenset({"nsfw", "explicit", "sexual", "porn", "porno", "nudity", "nude", "gore", "violence", "blood", "sensitive", "adult"})
SENSITIVE_TEXT_TERMS = frozenset({"nsfw", "porn", "porno", "pornografia", "pornografía", "sexual", "sexo", "xxx", "desnudo", "desnuda", "desnudez", "gore", "violencia", "sangre"})
ALLOWED_COMMON_TEXT = frozenset({"meme", "memes", "saludo", "saludos", "anuncio", "anuncios", "bienvenido", "bienvenidos", "comunicado"})
BLOCKED_LINK_HOSTS = frozenset({"phishing.example", "malware.example", "grabify.link"})
BLOCKED_LINK_TERMS = frozenset({"phishing", "malware", "credential-steal", "token-grabber"})


@dataclass(frozen=True, slots=True)
class CamiGuardDecision:
    action: str
    reason: str
    spoiler: bool
    target_room: str | None
    reactions: tuple[str, ...]
    alert_admin: bool
    strike_exempt: bool
    message: str


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = "".join(char for char in text if unicodedata.category(char) not in {"Cc", "Cf", "Cs"})
    return " ".join(text.split())


def _tokens(value: object) -> set[str]:
    return set(re.findall(r"[a-záéíóúüñ0-9]+", _normalize(value)))


def _has_any(value: object, terms: frozenset[str]) -> bool:
    tokens = _tokens(value)
    return any(term in tokens for term in terms)


def _urls(value: object) -> tuple[str, ...]:
    return tuple(re.findall(r"https?://[^\s<>]+", str(value or ""), flags=re.I))


def _unsafe_link(value: object) -> bool:
    for raw in _urls(value):
        try:
            parsed = urlparse(raw)
            host = (parsed.hostname or "").casefold().rstrip(".")
        except ValueError:
            return True
        if host in BLOCKED_LINK_HOSTS or any(term in _normalize(raw) for term in BLOCKED_LINK_TERMS):
            return True
    return False


def is_superadmin(user_id: object = "", username: object = "") -> bool:
    configured = os.getenv(SUPERADMIN_ENV, "").strip()
    uid = str(user_id or "").strip()
    name = str(username or "").strip().lstrip("@").casefold()
    if configured and uid == configured:
        return True
    return name == SUPERADMIN_USERNAME.casefold()


def scan_cami_guard(
    text: object,
    *,
    image_tags: tuple[str, ...] = (),
    user_id: object = "",
    username: object = "",
    content_kind: str = "text",
    target_room: str = "#general",
) -> CamiGuardDecision:
    """Clasifica texto y metadatos/tags de imagen sin inventar una detección visual."""
    admin = is_superadmin(user_id, username)
    combined = " ".join([_normalize(text), *(_normalize(tag) for tag in image_tags)])
    unsafe_link = _unsafe_link(text)
    sensitive = _has_any(combined, SENSITIVE_TEXT_TERMS) or any(_has_any(tag, SENSITIVE_IMAGE_TAGS) for tag in image_tags)

    if unsafe_link:
        return CamiGuardDecision("delete_alert", "unsafe_link", False, None, (), True, admin,
                                 "Cami: publicación detenida preventivamente por un enlace potencialmente inseguro.")
    if sensitive:
        return CamiGuardDecision("spoiler_redirect", "sensitive_content", True, "#cantina-18", (), admin, admin,
                                 "Cami: contenido sensible marcado como spoiler y derivado a la zona correspondiente.")
    if _has_any(text, ALLOWED_COMMON_TEXT) or content_kind.casefold() in {"meme", "saludo", "announcement", "anuncio"}:
        return CamiGuardDecision("allow_react", "common_sfw_post", False, target_room, DEFAULT_REACTIONS, False, admin,
                                 "Cami: publicación SFW permitida.")
    return CamiGuardDecision("allow", "clean", False, target_room, (), False, admin, "Cami: publicación permitida.")


def cami_guard_policy_summary() -> str:
    return ("Cami Guard previene publicaciones riesgosas; el SuperAdmin mantiene inmunidad "
            "frente a strikes, mute y ban, pero una publicación riesgosa puede ser detenida preventivamente.")
