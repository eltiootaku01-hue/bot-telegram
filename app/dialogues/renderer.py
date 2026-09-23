from __future__ import annotations

import re
from random import Random
from typing import Mapping

from app.dialogues.models import DialogueEvent
from app.dialogues.store import DialogueStore


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class DialogueRenderer:
    """Select and render local authored phrases without network access."""

    def __init__(
        self,
        store: DialogueStore,
        *,
        rng: Random | None = None,
    ) -> None:
        self.store = store
        self.rng = rng or Random()

    def render(
        self,
        event: DialogueEvent | str,
        identity: str,
        variables: Mapping[str, object] | None = None,
    ) -> str:
        phrases = self.store.load().phrases(event, identity)
        if not phrases:
            raise LookupError(f"No dialogue available for {event}/{identity}")
        phrase = self.rng.choice(phrases)
        values = {key: str(value) for key, value in (variables or {}).items()}

        missing = sorted(set(_PLACEHOLDER.findall(phrase)) - values.keys())
        if missing:
            raise ValueError(
                f"Missing dialogue variables for {event}/{identity}: {', '.join(missing)}"
            )
        return phrase.format_map(values)
