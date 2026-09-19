from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent, DialogueScene, PROFILES
from app.characters.repertoire import REPERTOIRE
from app.core.identity import BotIdentity


def test_director_selects_authored_variant_without_generating_text():
    director = CharacterDirector()
    first = director.choose(BotIdentity.CARI, CharacterIntent.GREETING, roll=0)
    second = director.choose(BotIdentity.CARI, CharacterIntent.GREETING, roll=1)

    assert first is not None
    assert second is not None
    assert first.scene.text != second.scene.text
    assert first.scene.speaker is BotIdentity.CARI


def test_sunna_unknown_topic_keeps_kuudere_repertoire():
    director = CharacterDirector()
    response = director.choose(BotIdentity.SUNNA, CharacterIntent.UNKNOWN_TOPIC, roll=1)

    assert response is not None
    assert response.scene.text == "No conozco eso."
    assert "¡" not in response.scene.text


def test_cari_can_trigger_authored_friend_intervention():
    director = CharacterDirector()
    responses = [
        director.choose(BotIdentity.CARI, CharacterIntent.UNKNOWN_TOPIC, roll=roll)
        for roll in range(7)
    ]

    follow_ups = [response.follow_up for response in responses if response is not None and response.follow_up]
    assert follow_ups
    assert follow_ups[0] is not None
    assert follow_ups[0].speaker is BotIdentity.CAMI


def test_repertoire_has_no_duplicate_scene_keys():
    keys = [scene.key for scene in REPERTOIRE]
    assert len(keys) == len(set(keys))


def test_every_identity_has_core_limit_and_greeting_scenes():
    director = CharacterDirector()
    for identity in BotIdentity:
        assert director.choose(identity, CharacterIntent.GREETING) is not None
        assert director.choose(identity, CharacterIntent.OUT_OF_SCOPE) is not None


def test_profiles_cover_all_identities():
    assert set(PROFILES) == set(BotIdentity)


def test_cari_profile_exposes_author_canon_drivers():
    cari = PROFILES[BotIdentity.CARI]
    assert "proteger" in cari.core_drive.casefold()
    assert "perder" in cari.core_fear.casefold()
    assert "otros la protejan" in cari.arc_theme.casefold()


def test_cami_profile_exposes_author_canon_drivers():
    cami = PROFILES[BotIdentity.CAMI]
    assert "comprender" in cami.core_drive.casefold()
    assert "perjudicar" in cami.core_fear.casefold()
    assert "razón" in cami.arc_theme.casefold()
    assert "empatía" in cami.arc_theme.casefold()


def test_sunna_profile_exposes_author_canon_drivers():
    sunna = PROFILES[BotIdentity.SUNNA]
    assert "proteger" in sunna.core_drive.casefold()
    assert "sola" in sunna.core_fear.casefold()
    assert "monstruo" in sunna.arc_theme.casefold()
    assert "linaje" in sunna.arc_theme.casefold()
    assert "jörmungandr" in sunna.archetype.casefold()


def test_profiles_without_author_bible_keep_optional_canon_fields_empty():
    for identity in (BotIdentity.CHIE,):
        profile = PROFILES[identity]
        assert profile.core_drive == ""
        assert profile.core_fear == ""
        assert profile.arc_theme == ""


def test_sunna_repertoire_stays_short_and_contained():
    sunna_lines = [scene.text for scene in REPERTOIRE if scene.speaker is BotIdentity.SUNNA]

    assert sunna_lines
    assert all("!" not in line for line in sunna_lines)
    assert max(len(line) for line in sunna_lines) <= 60


def test_sunna_repertoire_includes_growth_beyond_silence():
    sunna_lines = [scene.text for scene in REPERTOIRE if scene.speaker is BotIdentity.SUNNA]

    assert "Gracias por quedarte." in sunna_lines
    assert "Quiero saber qué es." in sunna_lines
    assert "Me gusta cuando está tranquilo." in sunna_lines


def test_cami_and_sunna_have_authored_cross_character_follow_ups():
    director = CharacterDirector()

    cami_response = director.choose(BotIdentity.CAMI, CharacterIntent.UNKNOWN_TOPIC, roll=3)
    sunna_response = director.choose(BotIdentity.SUNNA, CharacterIntent.UNKNOWN_TOPIC, roll=5)

    assert cami_response is not None
    assert cami_response.follow_up is not None
    assert cami_response.follow_up.speaker is BotIdentity.SUNNA
    assert cami_response.follow_up.text == "Sí... me gustaría."

    assert sunna_response is not None
    assert sunna_response.follow_up is not None
    assert sunna_response.follow_up.speaker is BotIdentity.CHIE
    assert "quedarme" in sunna_response.scene.text


def test_cross_character_follow_ups_are_authored_dialogue_scenes():
    interaction_scenes = [scene for scene in REPERTOIRE if scene.follow_up_speaker is not None]

    assert interaction_scenes
    for scene in interaction_scenes:
        assert scene.follow_up_text
        assert scene.follow_up_speaker is not scene.speaker


def test_every_identity_has_authored_emotional_interaction_scenes():
    director = CharacterDirector()

    for identity in BotIdentity:
        assert director.choose(identity, CharacterIntent.AFFECTION) is not None
        assert director.choose(identity, CharacterIntent.REASSURANCE) is not None
        assert director.choose(identity, CharacterIntent.BELONGING) is not None


def test_director_honors_authored_scene_weights() -> None:
    weighted = (
        DialogueScene(
            "weighted-heavy",
            CharacterIntent.GREETING,
            BotIdentity.CARI,
            "heavy",
            weight=3,
        ),
        DialogueScene(
            "weighted-light",
            CharacterIntent.GREETING,
            BotIdentity.CARI,
            "light",
            weight=1,
        ),
    )
    director = CharacterDirector(weighted)

    assert director.choose(BotIdentity.CARI, CharacterIntent.GREETING, roll=0).scene.text == "heavy"
    assert director.choose(BotIdentity.CARI, CharacterIntent.GREETING, roll=1).scene.text == "heavy"
    assert director.choose(BotIdentity.CARI, CharacterIntent.GREETING, roll=2).scene.text == "heavy"
    assert director.choose(BotIdentity.CARI, CharacterIntent.GREETING, roll=3).scene.text == "light"


def test_cross_character_cafe_scenes_cover_the_four_friendships() -> None:
    director = CharacterDirector()

    expected = (
        (BotIdentity.CARI, CharacterIntent.BELONGING, BotIdentity.SUNNA),
        (BotIdentity.CARI, CharacterIntent.REASSURANCE, BotIdentity.CAMI),
        (BotIdentity.CAMI, CharacterIntent.HELP, BotIdentity.CHIE),
        (BotIdentity.SUNNA, CharacterIntent.AFFECTION, BotIdentity.CARI),
        (BotIdentity.SUNNA, CharacterIntent.CONFUSION, BotIdentity.CAMI),
        (BotIdentity.CHIE, CharacterIntent.HELP, BotIdentity.CAMI),
        (BotIdentity.CHIE, CharacterIntent.REASSURANCE, BotIdentity.SUNNA),
    )

    for speaker, intent, follow_up in expected:
        found = [
            director.choose(speaker, intent, roll=index)
            for index in range(16)
        ]
        assert any(
            response is not None
            and response.follow_up is not None
            and response.follow_up.speaker is follow_up
            for response in found
        )


def test_cross_character_scenes_remain_authored_and_deterministic() -> None:
    director = CharacterDirector()
    first = director.choose(BotIdentity.SUNNA, CharacterIntent.AFFECTION, roll=3)
    second = director.choose(BotIdentity.SUNNA, CharacterIntent.AFFECTION, roll=3)

    assert first == second
    assert first is not None
    assert first.follow_up is not None
    assert "Gracias por esperarme" in first.scene.text
