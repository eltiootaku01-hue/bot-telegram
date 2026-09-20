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


def test_router_detects_exact_character_addressing() -> None:
    router = CharacterIntentRouter()

    assert router.target_identity("Sunna") is BotIdentity.SUNNA
    assert router.target_identity("hola, Cami") is BotIdentity.CAMI
    assert router.target_identity("Chie, una pregunta") is BotIdentity.CHIE
    assert router.target_identity("cariños") is None


def test_cari_does_not_claim_messages_addressed_to_another_character(database=None):
    # The conversation module must allow the explicitly named bot to own the turn.
    from app.core.identity import BotIdentity
    from app.modules.chat.module import ChatModule

    module = ChatModule(database, identity=BotIdentity.CARI)
    assert module._should_handle_text("Hola Cami") is False
    assert module._should_handle_text("Hola Sunna") is False
    assert module._should_handle_text("Hola Chie") is False
    assert module._should_handle_text("Hola") is False


def test_router_classifies_authored_confusion_phrases() -> None:
    router = CharacterIntentRouter()

    assert router.classify("No entiendo qué pasó") is CharacterIntent.CONFUSION
    assert router.classify("qué está pasando?") is CharacterIntent.CONFUSION
    assert router.classify("no comprendo") is CharacterIntent.CONFUSION


def test_router_returns_character_mentions_in_text_order() -> None:
    router = CharacterIntentRouter()

    assert router.target_identities("Cami y Sunna, una pregunta") == (
        BotIdentity.CAMI,
        BotIdentity.SUNNA,
    )


def test_router_keeps_single_target_backward_compatible() -> None:
    router = CharacterIntentRouter()

    assert router.target_identities("hola Cami") == (BotIdentity.CAMI,)
    assert router.target_identity("hola Cami") is BotIdentity.CAMI
