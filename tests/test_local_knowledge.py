from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.knowledge.retrieval import LocalKnowledgeResponder, is_question_like
from app.modules.chat.module import ChatModule


def test_question_detection_handles_common_spanish_questions() -> None:
    assert is_question_like("¿Qué puede hacer Cari?")
    assert is_question_like("como funciona el cafe")
    assert is_question_like("podés ayudarme")
    assert not is_question_like("hola mundo")


def test_local_knowledge_answers_cari_without_llm() -> None:
    responder = LocalKnowledgeResponder()

    result = responder.answer(BotIdentity.CARI, "¿Qué podés hacer?")

    assert result is not None
    assert result.article.key == "cari_capabilities"
    assert "Café Otaku" in result.article.answer


def test_local_knowledge_uses_pfa_without_turning_cari_into_a_clinician() -> None:
    responder = LocalKnowledgeResponder()

    result = responder.answer(BotIdentity.CARI, "me siento mal y necesito hablar")

    assert result is not None
    assert result.article.key == "cari_support_basics"
    assert "diagnósticos" in result.article.answer


def test_possible_immediate_danger_is_marked_for_human_handoff() -> None:
    responder = LocalKnowledgeResponder()

    decision = responder.should_handoff(
        BotIdentity.CARI,
        "quiero hacerme daño",
    )

    assert decision.required is True
    assert decision.reason == "possible_safety_or_abuse_issue"


def test_unknown_question_stays_unknown_instead_of_getting_an_invented_answer() -> None:
    responder = LocalKnowledgeResponder()

    result = responder.answer(
        BotIdentity.CARI,
        "¿Cuál es el precio de una cafetería en Marte?",
    )

    assert result is None


@pytest.mark.asyncio
async def test_chat_module_answers_known_cari_question_without_brain(database) -> None:
    module = ChatModule(
        database,
        identity=BotIdentity.CARI,
        settings=Settings(ai_enabled=False),
    )
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=99, type="supergroup"),
        text="¿Qué podés hacer?",
        answer=answer,
    )

    assert module._should_handle_text(message.text) is True
    await module.handle_text(message, AsyncMock())

    assert answers
    assert "Café Otaku" in answers[0]


@pytest.mark.asyncio
async def test_chat_module_responds_to_unknown_question_with_authored_fallback(database) -> None:
    module = ChatModule(
        database,
        identity=BotIdentity.CARI,
        settings=Settings(ai_enabled=False),
    )
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=99, type="supergroup"),
        text="¿Cuál es el horario del tren lunar?",
        answer=answer,
    )

    assert module._should_handle_text(message.text) is True
    await module.handle_text(message, AsyncMock())

    assert answers
    assert "no sé" in answers[0].casefold() or "no tengo" in answers[0].casefold()
