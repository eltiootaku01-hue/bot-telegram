# -*- coding: utf-8 -*-
"""Focused tests for Character V1 and the Sunna projection."""

from dataclasses import FrozenInstanceError, replace

import pytest

from bot_ia.characters import (
    CanonicalStatus,
    CanonProvenance,
    Character,
    CharacterRelationship,
    RelationshipType,
    Identity,
    Personality,
    SUNNA,
    project_character_to_waitress_profile,
    resolve_character_for_waitress,
)


def test_sunna_is_canonical_and_contains_no_developmental_details() -> None:
    assert SUNNA.canon_provenance.canonical_status is CanonicalStatus.CANON
    assert SUNNA.identity.provenance.canonical_status is CanonicalStatus.CANON
    assert SUNNA.personality.provenance.canonical_status is CanonicalStatus.CANON
    assert SUNNA.repertoire.entries == ()
    assert SUNNA.limits == ()

    all_text = repr(SUNNA)
    assert "color natural definitivo del cabello" not in all_text
    assert "distribución de las escamas" not in all_text
    assert "cabello blanco" not in all_text


def test_non_canon_character_data_is_rejected_before_runtime() -> None:
    developmental = CanonProvenance(
        source_id="test",
        source_version="1",
        source_section="developmental",
        canonical_status=CanonicalStatus.DEVELOPMENTAL,
    )
    with pytest.raises(ValueError, match="not runtime eligible"):
        Character(
            character_id="invalid",
            display_name="Invalid",
            identity=Identity(
                lineage="unknown",
                presentation="unknown",
                physical_traits=("unknown",),
                provenance=developmental,
            ),
            personality=SUNNA.personality,
            relationships=(),
            evolution=SUNNA.evolution,
            repertoire=SUNNA.repertoire,
            limits=(),
            canon_provenance=SUNNA.canon_provenance,
        )


def test_discarded_and_unknown_statuses_are_not_runtime_eligible() -> None:
    assert not CanonicalStatus.DEVELOPMENTAL.runtime_eligible
    assert not CanonicalStatus.DISCARDED_REPLACED.runtime_eligible
    assert not CanonicalStatus.UNKNOWN.runtime_eligible
    assert CanonicalStatus.CANON.runtime_eligible


def test_character_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        SUNNA.display_name = "changed"


def test_relationships_are_character_to_character() -> None:
    targets = {item.target_character_id for item in SUNNA.relationships}
    assert targets == {"cari", "cami", "chie"}
    assert {item.relationship_type for item in SUNNA.relationships} == {
        RelationshipType.ACCEPTANCE,
        RelationshipType.UNDERSTANDING,
        RelationshipType.SHARED_FEAR,
    }
    assert all(item.provenance.canonical_status is CanonicalStatus.CANON for item in SUNNA.relationships)


def test_narrative_evolution_is_independent_of_tcg_or_affinity() -> None:
    assert SUNNA.evolution.initial_stage_id == "dangerous"
    assert tuple(stage.stage_id for stage in SUNNA.evolution.stages) == (
        "dangerous",
        "acceptable",
        "rage",
        "choice",
    )
    assert SUNNA.evolution.transitions == (
        ("dangerous", "acceptable"),
        ("acceptable", "rage"),
        ("rage", "choice"),
    )
    assert not hasattr(SUNNA.evolution, "xp")
    assert not hasattr(SUNNA.evolution, "affinity")


def test_sunna_resolves_through_explicit_waitress_mapping() -> None:
    assert resolve_character_for_waitress("sunna") is SUNNA
    assert resolve_character_for_waitress("SUNNA") is SUNNA
    assert resolve_character_for_waitress("cari") is None


def test_character_projects_to_existing_waitress_prompt_profile() -> None:
    profile = project_character_to_waitress_profile(
        SUNNA,
        waitress_id="sunna",
        display_name="Sunna",
        role="novice",
    )

    assert profile.waitress_id == "sunna"
    assert profile.display_name == "Sunna"
    assert profile.role == "novice"
    assert "Identidad canónica: Sunna." in profile.personality_prompt
    assert "extremadamente silenciosa" in profile.personality_prompt
    assert "silencio no equivale a frialdad" in profile.personality_prompt


def test_projection_does_not_mutate_character() -> None:
    before = repr(SUNNA)
    project_character_to_waitress_profile(
        SUNNA,
        waitress_id="sunna",
        display_name="Sunna",
        role="novice",
    )
    assert repr(SUNNA) == before


def test_projection_rejects_unmapped_waitress() -> None:
    with pytest.raises(ValueError, match="explicitly associated"):
        project_character_to_waitress_profile(
            SUNNA,
            waitress_id="cari",
            display_name="Cari",
            role="novice",
        )


def test_projection_does_not_use_waifu_affinity_or_session_state() -> None:
    profile = project_character_to_waitress_profile(
        SUNNA,
        waitress_id="sunna",
        display_name="Sunna",
        role="novice",
    )
    assert "heart" not in profile.personality_prompt.casefold()
    assert "xp" not in profile.personality_prompt.casefold()
    assert "session" not in profile.personality_prompt.casefold()
