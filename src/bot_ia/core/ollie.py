"""Ayudante ligero de orientación para el flujo local."""

from __future__ import annotations

from bot_ia.core.models import Intent, OllieGuide


class OllieGuideBuilder:
    """Construye guías pequeñas y deterministas para orientar el siguiente paso."""

    def build(self, intent: Intent) -> OllieGuide:
        if intent is Intent.IDEA:
            return OllieGuide(
                task_type="ideation",
                search_topics=(
                    "recent_continuity",
                    "active_characters",
                    "relationships",
                    "pending_conflicts",
                    "existing_ideas",
                    "supporting_material",
                ),
                source_hints=(
                    "chapter",
                    "character",
                    "material",
                    "planning",
                    "outline",
                ),
                compact_request=(
                    "Preparar material interno relevante para idear "
                    "posibles direcciones de la historia."
                ),
            )

        if intent is Intent.CREATIVE_WRITING:
            return OllieGuide(
                task_type="creative_writing",
                search_topics=(
                    "relevant_characters",
                    "recent_continuity",
                    "established_events",
                    "relationships",
                ),
                source_hints=(
                    "chapter",
                    "character",
                    "internal_canon",
                    "material",
                    "style",
                ),
                compact_request=(
                    "Preparar el contexto mínimo necesario para escribir "
                    "sin contradecir hechos establecidos."
                ),
            )

        if intent is Intent.CHARACTER:
            return OllieGuide(
                task_type="character_analysis",
                search_topics=(
                    "character_identity",
                    "personality",
                    "history",
                    "relationships",
                ),
                source_hints=(
                    "character",
                    "chapter",
                    "internal_canon",
                ),
                compact_request=(
                    "Preparar la información establecida relevante "
                    "sobre el personaje solicitado."
                ),
            )

        if intent in {Intent.CANON, Intent.FACTUAL}:
            return OllieGuide(
                task_type="fact_check",
                search_topics=(
                    "established_facts",
                    "source_provenance",
                    "conflicts",
                ),
                source_hints=(
                    "internal_canon",
                    "chapter",
                    "character",
                ),
                compact_request=(
                    "Preparar evidencia suficiente para responder "
                    "solo con información establecida."
                ),
            )

        if intent is Intent.CONTINUITY:
            return OllieGuide(
                task_type="continuity_check",
                search_topics=(
                    "recent_events",
                    "timeline",
                    "characters",
                    "conflicts",
                ),
                source_hints=(
                    "chapter",
                    "outline",
                    "planning",
                    "internal_canon",
                ),
                compact_request=(
                    "Preparar el material necesario para comprobar "
                    "continuidad y detectar contradicciones."
                ),
            )

        if intent is Intent.EDITORIAL_REVIEW:
            return OllieGuide(
                task_type="editorial_review",
                search_topics=(
                    "target_text",
                    "style",
                    "characterization",
                    "continuity",
                ),
                source_hints=(
                    "chapter",
                    "style",
                    "character",
                    "internal_canon",
                ),
                compact_request=(
                    "Preparar únicamente el contexto necesario para "
                    "revisar el texto sin cambiar el canon."
                ),
            )

        if intent is Intent.EXTERNAL_RESEARCH:
            return OllieGuide(
                task_type="external_research",
                search_topics=("research_question", "required_scope"),
                source_hints=("external_research",),
                compact_request=(
                    "Definir con precisión qué información externa "
                    "necesita investigarse."
                ),
            )

        return OllieGuide(
            task_type="general",
            compact_request="Determinar la información mínima necesaria para continuar.",
        )
