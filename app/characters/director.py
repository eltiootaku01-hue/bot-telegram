from __future__ import annotations

from dataclasses import dataclass

from app.characters.models import CharacterIntent, DialogueScene
from app.characters.repertoire import REPERTOIRE
from app.core.identity import BotIdentity


@dataclass(frozen=True, slots=True)
class CharacterResponse:
    scene: DialogueScene
    follow_up: DialogueScene | None = None


class CharacterDirector:
    """Deterministic selector for the characters' authored repertoire.

    It never generates text. The caller supplies the intent and a stable roll so
    the same runtime can be deterministic while still offering several authored
    variants.
    """

    def __init__(self, repertoire: tuple[DialogueScene, ...] = REPERTOIRE) -> None:
        self._by_key: dict[tuple[BotIdentity, CharacterIntent], tuple[DialogueScene, ...]] = {}
        for scene in repertoire:
            key = (scene.speaker, scene.intent)
            self._by_key[key] = (*self._by_key.get(key, ()), scene)

    def choose(
        self,
        identity: BotIdentity,
        intent: CharacterIntent,
        *,
        roll: int = 0,
    ) -> CharacterResponse | None:
        scenes = self._by_key.get((identity, intent), ())
        if not scenes:
            return None
        scene = scenes[abs(roll) % len(scenes)]
        follow_up = None
        if scene.follow_up_speaker is not None and scene.follow_up_text:
            follow_up = DialogueScene(
                key=f"{scene.key}:follow-up",
                intent=intent,
                speaker=scene.follow_up_speaker,
                text=scene.follow_up_text,
            )
        return CharacterResponse(scene=scene, follow_up=follow_up)
