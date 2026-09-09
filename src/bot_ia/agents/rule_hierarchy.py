"""Resolución local y auditable de reglas que compiten por el mismo asunto."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RulePriority(IntEnum):
    SECURITY_NO_INVENTION = 1
    SOURCE_AUTHORITY_CANON = 2
    UNIVERSE_PRIVACY_ISOLATION = 3
    EVIDENCE_UNCERTAINTY_CONFLICTS = 4
    EXPLICIT_USER_INSTRUCTIONS = 5
    TASK_OBJECTIVE = 6
    CONVERSATION_POLICY = 7
    IA_CHAN_PERSONALITY = 8
    STYLE_FORMAT = 9


@dataclass(frozen=True, slots=True)
class PolicyRule:
    rule_id: str
    priority: RulePriority
    subject: str
    directive: str

    def __post_init__(self) -> None:
        if not self.rule_id or not self.subject or not self.directive:
            raise ValueError("rule_id, subject and directive are required")


@dataclass(frozen=True, slots=True)
class RuleConflict:
    subject: str
    winner_rule_id: str | None
    blocked_rule_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class RuleResolution:
    effective_rules: tuple[PolicyRule, ...]
    conflicts: tuple[RuleConflict, ...]


class RuleHierarchy:
    """Una prioridad numéricamente menor vence; empates contradictorios se conservan."""

    @staticmethod
    def compare(left: RulePriority, right: RulePriority) -> int:
        """Devuelve -1 si left vence, 1 si right vence y 0 si empatan."""
        return (left > right) - (left < right)

    @classmethod
    def resolve(cls, rules: tuple[PolicyRule, ...]) -> RuleResolution:
        by_subject: dict[str, list[PolicyRule]] = {}
        for rule in rules:
            by_subject.setdefault(rule.subject, []).append(rule)
        effective: list[PolicyRule] = []
        conflicts: list[RuleConflict] = []
        for subject, candidates in by_subject.items():
            ordered = sorted(candidates, key=lambda rule: (rule.priority, rule.rule_id))
            highest_priority = ordered[0].priority
            highest = [rule for rule in ordered if rule.priority == highest_priority]
            if len({rule.directive for rule in highest}) > 1:
                conflicts.append(RuleConflict(subject, None, tuple(rule.rule_id for rule in ordered), "equal_priority_conflict"))
                continue
            winner = highest[0]
            effective.append(winner)
            blocked = tuple(rule.rule_id for rule in ordered if rule.directive != winner.directive)
            if blocked:
                conflicts.append(RuleConflict(subject, winner.rule_id, blocked, "higher_priority_rule_wins"))
        return RuleResolution(tuple(effective), tuple(conflicts))
