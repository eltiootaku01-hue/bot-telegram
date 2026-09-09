"""Adaptadores deterministas: interpretan expedientes, no generan ni recuperan datos."""

from __future__ import annotations

from bot_ia.librarian.models import SourceType

from .base import BaseAgent
from .conversation_policy import ConversationGuidance, ConversationPolicy
from .models import AgentFinding, AgentRequest, AgentResult, AgentStatus
from .output_contract import IAChanOutputContract, ResponseType, RuleCheck


class IAChanAgent(BaseAgent):
    AGENT_ID = "ia_chan"
    def __init__(self, policy: ConversationPolicy | None = None) -> None:
        self._policy = policy or ConversationPolicy()

    def run(self, request: AgentRequest) -> AgentResult:
        error = self.validate(request)
        if error:
            return self.rejected(error)
        sources = tuple(item.source_id for item in request.context_pack.selections if item.source_id is not None)
        guidance = self._policy.assess(request.user_request)
        contract = self._output_contract(request, guidance)
        findings = (AgentFinding("context_received", f"{len(request.context_pack.selections)} selected items", sources), AgentFinding("constraints", ", ".join(request.constraints) or "none"), AgentFinding("conversation_policy", f"{guidance.act.value}; {guidance.epistemic_label}; {guidance.response_mode}"), AgentFinding("output_contract", "valid" if contract.validate().valid else "requires_review"))
        return AgentResult(self.AGENT_ID, AgentStatus.COMPLETE, contract.answer, findings, sources, contract.uncertainty, contract.conflicts, "Use this brief for a future conversational or creative provider call.", contract)

    @staticmethod
    def _output_contract(request: AgentRequest, guidance: ConversationGuidance) -> IAChanOutputContract:
        evidence = tuple(item.source_id for item in request.context_pack.selections if item.kind == "evidence" and item.source_id is not None)
        memory = tuple(item.source_id for item in request.context_pack.selections if item.kind == "memory" and item.source_id is not None)
        memory_authorized = all(item.reason == "authorized relevant memory" for item in request.context_pack.selections if item.kind == "memory")
        conflicts = tuple(conflict.conflict_key for conflict in request.evidence_pack.conflicts)
        response_type = {
            "fact": ResponseType.FACTUAL,
            "doubt": ResponseType.DOUBT,
            "hypothesis": ResponseType.HYPOTHESIS,
            "idea": ResponseType.IDEA,
            "proposal": ResponseType.PROPOSAL,
            "opinion": ResponseType.OPINION,
            "advice": ResponseType.ADVICE,
            "subjective": ResponseType.OPINION,
            "casual": ResponseType.CASUAL,
            "creative": ResponseType.CREATIVE,
            "clarification": ResponseType.CLARIFICATION,
        }[guidance.act.value]
        uncertainty = "conflict" if conflicts else ("context_insufficient" if not request.context_pack.sufficient else None)
        checks = (
            RuleCheck("security_no_invention", response_type is not ResponseType.FACTUAL or bool(evidence), "factual claims require supplied evidence"),
            RuleCheck("universe_isolation", request.context_pack.universe_id == request.universe_id and request.evidence_pack.query.universe_id == request.universe_id, "all supplied material shares the request universe"),
            RuleCheck("memory_authorization", not memory or memory_authorized, "memory selections must be authorized"),
            RuleCheck("conflict_disclosure", not conflicts or uncertainty is not None, "conflicts remain visible"),
        )
        return IAChanOutputContract(response_type, "IA-chan received the prepared coauthoring brief; no provider was invoked.", request.context_pack.confidence, f"{guidance.act.value}; {guidance.epistemic_label}; {guidance.response_mode}", evidence, request.context_pack.sufficient and bool(evidence), memory, memory_authorized, request.context_pack.universe_id, request.universe_id, guidance.requires_clarification, guidance.response_mode, uncertainty, conflicts, checks)


class HistorianAgent(BaseAgent):
    AGENT_ID = "historian"

    def run(self, request: AgentRequest) -> AgentResult:
        error = self.validate(request)
        if error:
            return self.rejected(error)
        shown, planned, unknown = [], [], []
        for ranked in request.evidence_pack.sources:
            source_id, source_type = ranked.entry.record.source_id, ranked.entry.metadata.source_type
            if source_type in {SourceType.PLANNING, SourceType.OUTLINE}:
                planned.append(source_id)
            elif ranked.epistemic.value == "established":
                shown.append(source_id)
            else:
                unknown.append(source_id)
        findings = (AgentFinding("confirmed", ", ".join(shown) or "none", tuple(shown)), AgentFinding("planning", ", ".join(planned) or "none", tuple(planned)), AgentFinding("unknown", ", ".join(unknown) or "none", tuple(unknown)))
        conflicts = tuple(conflict.conflict_key for conflict in request.evidence_pack.conflicts)
        status = AgentStatus.INSUFFICIENT_EVIDENCE if not shown and not planned else AgentStatus.COMPLETE
        answer = "Continuity report preserves confirmed, planned, unknown, and conflicting material without conversion."
        uncertainty = "conflict" if conflicts else ("no_confirmed_fact" if not shown else None)
        return AgentResult(self.AGENT_ID, status, answer, findings, tuple(shown + planned + unknown), uncertainty, conflicts, "Resolve conflicts with additional internal evidence; planning remains non-factual.")


class EditorAgent(BaseAgent):
    AGENT_ID = "editor"

    def run(self, request: AgentRequest) -> AgentResult:
        error = self.validate(request)
        if error:
            return self.rejected(error)
        constraints = request.constraints or ("preserve evidence and avoid automatic rewrites",)
        findings = tuple(AgentFinding("editorial_constraint", constraint) for constraint in constraints)
        return AgentResult(self.AGENT_ID, AgentStatus.COMPLETE, "Editorial brief prepared; no rewrite or canon change was applied.", findings, (), None, (), "Review POV, tense, style, dialogue, rhythm, physical coherence, and emotion only when evidence supports it.")


class ResearcherAgent(BaseAgent):
    AGENT_ID = "researcher"

    def run(self, request: AgentRequest) -> AgentResult:
        error = self.validate(request)
        if error:
            return self.rejected(error)
        findings = tuple(AgentFinding("external_reference", f"{reference.source} | {reference.medium} | {reference.version}") for reference in request.external_references)
        return AgentResult(self.AGENT_ID, AgentStatus.COMPLETE, "External references recorded separately; they do not establish internal canon.", findings, (), "external_references_not_canon", (), "Validate applicability against internal evidence before use.")
