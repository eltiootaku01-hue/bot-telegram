from __future__ import annotations

from random import Random
from typing import Mapping

from app.dialogues.models import DialogueEvent
from app.dialogues.store import DialogueStore


class DialogueManager:
    """Thin runtime adapter around the shared offline dialogue catalog."""

    def __init__(self, path: str, *, rng: Random | None = None) -> None:
        self.store = DialogueStore(path)
        self.rng = rng or Random()

    def render(
        self,
        event: DialogueEvent | str,
        identity: str,
        variables: Mapping[str, object] | None = None,
    ) -> str:
        from app.dialogues.renderer import DialogueRenderer

        return DialogueRenderer(self.store, rng=self.rng).render(
            event,
            identity,
            variables,
        )
