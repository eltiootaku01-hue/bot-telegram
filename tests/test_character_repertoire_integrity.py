from collections import Counter

from app.characters.models import CharacterIntent
from app.characters.repertoire import REPERTOIRE
from app.core.identity import BotIdentity


_CORE_INTENTS = (
    CharacterIntent.GREETING,
    CharacterIntent.FAREWELL,
    CharacterIntent.THANKS,
    CharacterIntent.HELP,
    CharacterIntent.UNKNOWN_TOPIC,
    CharacterIntent.OUT_OF_SCOPE,
    CharacterIntent.BUSY,
)


def test_each_identity_has_a_minimum_authored_core_repertoire():
    for identity in BotIdentity:
        scenes = [scene for scene in REPERTOIRE if scene.speaker is identity]
        counts = Counter(scene.intent for scene in scenes)

        assert len(scenes) >= 12
        assert all(counts[intent] >= 1 for intent in _CORE_INTENTS)


def test_all_authored_scenes_have_text_and_valid_speaker():
    assert REPERTOIRE
    assert all(scene.text.strip() for scene in REPERTOIRE)
    assert all(scene.speaker in set(BotIdentity) for scene in REPERTOIRE)


def test_follow_up_scenes_have_complete_pair():
    for scene in REPERTOIRE:
        assert scene.follow_up_speaker is None or scene.follow_up_text
