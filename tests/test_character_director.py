from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent
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
    response = director.choose(BotIdentity.CARI, CharacterIntent.UNKNOWN_TOPIC, roll=0)

    assert response is not None
    assert response.follow_up is not None
    assert response.follow_up.speaker is BotIdentity.CAMI
