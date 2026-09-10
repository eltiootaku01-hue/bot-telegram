from bot_ia.contracts import SessionState
from bot_ia.core.intents import IntentClassifier, normalize_message
from bot_ia.core.local_response import build_local_response
from bot_ia.core.models import EntityCandidate, Intent
from bot_ia.core.references import ReferenceResolver
from datetime import datetime, timedelta, timezone


def test_common_casual_messages_are_local_intents():
    classifier = IntentClassifier()
    assert classifier.classify(normalize_message("hola IA-chan")) is Intent.GREETING
    assert classifier.classify(normalize_message("gracias")) is Intent.GREETING
    assert classifier.classify(normalize_message("perfecto, dale")) is Intent.GREETING


def test_help_and_follow_up_intents_are_recognized():
    classifier = IntentClassifier()
    assert classifier.classify(normalize_message("me ayudas con esto")) is Intent.HELP
    assert classifier.classify(normalize_message("seguimos donde quedamos")) is Intent.CONTINUITY


def test_project_knowledge_overview_is_local():
    classifier = IntentClassifier()
    assert classifier.classify(normalize_message("qué información tienes sobre One Neko Punch?")) is Intent.KNOWLEDGE_OVERVIEW


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


def test_recent_reference_resolves_feminine_follow_up():
    resolver = ReferenceResolver()
    candidate = EntityCandidate("kuro", "one_neko_punch", "Kuro", ("N/A",))
    state = SessionState(
        "session:test",
        "one_neko_punch",
        datetime.now(timezone.utc) + timedelta(hours=1),
    )
    state.recent_reference_ids = ("kuro",)
    resolutions = resolver.resolve("¿y ella qué hace?", "one_neko_punch", (candidate,), state)
    assert any(item.resolved_entity_id == "kuro" for item in resolutions)


def test_bare_article_does_not_create_entity_reference():
    resolver = ReferenceResolver()
    candidate = EntityCandidate("kuro", "one_neko_punch", "Kuro")
    resolutions = resolver.resolve("el capítulo continúa", "one_neko_punch", (candidate,), None)
    assert resolutions == ()
