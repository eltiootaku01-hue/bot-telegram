from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent, PROFILES
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


def test_non_cari_profiles_keep_optional_canon_fields_empty_until_defined():
    for identity in (BotIdentity.SUNNA, BotIdentity.CAMI, BotIdentity.CHIE):
        profile = PROFILES[identity]
        assert profile.core_drive == ""
        assert profile.core_fear == ""
        assert profile.arc_theme == ""


def test_sunna_repertoire_stays_short_and_contained():
    sunna_lines = [scene.text for scene in REPERTOIRE if scene.speaker is BotIdentity.SUNNA]

    assert sunna_lines
    assert all("!" not in line for line in sunna_lines)
    assert max(len(line) for line in sunna_lines) <= 60
