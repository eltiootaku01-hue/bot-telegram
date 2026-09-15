from app.characters.models import CharacterIntent
from app.characters.router import CharacterIntentRouter
from app.core.identity import BotIdentity


def test_router_classifies_common_explicit_phrases_without_ai():
    router = CharacterIntentRouter()

    assert router.classify("Hola Cari") is CharacterIntent.GREETING
    assert router.classify("gracias por la ayuda") is CharacterIntent.THANKS
    assert router.classify("me voy, hasta luego") is CharacterIntent.FAREWELL
    assert router.classify("me podés ayudar?") is CharacterIntent.HELP
    assert router.classify("esto no tiene un disparador") is None


def test_router_uses_authored_repertoire_for_cari():
    router = CharacterIntentRouter()
    response = router.choose(BotIdentity.CARI, "hola", roll=1)

    assert response is not None
    assert response.scene.speaker is BotIdentity.CARI
    assert response.scene.intent is CharacterIntent.GREETING


def test_router_does_not_match_keywords_inside_other_words():
    router = CharacterIntentRouter()

    assert router.classify("holanda") is None
    assert router.classify("hayey") is None
    assert router.classify("agradecimiento") is None
    assert router.classify("hospital") is None
    assert router.classify("gracioso") is None
    assert router.classify("chaucha") is None
    assert router.classify("hey! hola") is CharacterIntent.GREETING
