from __future__ import annotations

import re

from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity


class CharacterIntentRouter:
    """Small deterministic intent router for everyday character-facing chat.

    This layer deliberately uses explicit keyword families instead of an LLM.
    Unknown text remains unknown so the character can use its authored fallback
    repertoire rather than inventing an answer.
    """

    _KEYWORDS: tuple[tuple[CharacterIntent, tuple[str, ...]], ...] = (
        (
            CharacterIntent.GREETING,
            ("hola", "buenas", "hey", "buenos dias", "buenas tardes", "buenas noches"),
        ),
        (
            CharacterIntent.FAREWELL,
            ("chau", "adios", "nos vemos", "hasta luego", "me voy"),
        ),
        (
            CharacterIntent.THANKS,
            ("gracias", "muchas gracias", "te agradezco"),
        ),
        (
            CharacterIntent.APOLOGY,
            ("perdon", "perdón", "lo siento", "disculpa"),
        ),
        (
            CharacterIntent.HELP,
            (
                "ayuda",
                "ayudame",
                "ayúdame",
                "que podes hacer",
                "qué podés hacer",
                "podes ayudar",
                "podés ayudar",
                "me podes ayudar",
                "me podés ayudar",
            ),
        ),
        (
            CharacterIntent.AFFECTION,
            (
                "te quiero",
                "te aprecio",
                "te extraño",
                "te extrano",
                "me importas",
                "me importás",
            ),
        ),
        (
            CharacterIntent.REASSURANCE,
            (
                "estás bien",
                "estas bien",
                "todo bien",
                "cómo estás",
                "como estas",
                "como está todo",
            ),
        ),
        (
            CharacterIntent.BELONGING,
            (
                "puedo quedarme",
                "me quedo",
                "puedo estar aquí",
                "puedo estar aqui",
                "quédate",
                "quedate",
                "hay lugar",
            ),
        ),
        (
            CharacterIntent.CONFUSION,
            (
                "no entiendo",
                "no comprendo",
                "no sé qué pasó",
                "no se que paso",
                "que pasó",
                "que paso",
                "qué está pasando",
                "que esta pasando",
            ),
        ),
    )

    _TARGETS: tuple[tuple[BotIdentity, tuple[str, ...]], ...] = (
        (BotIdentity.CARI, ("cari",)),
        (BotIdentity.SUNNA, ("sunna",)),
        (BotIdentity.CAMI, ("cami",)),
        (BotIdentity.CHIE, ("chie",)),
    )

    @classmethod
    def target_identity(cls, text: str) -> BotIdentity | None:
        normalized = " ".join(text.casefold().strip().split())
        if not normalized:
            return None
        for identity, aliases in cls._TARGETS:
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\b", normalized):
                    return identity
        return None

    def __init__(self, director: CharacterDirector | None = None) -> None:
        self.director = director or CharacterDirector()

    def classify(self, text: str) -> CharacterIntent | None:
        normalized = " ".join(text.casefold().strip().split())
        if not normalized:
            return None
        for intent, keywords in self._KEYWORDS:
            if any(
                re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
                for keyword in keywords
            ):
                return intent
        return None

    def choose(self, identity: BotIdentity, text: str, *, roll: int = 0):
        intent = self.classify(text)
        if intent is None:
            intent = CharacterIntent.UNKNOWN_TOPIC
        return self.director.choose(identity, intent, roll=roll)
