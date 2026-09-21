"""Compatibility facade for the authoritative WaifuMon progression service.

The gameplay authority lives in :mod:`app.game.progression`. This module keeps
the historical import path stable for specialized game components.
"""

from app.game.progression import (
    EVOLUTION_BANDS,
    EvolutionBand,
    EvolutionStage,
    MAX_WAIFUMON_LEVEL,
    ProgressionResult,
    CollectionStatus,
    WaifuMonStats,
    add_character_experience,
    add_collection_experience,
    combat_style_for_element,
    evolution_band_for_level,
    evolution_next_level,
    evolution_stage_for_level,
    level_cap_for_evolution_stage,
    level_floor_for_evolution_stage,
    potential_score_for_seed,
    stats_for_character,
    stats_for_collection,
)


__all__ = [
    "EVOLUTION_BANDS",
    "EvolutionBand",
    "EvolutionStage",
    "MAX_WAIFUMON_LEVEL",
    "ProgressionResult",
    "CollectionStatus",
    "WaifuMonStats",
    "add_character_experience",
    "add_collection_experience",
    "combat_style_for_element",
    "evolution_band_for_level",
    "evolution_next_level",
    "evolution_stage_for_level",
    "level_cap_for_evolution_stage",
    "level_floor_for_evolution_stage",
    "potential_score_for_seed",
    "stats_for_character",
    "stats_for_collection",
]
