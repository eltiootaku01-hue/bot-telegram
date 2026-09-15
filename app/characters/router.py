from __future__ import annotations

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
            ("ayuda", "ayudame", "ayúdame", "que podes hacer", "qué podés hacer"),
        ),
    )

    def __init__(self, director: CharacterDirector | None = None) -> None:
        self.director = director or CharacterDirector()

    def classify(self, text: str) -> CharacterIntent | None:
        normalized = " ".join(text.casefold().strip().split())
        if not normalized:
            return None
        for intent, keywords in self._KEYWORDS:
            if any(keyword in normalized for keyword in keywords):
                return intent
        return None

    def choose(self, identity: BotIdentity, text: str, *, roll: int = 0):
        intent = self.classify(text)
        if intent is None:
            intent = CharacterIntent.UNKNOWN_TOPIC
        return self.director.choose(identity, intent, roll=roll)
