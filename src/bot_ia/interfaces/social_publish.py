# -*- coding: utf-8 -*-
"""Preparación y apertura local de publicaciones sociales desde pedidos existentes."""

from __future__ import annotations

from dataclasses import dataclass
import re
import webbrowser
from urllib.parse import quote


@dataclass(frozen=True, slots=True)
class SocialPublication:
    character: str
    anime: str
    outfit: str
    prompt: str
    hashtags: tuple[str, ...]
    text: str
    invite_url: str


def _tag(value: str) -> str:
    cleaned = re.sub(r"[^\w-]+", "", str(value).strip(), flags=re.UNICODE)
    return f"#{cleaned}" if cleaned else ""


def build_hashtags(*, character: str, anime: str, outfit: str) -> tuple[str, ...]:
    return tuple(
        item for item in (
            _tag(character),
            _tag(anime),
            "#AIArt",
            _tag(outfit),
        ) if item
    )


def build_publication(*, character: str, anime: str, outfit: str, prompt: str, invite_url: str) -> SocialPublication:
    hashtags = build_hashtags(character=character, anime=anime, outfit=outfit)
    text = (
        f"✨ Nueva publicación de {character}\n"
        f"{prompt}\n\n"
        + " ".join(hashtags)
        + f"\n\n{invite_url}"
    )
    return SocialPublication(character, anime, outfit, prompt, hashtags, text, invite_url)


def open_x_draft(publication: SocialPublication) -> str:
    """Abre X en el navegador local con el texto preparado; no publica automáticamente."""
    url = "https://x.com/intent/post?text=" + quote(publication.text, safe="")
    webbrowser.open(url)
    return url
