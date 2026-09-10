from bot_ia.core.intents import IntentClassifier, normalize_message
from bot_ia.core.local_response import build_local_response
from bot_ia.core.models import Intent


def test_common_casual_messages_are_local_intents():
    classifier = IntentClassifier()
    assert classifier.classify(normalize_message("hola IA-chan")) is Intent.GREETING
    assert classifier.classify(normalize_message("gracias")) is Intent.GREETING
    assert classifier.classify(normalize_message("perfecto, dale")) is Intent.GREETING


def test_help_and_follow_up_intents_are_recognized():
    classifier = IntentClassifier()
    assert classifier.classify(normalize_message("me ayudas con esto")) is Intent.HELP
    assert classifier.classify(normalize_message("seguimos donde quedamos")) is Intent.CONTINUITY


def test_knowledge_overview_is_local_and_mentions_inventory():
    text = build_local_response(
        Intent.KNOWLEDGE_OVERVIEW,
        "qué información tienes sobre One Neko Punch?",
        "one_neko_punch",
        ("Cap 1.md", "Cap 2.md", "lore.md"),
    )
    assert text is not None
    assert "3 documento(s)" in text
    assert "Cap 1.md" in text
