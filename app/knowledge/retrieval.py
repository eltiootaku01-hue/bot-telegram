from __future__ import annotations

import re
import unicodedata

from app.core.identity import BotIdentity
from app.knowledge.catalog import ARTICLES
from app.knowledge.models import HandoffDecision, KnowledgeAnswer

_STOPWORDS = {
    "a",
    "al",
    "con",
    "como",
    "cuando",
    "de",
    "del",
    "el",
    "en",
    "es",
    "esta",
    "este",
    "hay",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "para",
    "por",
    "que",
    "qué",
    "se",
    "si",
    "un",
    "una",
    "y",
    "yo",
}


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.split())


def is_question_like(text: str) -> bool:
    normalized = normalize(text)
    if "?" in text:
        return True
    return bool(
        re.search(
            r"(?<!\w)(que|como|cuando|donde|quien|por que|para que|puedo|podes|podemos|sabes|tenes|tienes)\b",
            normalized,
        )
    )


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", normalize(value))
        if token not in _STOPWORDS
    }


def _phrase_score(normalized: str, phrase: str) -> int:
    candidate = normalize(phrase)
    if not candidate:
        return 0
    if candidate in normalized:
        return 8 + len(_meaningful_tokens(candidate)) * 3

    candidate_tokens = _meaningful_tokens(candidate)
    message_tokens = _meaningful_tokens(normalized)
    if not candidate_tokens:
        return 0

    overlap = len(candidate_tokens & message_tokens)
    if len(candidate_tokens) == 1:
        return 6 if overlap == 1 else 0
    if overlap < 2:
        return 0
    return overlap * 3


class LocalKnowledgeResponder:
    """Deterministic local answer lookup; no LLM and no external network calls."""

    def __init__(self) -> None:
        self._articles = ARTICLES

    def answer(self, identity: BotIdentity, text: str) -> KnowledgeAnswer | None:
        normalized = normalize(text)
        if not normalized:
            return None

        candidates: list[tuple[int, int, str, KnowledgeAnswer]] = []
        for article in self._articles:
            if article.identity is not identity:
                continue
            score = sum(_phrase_score(normalized, keyword) for keyword in article.keywords)
            if score:
                candidates.append(
                    (
                        score + article.priority // 20,
                        article.priority,
                        article.key,
                        KnowledgeAnswer(article=article, score=score),
                    )
                )

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        score, _, _, result = candidates[0]
        minimum = 6 if is_question_like(text) else 8
        if score < minimum:
            return None
        return result

    def should_handoff(self, identity: BotIdentity, text: str) -> HandoffDecision:
        normalized = normalize(text)

        if any(
            marker in normalized
            for marker in (
                "me quiero morir",
                "quiero hacerme dano",
                "me voy a lastimar",
                "suicidio",
                "violencia",
                "me estan pegando",
                "me estan acosando",
            )
        ):
            return HandoffDecision(True, "possible_safety_or_abuse_issue")

        if not is_question_like(text):
            return HandoffDecision(False, "not_a_question")

        if self.answer(identity, text) is None:
            return HandoffDecision(True, "knowledge_not_found")
        return HandoffDecision(False, "knowledge_available")
