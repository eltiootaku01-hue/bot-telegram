"""Contrato verificable de una salida conversacional, sin E/S ni generación."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bot_ia.contracts import Confidence


class ResponseType(str, Enum):
    FACTUAL = "factual"
    DOUBT = "doubt"
    HYPOTHESIS = "hypothesis"
    IDEA = "idea"
    PROPOSAL = "proposal"
    OPINION = "opinion"
    ADVICE = "advice"
    CASUAL = "casual"
    CREATIVE = "creative"
    CLARIFICATION = "clarification"


@dataclass(frozen=True, slots=True)
class RuleCheck:
    rule_id: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ContractValidation:
    valid: bool
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IAChanOutputContract:
    """Datos mínimos para auditar una respuesta antes de mostrarla al usuario."""

    response_type: ResponseType
    answer: str
    certainty: Confidence
    interpretation: str
    used_evidence: tuple[str, ...]
    evidence_sufficient: bool
    used_memory: tuple[str, ...]
    memory_authorized: bool
    universe_id: str
    expected_universe_id: str
    needs_clarification: bool
    proposed_action: str
    uncertainty: str | None = None
    conflicts: tuple[str, ...] = ()
    rule_checks: tuple[RuleCheck, ...] = ()

    def validate(self) -> ContractValidation:
        """Comprueba invariantes; nunca añade evidencia, memoria ni autoridad."""
        issues: list[str] = []
        if not self.answer.strip():
            issues.append("answer_required")
        if not self.interpretation.strip():
            issues.append("interpretation_required")
        if not self.proposed_action.strip():
            issues.append("proposed_action_required")
        if self.universe_id != self.expected_universe_id:
            issues.append("universe_mismatch")
        if self.used_memory and not self.memory_authorized:
            issues.append("memory_not_authorized")
        if self.response_type is ResponseType.FACTUAL and not (self.evidence_sufficient and self.used_evidence):
            issues.append("factual_evidence_insufficient")
        if self.response_type is ResponseType.FACTUAL and not self.evidence_sufficient:
            if self.uncertainty is None or self.certainty not in {Confidence.LOW, Confidence.NONE}:
                issues.append("uncertainty_not_explicit")
        if self.conflicts and self.uncertainty is None:
            issues.append("conflict_not_disclosed")
        issues.extend(f"rule_check_failed:{check.rule_id}" for check in self.rule_checks if not check.passed)
        return ContractValidation(not issues, tuple(issues))
