# -*- coding: utf-8 -*-
"""Canonical Sunna V1 definition.

This module is the single normative runtime dataset for Character V1.
Only facts explicitly classified as CANON by the audited source are included.
"""

from .models import (
    CanonicalStatus,
    CanonProvenance,
    RelationshipType,
    Character,
    CharacterRelationship,
    Evolution,
    EvolutionStage,
    Identity,
    Personality,
    Repertoire,
)

_SOURCE_8 = "Se ha pegado el markdown(8).md"
_SOURCE_9 = "Se ha pegado el markdown(9).md"
_VERSION = "2026-09-15/16"

_CANON_8 = CanonProvenance(
    source_id=_SOURCE_8,
    source_version=_VERSION,
    source_section="15. ESTADO ACTUAL DEL DISEÑO / CANON",
    canonical_status=CanonicalStatus.CANON,
)
_CANON_9_PERSONALITY = CanonProvenance(
    source_id=_SOURCE_9,
    source_version=_VERSION,
    source_section="22-27. Personalidad inicial / virtudes / defectos / mayor miedo",
    canonical_status=CanonicalStatus.CANON,
)
_CANON_9_RELATIONSHIPS = CanonProvenance(
    source_id=_SOURCE_9,
    source_version=_VERSION,
    source_section="30-31. Relaciones Sunna / Cari / Cami / Chie",
    canonical_status=CanonicalStatus.CANON,
)
_CANON_9_EVOLUTION = CanonProvenance(
    source_id=_SOURCE_9,
    source_version=_VERSION,
    source_section="32. Evolución narrativa de Sunna / 20. Relación con Jörmungandr",
    canonical_status=CanonicalStatus.CANON,
)

SUNNA = Character(
    character_id="sunna",
    display_name="Sunna",
    identity=Identity(
        lineage="descendiente de Jörmungandr",
        presentation="principalmente humana / semi-furro",
        physical_traits=(
            "complexión extremadamente delgada",
            "piel muy pálida",
            "cabello largo y descuidado",
            "blunt bangs",
            "ojos dorados",
            "características serpentinas",
        ),
        provenance=_CANON_8,
    ),
    personality=Personality(
        core_traits=(
            "extremadamente silenciosa",
            "reservada",
            "insegura",
            "sensible",
            "emocional",
            "curiosa",
            "observadora",
        ),
        values=(
            "lealtad",
            "pertenencia",
        ),
        fears=(
            "perder a Cari y sus amigas",
            "volver a quedarse sola",
        ),
        strengths=(
            "adaptabilidad",
            "resistencia mental",
            "observación",
            "lealtad",
            "valentía silenciosa",
        ),
        weaknesses=(
            "baja autoestima",
            "culpa",
            "dificultad para aceptar cariño",
            "autosacrificio",
            "dificultad para reconocer su valor",
        ),
        speech_style=(
            "habla poco",
            "observa antes de participar",
            "su silencio es una defensa aprendida",
        ),
        behavioral_boundaries=(
            "silencio no equivale a frialdad",
            "introversión no equivale a indiferencia",
        ),
        provenance=_CANON_9_PERSONALITY,
    ),
    relationships=(
        CharacterRelationship(
            target_character_id="cari",
            relationship_type=RelationshipType.ACCEPTANCE,
            provenance=_CANON_9_RELATIONSHIPS,
        ),
        CharacterRelationship(
            target_character_id="cami",
            relationship_type=RelationshipType.UNDERSTANDING,
            provenance=_CANON_9_RELATIONSHIPS,
        ),
        CharacterRelationship(
            target_character_id="chie",
            relationship_type=RelationshipType.SHARED_FEAR,
            provenance=_CANON_9_RELATIONSHIPS,
        ),
    ),
    evolution=Evolution(
        initial_stage_id="dangerous",
        stages=(
            EvolutionStage(
                stage_id="dangerous",
                theme="supervivencia y miedo",
                narrative_state="Soy peligrosa.",
                provenance=_CANON_9_EVOLUTION,
            ),
            EvolutionStage(
                stage_id="acceptable",
                theme="aceptación",
                narrative_state="Quizás puedo ser aceptada.",
                provenance=_CANON_9_EVOLUTION,
            ),
            EvolutionStage(
                stage_id="rage",
                theme="rabia reconocida",
                narrative_state="También tengo derecho a sentir rabia.",
                provenance=_CANON_9_EVOLUTION,
            ),
            EvolutionStage(
                stage_id="choice",
                theme="elección sobre el dolor",
                narrative_state="Puedo elegir qué hacer con mi dolor.",
                provenance=_CANON_9_EVOLUTION,
            ),
        ),
        transitions=(
            ("dangerous", "acceptable"),
            ("acceptable", "rage"),
            ("rage", "choice"),
        ),
        provenance=_CANON_9_EVOLUTION,
    ),
    repertoire=Repertoire(),
    limits=(),
    canon_provenance=_CANON_8,
)

SUNNA.require_runtime_eligible()
