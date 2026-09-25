from __future__ import annotations

import re
from typing import Mapping

from app.dialogues.models import DialogueEvent, SUPPORTED_IDENTITIES
from app.dialogues.store import DialogueStore

_PLACEHOLDER = re.compile(r"\\{([A-Za-z_][A-Za-z0-9_]*)\\}")
_FALLBACKS = {
    "cari": "(^_^)/ No entendí eso, pero sigo acá en el Café. ¿Probamos otra cosa?",
    "sunna": "(*/ω＼*) No estoy segura de qué querías decir... probemos de nuevo.",
    "cami": "( ಠ_ಠ ) No encontré una acción para eso. Decime qué necesitás.",
    "chie": "( ಠ_ಠ ) Entrada no reconocida. Mantené el orden y probá otra instrucción.",
}

class DialogueManager:
    """RAM-resident deterministic dialogue catalog; never performs runtime file I/O."""

    def __init__(self, path: str) -> None:
        self.store = DialogueStore(path)
        self._catalog = self.store.load()

    def render(
        self,
        event: DialogueEvent | str,
        identity: str,
        variables: Mapping[str, object] | None = None,
    ) -> str:
        phrases = self._catalog.phrases(event, identity)
        if not phrases:
            return self.fallback(identity, variables)
        phrase = phrases[0]
        values = {key: str(value) for key, value in (variables or {}).items()}
        missing = sorted(set(_PLACEHOLDER.findall(phrase)) - values.keys())
        if missing:
            raise ValueError(
                f"Missing dialogue variables for {event}/{identity}: {', '.join(missing)}"
            )
        return phrase.format_map(values)

    def fallback(self, identity: str, variables: Mapping[str, object] | None = None) -> str:
        key = identity.casefold().strip()
        if key not in SUPPORTED_IDENTITIES:
            raise ValueError(f"Unsupported dialogue identity: {identity}")
        return _FALLBACKS[key].format_map(
            {key: str(value) for key, value in (variables or {}).items()}
        )
