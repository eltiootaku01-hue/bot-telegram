# -*- coding: utf-8 -*-
"""Localized Character -> existing waitress prompt projection."""

from __future__ import annotations

from bot_ia.providers.prompt_builder import WaitressPromptProfile

from .models import Character
from .sunna import SUNNA


CHARACTER_WAITRESS_MAP: dict[str, str] = {
    "sunna": "sunna",
}
_WAITRESS_CHARACTER_MAP = {
    waitress_id: character_id
    for character_id, waitress_id in CHARACTER_WAITRESS_MAP.items()
}


def resolve_character_for_waitress(waitress_id: str) -> Character | None:
    if not isinstance(waitress_id, str) or not waitress_id.strip():
        raise ValueError("waitress_id is required")
    character_id = _WAITRESS_CHARACTER_MAP.get(waitress_id.strip().casefold())
    if character_id is None:
        return None
    if character_id != SUNNA.character_id:
        raise RuntimeError("unsupported Character V1 mapping")
    SUNNA.require_runtime_eligible()
    return SUNNA


def project_character_to_waitress_profile(
    character: Character,
    *,
    waitress_id: str,
    display_name: str,
    role: str,
) -> WaitressPromptProfile:
    character.require_runtime_eligible()
    if not isinstance(waitress_id, str) or not waitress_id.strip():
        raise ValueError("waitress_id is required")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("display_name is required")
    if not isinstance(role, str) or not role.strip():
        raise ValueError("role is required")

    mapped = resolve_character_for_waitress(waitress_id)
    if mapped is None or mapped.character_id != character.character_id:
        raise ValueError("waitress is not explicitly associated with character")

    personality = _personality_prompt(character)
    return WaitressPromptProfile(
        waitress_id=waitress_id.strip(),
        display_name=display_name.strip(),
        role=role.strip(),
        personality_prompt=personality,
    )


def _personality_prompt(character: Character) -> str:
    traits = ", ".join(character.personality.core_traits)
    strengths = ", ".join(character.personality.strengths)
    weaknesses = ", ".join(character.personality.weaknesses)
    fears = ", ".join(character.personality.fears)
    speech = "; ".join(character.personality.speech_style)
    boundaries = "; ".join(character.personality.behavioral_boundaries)

    parts = [
        f"Identidad canónica: {character.display_name}.",
        f"Rasgos: {traits}.",
        f"Fortalezas: {strengths}.",
        f"Debilidades: {weaknesses}.",
        f"Miedos: {fears}.",
        f"Estilo: {speech}.",
        f"Reglas de interpretación: {boundaries}.",
    ]
    return " ".join(parts)
