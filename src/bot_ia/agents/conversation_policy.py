"""Politica conversacional universal, local y separada de canon y memoria."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata
import unicodedata


class ConversationAct(str, Enum):
    FACT = "fact"
    DOUBT = "doubt"
    HYPOTHESIS = "hypothesis"
    IDEA = "idea"
    PROPOSAL = "proposal"
    OPINION = "opinion"
    ADVICE = "advice"
    SUBJECTIVE = "subjective"
    CASUAL = "casual"
    CREATIVE = "creative"
    CLARIFICATION = "clarification"


@dataclass(frozen=True, slots=True)
class ConversationGuidance:
    act: ConversationAct
    epistemic_label: str
    requires_clarification: bool
    requires_llm: bool
    response_mode: str
    follow_up: str | None = None


class ConversationPolicy:
    """Heuristicas conservadoras: clasifican intencion, nunca establecen canon."""

    def assess(
        self,
        message: str,
        recent_context: tuple[str, ...] = (),
    ) -> ConversationGuidance:
        text = " ".join(message.casefold().split())
        normalized_text = "".join(
            character
            for character in unicodedata.normalize("NFD", text)
            if unicodedata.category(character) != "Mn"
        )

        if not text:
            return ConversationGuidance(
                ConversationAct.CLARIFICATION,
                "no_establecido",
                True,
                False,
                "ask",
                "Que deseas explorar?",
            )

        if any(
            word in normalized_text
            for word in (
                "hola",
                "gracias",
                "jaja",
                "que tal",
            )
        ):
            return ConversationGuidance(
                ConversationAct.CASUAL,
                "opinion",
                False,
                False,
                "casual",
            )

        ambiguous = (
            any(
                word in normalized_text
                for word in (
                    "ella",
                    "el",
                    "esa escena",
                    "eso",
                )
            )
            and not recent_context
        )

        # "el" como articulo no debe producir ambiguedad.
        # Solo se considera ambiguo cuando aparece como referencia
        # independiente.
        if re.search(r"\b(el|ella|esa escena|eso)\b", text):
            ambiguous = (
                not recent_context
                and (
                    re.search(r"\bella\b", text) is not None
                    or re.search(r"\besa escena\b", text) is not None
                    or re.search(r"\beso\b", text) is not None
                )
            )

        if "?" in text and ambiguous:
            return ConversationGuidance(
                ConversationAct.DOUBT,
                "no_establecido",
                True,
                False,
                "ask",
                "A que referencia te refieres?",
            )

        # IDEACION: debe evaluarse antes de la regla generica de preguntas.
        if any(
            phrase in normalized_text
            for phrase in (
                "que se te ocurre",
                "que ideas",
                "ideas para",
                "idea para",
                "que podriamos hacer",
                "que podria pasar",
                "que podrias hacer",
                "que podemos hacer",
                "que haria falta",
            )
        ):
            return ConversationGuidance(
                ConversationAct.IDEA,
                "idea",
                False,
                False,
                "discuss",
            )

        if any(
            phrase in normalized_text
            for phrase in (
                "que harias",
                "recomiendas",
                "cual elegirias",
            )
        ):
            return ConversationGuidance(
                ConversationAct.ADVICE,
                "opinion",
                False,
                False,
                "recommendation",
            )

        if any(
            phrase in normalized_text
            for phrase in (
                "que te parece",
                "opinion",
            )
        ):
            return ConversationGuidance(
                ConversationAct.OPINION,
                "opinion",
                False,
                False,
                "opinion",
            )

        if any(
            word in normalized_text
            for word in (
                "escribe",
                "escena",
                "dialogo",
            )
        ):
            return ConversationGuidance(
                ConversationAct.CREATIVE,
                "proposal",
                False,
                True,
                "creative",
            )

        if any(
            word in normalized_text
            for word in (
                "podria",
                "me gusta esta idea",
                "pienso que",
            )
        ):
            return ConversationGuidance(
                ConversationAct.PROPOSAL,
                "proposal",
                False,
                True,
                "discuss_proposal",
            )

        if any(
            word in normalized_text
            for word in (
                "hipotesis",
                "quiza",
                "quizas",
                "tal vez",
            )
        ):
            return ConversationGuidance(
                ConversationAct.HYPOTHESIS,
                "hypothesis",
                False,
                False,
                "qualify",
            )

        if "?" in text and any(
            word in normalized_text
            for word in (
                "quien",
                "que paso",
                "esta mostrado",
            )
        ):
            return ConversationGuidance(
                ConversationAct.FACT,
                "not_established",
                False,
                False,
                "evidence",
            )

        if "?" in text:
            return ConversationGuidance(
                ConversationAct.DOUBT,
                "no_establecido",
                False,
                False,
                "evidence",
            )

        if re.search(r"\b(claro|seguro),?\b", text):
            return ConversationGuidance(
                ConversationAct.DOUBT,
                "ambiguous",
                True,
                False,
                "clarify_tone",
                "Lo dices literalmente o con ironia?",
            )

        return ConversationGuidance(
            ConversationAct.IDEA,
            "idea",
            False,
            False,
            "discuss",
        )




