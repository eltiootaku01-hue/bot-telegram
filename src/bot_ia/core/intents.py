"""Clasificador extensible de reglas locales, sin modelos estadísticos."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .models import Intent, NormalizedMessage


@dataclass(frozen=True, slots=True)
class IntentRule:
    intent: Intent
    patterns: tuple[str, ...]

    def matches(self, text: str) -> bool:
        comparable = _comparison_text(text)
        return any(
            re.search(pattern, comparable) is not None
            for pattern in self.patterns
        )


RULES: tuple[IntentRule, ...] = (
    IntentRule(
        Intent.UNIVERSE_CHANGE,
        (
            r"\bcambiar?\b",
            r"\btrabajar\b.*\buniverso\b",
            r"\botro universo\b",
        ),
    ),
    IntentRule(
        Intent.CREATIVE_WRITING,
        (
            r"\bescribe\b",
            r"\bescena\b",
            r"\brelato\b",
        ),
    ),
    IntentRule(
        Intent.EDITORIAL_REVIEW,
        (
            r"\brevisa\b",
            r"\bedita\b",
            r"\bcorreccion\b",
        ),
    ),
    IntentRule(
        Intent.EXTERNAL_RESEARCH,
        (
            r"\binvestiga\b",
            r"\bbusca en web\b",
            r"\bfuente externa\b",
        ),
    ),
    IntentRule(
        Intent.CANON,
        (
            r"\bcanon\b",
        ),
    ),
    IntentRule(
        Intent.CONTINUITY,
        (
            r"\bcontinuidad\b",
            r"\bconsistenc\w*\b",
        ),
    ),
    IntentRule(
        Intent.CHARACTER,
        (
            r"\bquien es\b",
            r"\bpersonaje\b",
            r"\balias\b",
        ),
    ),
    IntentRule(
        Intent.HELP,
        (
            r"^ayuda\b",
            r"^help\b",
        ),
    ),
    IntentRule(
        Intent.GREETING,
        (
            r"^(hola|buenas|hey)\b",
        ),
    ),

    # Las solicitudes de ideación ganan prioridad frente
    # a la regla factual genérica.
    IntentRule(
        Intent.IDEA,
        (
            r"\bque\s+se\s+te\s+ocurre\b",
            r"\bque\s+ideas\b",
            r"\bideas\s+para\b",
            r"\bidea\s+para\b",
            r"\bque\s+podriamos\s+hacer\b",
            r"\bque\s+podria\s+pasar\b",
            r"\blluvia\s+de\s+ideas\b",
            r"\bidea\b",
        ),
    ),

    IntentRule(
        Intent.ORGANIZATION,
        (
            r"\borganiza\b",
            r"\bplanifica\b",
            r"\bordena\b",
        ),
    ),

    # Factual debe permanecer después de IDEA.
    IntentRule(
        Intent.FACTUAL,
        (
            r"\bque\b",
            r"\bquien\b",
            r"\bcuando\b",
            r"\bdonde\b",
        ),
    ),
)


def normalize_message(message: str) -> NormalizedMessage:
    if not message or not message.strip():
        raise ValueError("message cannot be empty")

    original = message
    repaired = _repair_mojibake(message)
    normalized = " ".join(repaired.casefold().split())
    tokens = tuple(
        re.findall(
            r"[\w]+",
            normalized,
            flags=re.UNICODE,
        )
    )

    return NormalizedMessage(original, normalized, tokens)


class IntentClassifier:
    def __init__(self, rules: tuple[IntentRule, ...] = RULES) -> None:
        self._rules = rules

    def classify(self, message: NormalizedMessage) -> Intent:
        for rule in self._rules:
            if rule.matches(message.normalized):
                return rule.intent
        return Intent.UNKNOWN


def _comparison_text(text: str) -> str:
    repaired = _repair_mojibake(text)
    decomposed = unicodedata.normalize("NFKD", repaired)
    without_accents = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char)
    )
    return " ".join(without_accents.casefold().split())


def _repair_mojibake(text: str) -> str:
    """Repara UTF-8 interpretado accidentalmente como Latin-1."""
    suspicious = ("Ã", "Â", "â", "ð", " ")

    if not any(marker in text for marker in suspicious):
        return text

    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

    original_score = sum(text.count(marker) for marker in suspicious)
    repaired_score = sum(repaired.count(marker) for marker in suspicious)

    return repaired if repaired_score < original_score else text