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
    """Deterministic selector for authored character scenes and interactions."""

    def __init__(self, repertoire: tuple[DialogueScene, ...] = REPERTOIRE) -> None:
        self._by_key: dict[tuple[BotIdentity, CharacterIntent], tuple[DialogueScene, ...]] = {}
        self._interactions: dict[
            tuple[BotIdentity, BotIdentity, CharacterIntent],
            tuple[DialogueScene, ...],
        ] = {}
        for scene in repertoire:
            key = (scene.speaker, scene.intent)
            self._by_key[key] = (*self._by_key.get(key, ()), scene)
            if scene.follow_up_speaker is not None and scene.follow_up_text:
                interaction_key = (scene.speaker, scene.follow_up_speaker, scene.intent)
                self._interactions[interaction_key] = (
                    *self._interactions.get(interaction_key, ()),
                    scene,
                )

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
        return self._response(self._weighted_scene(scenes, roll), intent)

    def choose_interaction(
        self,
        identity: BotIdentity,
        partner: BotIdentity,
        intent: CharacterIntent,
        *,
        roll: int = 0,
    ) -> CharacterResponse | None:
        """Choose an authored two-character scene when one exists for the pair."""
        scenes = self._interactions.get((identity, partner, intent), ())
        if not scenes and intent is not CharacterIntent.UNKNOWN_TOPIC:
            scenes = self._interactions.get(
                (identity, partner, CharacterIntent.UNKNOWN_TOPIC),
                (),
            )
        if not scenes:
            return None
        return self._response(self._weighted_scene(scenes, roll), scenes[0].intent)

    @staticmethod
    def _response(scene: DialogueScene, intent: CharacterIntent) -> CharacterResponse:
        follow_up = None
        if scene.follow_up_speaker is not None and scene.follow_up_text:
            follow_up = DialogueScene(
                key=f"{scene.key}:follow-up",
                intent=intent,
                speaker=scene.follow_up_speaker,
                text=scene.follow_up_text,
            )
        return CharacterResponse(scene=scene, follow_up=follow_up)

    @staticmethod
    def _weighted_scene(
        scenes: tuple[DialogueScene, ...],
        roll: int,
    ) -> DialogueScene:
        total_weight = sum(scene.weight for scene in scenes)
        cursor = abs(roll) % total_weight
        for scene in scenes:
            if cursor < scene.weight:
                return scene
            cursor -= scene.weight
        return scenes[-1]
