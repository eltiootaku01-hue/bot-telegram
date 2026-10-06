# -*- coding: utf-8 -*-
"""Focused tests for the isolated CAFE-01 domain foundation."""

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bot_ia.cafe import (
    CafeDomainEvent,
    CafeDomainEventType,
    CafeDomainIdentity,
    CharacterRef,
    CharacterState,
    RelationshipState,
    RelationshipStatus,
)
from bot_ia.characters import SUNNA


UTC_NOW = datetime.now(timezone.utc)


def test_public_exports_are_limited_to_frozen_foundation() -> None:
    import bot_ia.cafe as cafe

    assert set(cafe.__all__) == {
        "CafeDomainEvent",
        "CafeDomainEventType",
        "CafeDomainIdentity",
        "CharacterRef",
        "CharacterState",
        "RelationshipState",
        "RelationshipStatus",
    }
    assert not hasattr(cafe, "AuthorityCore")
    assert not hasattr(cafe, "WaifuRegistry")
    assert not hasattr(cafe, "MemoryStore")
    assert not hasattr(cafe, "TelegramEventLedger")


def test_cafe_domain_identity_accepts_valid_id_and_actor_refs() -> None:
    identity = CafeDomainIdentity(
        identity_id="cafe-user-1",
        actor_keys=("telegram:123", "discord:456"),
        created_at=UTC_NOW,
        updated_at=UTC_NOW,
    )

    assert identity.identity_id == "cafe-user-1"
    assert identity.actor_keys == ("telegram:123", "discord:456")
    assert isinstance(identity.actor_keys, tuple)


@pytest.mark.parametrize("value", ["", "   "])
def test_cafe_domain_identity_rejects_empty_id(value: str) -> None:
    with pytest.raises(ValueError, match="identity_id"):
        CafeDomainIdentity(value, ("telegram:123",), UTC_NOW, UTC_NOW)


def test_cafe_domain_identity_rejects_mutable_actor_keys() -> None:
    with pytest.raises(TypeError, match="immutable tuple"):
        CafeDomainIdentity(
            "cafe-user-1",
            ["telegram:123"],  # type: ignore[arg-type]
            UTC_NOW,
            UTC_NOW,
        )


def test_cafe_domain_identity_rejects_duplicate_actor_refs() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        CafeDomainIdentity(
            "cafe-user-1",
            ("telegram:123", "telegram:123"),
            UTC_NOW,
            UTC_NOW,
        )


def test_cafe_domain_identity_has_no_platform_authority_api() -> None:
    public_names = set(dir(CafeDomainIdentity))
    assert {
        "authenticate",
        "authorize",
        "parse_credentials",
        "link_platforms",
    }.isdisjoint(public_names)


def test_character_ref_is_identifier_only() -> None:
    reference = CharacterRef("sunna")

    assert reference.character_id == "sunna"
    assert [field.name for field in fields(reference)] == ["character_id"]


@pytest.mark.parametrize("value", ["", "   ", None, 7])
def test_character_ref_rejects_invalid_ids(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        CharacterRef(value)  # type: ignore[arg-type]


def test_character_ref_contains_no_character_v1_copy() -> None:
    field_names = {field.name for field in fields(CharacterRef)}
    assert field_names == {"character_id"}
    assert not {
        "identity",
        "personality",
        "relationships",
        "evolution",
        "repertoire",
        "limits",
        "canon_provenance",
    } & field_names


def test_character_state_is_immutable_and_typed() -> None:
    state = CharacterState(
        character_ref=CharacterRef("sunna"),
        evolution_stage_id="dangerous",
        state_version=1,
        updated_at=UTC_NOW,
    )

    assert state.character_ref == CharacterRef("sunna")
    assert state.evolution_stage_id == "dangerous"
    assert state.state_version == 1

    with pytest.raises(FrozenInstanceError):
        state.state_version = 2


def test_character_state_allows_optional_evolution_stage() -> None:
    state = CharacterState(
        character_ref=CharacterRef("sunna"),
        evolution_stage_id=None,
        state_version=1,
        updated_at=UTC_NOW,
    )
    assert state.evolution_stage_id is None


def test_character_state_rejects_invalid_versions() -> None:
    with pytest.raises(ValueError):
        CharacterState(CharacterRef("sunna"), None, 0, UTC_NOW)

    with pytest.raises(TypeError):
        CharacterState(
            CharacterRef("sunna"),
            None,
            True,  # type: ignore[arg-type]
            UTC_NOW,
        )


def test_character_state_has_no_forbidden_state_fields() -> None:
    field_names = {field.name for field in fields(CharacterState)}
    assert field_names == {
        "character_ref",
        "evolution_stage_id",
        "state_version",
        "updated_at",
    }
    assert not {
        "canon",
        "personality",
        "relationships",
        "busy",
        "resting",
        "waitress_session",
        "browser",
        "webchat",
        "physical_resource",
        "cafe_session",
        "presence",
        "payload",
        "data",
    } & field_names


def test_relationship_state_is_immutable_and_typed() -> None:
    relationship = RelationshipState(
        domain_identity_id="cafe-user-1",
        character_ref=CharacterRef("sunna"),
        status=RelationshipStatus.ACTIVE,
        started_at=UTC_NOW,
        updated_at=UTC_NOW,
    )

    assert relationship.domain_identity_id == "cafe-user-1"
    assert relationship.character_ref == CharacterRef("sunna")
    assert relationship.status is RelationshipStatus.ACTIVE

    with pytest.raises(FrozenInstanceError):
        relationship.status = RelationshipStatus.INACTIVE


def test_relationship_state_rejects_arbitrary_status_strings() -> None:
    with pytest.raises(TypeError, match="RelationshipStatus"):
        RelationshipState(
            "cafe-user-1",
            CharacterRef("sunna"),
            "active",  # type: ignore[arg-type]
            UTC_NOW,
            UTC_NOW,
        )


def test_relationship_state_has_no_affinity_fields() -> None:
    field_names = {field.name for field in fields(RelationshipState)}
    assert field_names == {
        "domain_identity_id",
        "character_ref",
        "status",
        "started_at",
        "updated_at",
    }
    assert not {
        "heart_level",
        "affinity_score",
        "gacha_modifier",
        "waitress_affinity",
    } & field_names


def test_cafe_domain_event_is_immutable_and_typed() -> None:
    event = CafeDomainEvent(
        event_id="evt-1",
        event_type=CafeDomainEventType.CHARACTER_STATE_CHANGED,
        occurred_at=UTC_NOW,
        domain_identity_id="cafe-user-1",
        character_ref=CharacterRef("sunna"),
        correlation_id="corr-1",
    )

    assert event.event_id == "evt-1"
    assert event.event_type is CafeDomainEventType.CHARACTER_STATE_CHANGED

    with pytest.raises(FrozenInstanceError):
        event.event_id = "evt-2"


def test_cafe_domain_event_accepts_optional_typed_references() -> None:
    event = CafeDomainEvent(
        "evt-2",
        CafeDomainEventType.RELATIONSHIP_STATE_CHANGED,
        UTC_NOW,
        None,
        None,
        None,
    )
    assert event.domain_identity_id is None
    assert event.character_ref is None


def test_cafe_domain_event_rejects_arbitrary_event_types() -> None:
    with pytest.raises(TypeError, match="CafeDomainEventType"):
        CafeDomainEvent(
            "evt-3",
            "relationship_created",  # type: ignore[arg-type]
            UTC_NOW,
            None,
            None,
            None,
        )


def test_cafe_domain_event_has_no_generic_payload_or_runtime_behavior() -> None:
    field_names = {field.name for field in fields(CafeDomainEvent)}
    assert field_names == {
        "event_id",
        "event_type",
        "occurred_at",
        "domain_identity_id",
        "character_ref",
        "correlation_id",
    }
    public_names = set(dir(CafeDomainEvent))
    assert {
        "dispatch",
        "publish",
        "schedule",
        "retry",
        "handle",
        "emit",
    }.isdisjoint(public_names)


def test_event_name_is_distinct_from_world_cafe_event() -> None:
    assert CafeDomainEvent.__name__ == "CafeDomainEvent"
    assert CafeDomainEvent.__name__ != "CafeEvent"


def test_cafe_module_has_no_forbidden_productive_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "bot_ia" / "cafe"
    forbidden_tokens = (
        "AuthorityCore",
        "AuthenticatedTelegramActor",
        "TelegramEventLedger",
        "WaifuRegistry",
        "WaitressSessionManager",
        "MemoryStore",
        "PhysicalResourceAuthority",
        "QWebEngine",
        "Playwright",
    )

    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden_tokens), path


def test_cafe_foundation_references_sunna_without_mutating_or_cloning() -> None:
    before = repr(SUNNA)
    reference = CharacterRef(SUNNA.character_id)
    state = CharacterState(reference, None, 1, UTC_NOW)

    assert state.character_ref.character_id == SUNNA.character_id
    assert repr(SUNNA) == before


def test_closed_enum_members_are_exactly_the_frozen_minimum() -> None:
    assert set(RelationshipStatus) == {
        RelationshipStatus.ACTIVE,
        RelationshipStatus.INACTIVE,
    }
    assert set(CafeDomainEventType) == {
        CafeDomainEventType.CHARACTER_STATE_CHANGED,
        CafeDomainEventType.RELATIONSHIP_STATE_CHANGED,
    }
