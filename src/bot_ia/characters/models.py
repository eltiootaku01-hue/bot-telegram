# -*- coding: utf-8 -*-
"""Minimal immutable Character V1 domain contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CanonicalStatus(str, Enum):
    CANON = "CANON"
    DEVELOPMENTAL = "DEVELOPMENTAL"
    DISCARDED_REPLACED = "DISCARDED_REPLACED"
    UNKNOWN = "UNKNOWN"

    @property
    def runtime_eligible(self) -> bool:
        return self is CanonicalStatus.CANON


@dataclass(frozen=True, slots=True)
class CanonProvenance:
    source_id: str
    source_version: str
    source_section: str
    canonical_status: CanonicalStatus

    def __post_init__(self) -> None:
        for value, name in (
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.source_section, "source_section"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")

    def require_runtime(self) -> None:
        if not self.canonical_status.runtime_eligible:
            raise ValueError(
                f"canonical status {self.canonical_status.value} is not runtime eligible"
            )


@dataclass(frozen=True, slots=True)
class Identity:
    lineage: str
    presentation: str
    physical_traits: tuple[str, ...]
    provenance: CanonProvenance

    def __post_init__(self) -> None:
        _require_text(self.lineage, "identity lineage")
        _require_text(self.presentation, "identity presentation")
        _require_nonempty_tuple(self.physical_traits, "identity physical_traits")
        self.provenance.require_runtime()


@dataclass(frozen=True, slots=True)
class Personality:
    core_traits: tuple[str, ...]
    values: tuple[str, ...]
    fears: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    speech_style: tuple[str, ...]
    behavioral_boundaries: tuple[str, ...]
    provenance: CanonProvenance

    def __post_init__(self) -> None:
        for value, name in (
            (self.core_traits, "core_traits"),
            (self.values, "values"),
            (self.fears, "fears"),
            (self.strengths, "strengths"),
            (self.weaknesses, "weaknesses"),
            (self.speech_style, "speech_style"),
            (self.behavioral_boundaries, "behavioral_boundaries"),
        ):
            _require_nonempty_tuple(value, name)
        self.provenance.require_runtime()


@dataclass(frozen=True, slots=True)
class CharacterRelationship:
    target_character_id: str
    documented_relation: str
    provenance: CanonProvenance

    def __post_init__(self) -> None:
        _require_text(self.target_character_id, "relationship target_character_id")
        _require_text(self.documented_relation, "documented_relation")
        self.provenance.require_runtime()


@dataclass(frozen=True, slots=True)
class EvolutionStage:
    stage_id: str
    theme: str
    narrative_state: str
    provenance: CanonProvenance

    def __post_init__(self) -> None:
        _require_text(self.stage_id, "stage_id")
        _require_text(self.theme, "stage theme")
        _require_text(self.narrative_state, "narrative_state")
        self.provenance.require_runtime()


@dataclass(frozen=True, slots=True)
class Evolution:
    initial_stage_id: str
    stages: tuple[EvolutionStage, ...]
    transitions: tuple[tuple[str, str], ...]
    provenance: CanonProvenance

    def __post_init__(self) -> None:
        self.provenance.require_runtime()
        if not self.stages:
            raise ValueError("evolution requires stages")
        stage_ids = {stage.stage_id for stage in self.stages}
        if len(stage_ids) != len(self.stages):
            raise ValueError("evolution stage ids must be unique")
        if self.initial_stage_id not in stage_ids:
            raise ValueError("initial evolution stage must exist")
        for source_id, target_id in self.transitions:
            if source_id not in stage_ids or target_id not in stage_ids:
                raise ValueError("evolution transition references unknown stage")
        if len(set(self.transitions)) != len(self.transitions):
            raise ValueError("evolution transitions must be unique")


@dataclass(frozen=True, slots=True)
class RepertoireEntry:
    entry_id: str
    content: str
    provenance: CanonProvenance

    def __post_init__(self) -> None:
        _require_text(self.entry_id, "repertoire entry_id")
        _require_text(self.content, "repertoire content")
        self.provenance.require_runtime()


@dataclass(frozen=True, slots=True)
class Repertoire:
    entries: tuple[RepertoireEntry, ...] = ()

    def __post_init__(self) -> None:
        entry_ids = [entry.entry_id for entry in self.entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("repertoire entry ids must be unique")


@dataclass(frozen=True, slots=True)
class CharacterLimit:
    subject: str
    constraint: str
    provenance: CanonProvenance

    def __post_init__(self) -> None:
        _require_text(self.subject, "limit subject")
        _require_text(self.constraint, "limit constraint")
        self.provenance.require_runtime()


@dataclass(frozen=True, slots=True)
class Character:
    character_id: str
    display_name: str
    identity: Identity
    personality: Personality
    relationships: tuple[CharacterRelationship, ...]
    evolution: Evolution
    repertoire: Repertoire
    limits: tuple[CharacterLimit, ...]
    canon_provenance: CanonProvenance

    def __post_init__(self) -> None:
        _require_identifier(self.character_id, "character_id")
        _require_text(self.display_name, "display_name")
        self.canon_provenance.require_runtime()

        nested = [
            self.identity.provenance,
            self.personality.provenance,
            self.evolution.provenance,
            *(item.provenance for item in self.relationships),
            *(item.provenance for item in self.repertoire.entries),
            *(item.provenance for item in self.limits),
            *(stage.provenance for stage in self.evolution.stages),
        ]
        for provenance in nested:
            provenance.require_runtime()

        relationship_targets = [
            item.target_character_id for item in self.relationships
        ]
        if len(set(relationship_targets)) != len(relationship_targets):
            raise ValueError("character relationship targets must be unique")

    def require_runtime_eligible(self) -> None:
        self.canon_provenance.require_runtime()
        self.identity.provenance.require_runtime()
        self.personality.provenance.require_runtime()
        self.evolution.provenance.require_runtime()
        for relationship in self.relationships:
            relationship.provenance.require_runtime()
        for entry in self.repertoire.entries:
            entry.provenance.require_runtime()
        for limit in self.limits:
            limit.provenance.require_runtime()
        for stage in self.evolution.stages:
            stage.provenance.require_runtime()


def _require_identifier(value: str, name: str) -> None:
    _require_text(value, name)
    if any(character.isspace() for character in value):
        raise ValueError(f"{name} cannot contain whitespace")


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _require_nonempty_tuple(value: tuple[str, ...], name: str) -> None:
    if not value or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must contain non-empty strings")
