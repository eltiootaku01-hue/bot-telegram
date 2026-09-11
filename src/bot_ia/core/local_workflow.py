"""Flujo local inyectable que une evidencia, contexto, IA-chan y reglas."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Mapping

from bot_ia.agents import AgentRegistry, AgentRequest, AgentResult, PolicyRule, ResponseType, RuleCheck, RuleHierarchy, RulePriority, RuleResolution
from bot_ia.context import ContextBuilder, ContextPack, TokenBudget
from bot_ia.config import ProviderConfig
from bot_ia.contracts import Confidence, UniverseDefinition
from bot_ia.librarian import EntityIndex, LocalLibrarian, RetrievalQuery
from bot_ia.librarian.models import CatalogEntry, Coverage, CoverageStatus, EvidencePack
from bot_ia.memory import MemoryStore
from bot_ia.providers import ProviderManager, ProviderRequest, ProviderResponse, ProviderStatus

from .application import ApplicationRequest
from .evidence_gate import EvidenceGate
from .external_policy import wrap_external_proposal
from .local_response import build_local_response
from .models import BrainResult, RouteDecision
from .ollie import OllieGuideBuilder

RuleFactory = Callable[[BrainResult, RouteDecision], tuple[PolicyRule, ...]]


@dataclass(frozen=True, slots=True)
class LocalExecution:
    text: str
    searched: bool
    evidence: EvidencePack
    context: ContextPack
    agent_result: AgentResult
    rule_resolution: RuleResolution
    provider_response: ProviderResponse | None


class LocalWorkflow:
    """Orquesta sólo dependencias locales o inyectadas; nunca carga credenciales."""

    def __init__(
        self,
        entries_by_universe: Mapping[str, tuple[CatalogEntry, ...]],
        *,
        entity_indexes: Mapping[str, EntityIndex] | None = None,
        librarian: LocalLibrarian | None = None,
        context_builder: ContextBuilder | None = None,
        agents: AgentRegistry | None = None,
        memory_store: MemoryStore | None = None,
        provider_manager: ProviderManager | None = None,
        token_budget: TokenBudget | None = None,
        rule_factory: RuleFactory | None = None,
        provider_config: ProviderConfig | None = None,
        provider_id: str = "local_fake",
        provider_model: str = "local-v1",
        fallback_provider: str | None = None,
    ) -> None:
        self._entries = dict(entries_by_universe)
        self._entity_indexes = dict(entity_indexes or {})
        self._librarian = librarian or LocalLibrarian()
        self._context_builder = context_builder or ContextBuilder()
        self._agents = agents or AgentRegistry()
        self._memory_store = memory_store
        self._provider_manager = provider_manager
        self._budget = token_budget or TokenBudget(256)
        self._rule_factory = rule_factory or self._default_rules
        self._ollie = OllieGuideBuilder()
        self._evidence_gate = EvidenceGate()
        self._provider_config = provider_config or ProviderConfig(provider_id=provider_id, model=provider_model, fallback_provider=fallback_provider)
        self._response_cache: dict[tuple[str, str, str, str, str, str, str, str], ProviderResponse] = {}
        self._response_cache_limit = 64

    def register_universe(self, definition: UniverseDefinition, entries: tuple[CatalogEntry, ...]) -> None:
        """Añade una biblioteca nueva sin mezclarla con las existentes."""
        if definition.universe_id in self._entries:
            raise ValueError(f"universe already registered in workflow: {definition.universe_id}")
        self._entries[definition.universe_id] = entries
        self._entity_indexes[definition.universe_id] = EntityIndex(entries)

    def execute(self, request: ApplicationRequest, brain: BrainResult, decision: RouteDecision) -> LocalExecution:
        if brain.universe_id is None:
            raise ValueError("local workflow requires a resolved universe")

        preferred_source_ids = self._preferred_sources(brain)
        query = RetrievalQuery(brain.normalized.original, brain.universe_id, preferred_source_ids=preferred_source_ids)
        searched = decision.requires_search or decision.requires_agent or decision.requires_llm
        evidence = self._librarian.retrieve(query, self._entries.get(brain.universe_id, ())) if searched else self._empty_evidence(query)
        rules = self._rule_factory(brain, decision)
        resolution = RuleHierarchy.resolve(rules)
        critical_rules = tuple(f"{rule.rule_id}: {rule.subject} -> {rule.directive}" for rule in rules if rule.priority <= RulePriority.EVIDENCE_UNCERTAINTY_CONFLICTS)
        memory_matches = ()
        if self._memory_store is not None:
            memory_matches = self._memory_store.retrieve(universe_id=brain.universe_id, user_id=request.user_id, conversation_id=request.conversation_id, query=brain.normalized.original)
        context = self._context_builder.build(evidence, self._budget, critical_rules=critical_rules, memory_matches=memory_matches, future_task=decision.requires_llm)
        ollie = self._ollie.build(brain.intent)
        agent_id = decision.agent_id or self._agents.agent_for_intent(brain.intent) or "ia_chan"
        agent = self._agents.dispatch(AgentRequest(agent_id, brain.universe_id, brain.intent.value, brain.normalized.original, brain.state, context, evidence, constraints=(ollie.compact_request,) if ollie.compact_request else ()))
        contract = agent.output_contract
        if contract is not None:
            hierarchy_ok = not any(conflict.winner_rule_id is None for conflict in resolution.conflicts)
            contract = replace(contract, rule_checks=(*contract.rule_checks, RuleCheck("rule_hierarchy", hierarchy_ok, "conflicts are retained in the execution trace")))
            agent = replace(agent, output_contract=contract)
        provider_response = self._run_local_provider(decision, brain, agent, context)
        if decision.external_api_authorized and provider_response is not None and provider_response.status is ProviderStatus.SUCCESS and provider_response.output_text:
            external_text = wrap_external_proposal(provider_response.output_text)
            if contract is not None:
                contract = replace(contract, response_type=ResponseType.PROPOSAL, answer=external_text, evidence_sufficient=False, certainty=Confidence.LOW, uncertainty="external_api_unverified", proposed_action="review_before_library_incorporation")
                agent = replace(agent, answer=external_text, output_contract=contract)
            else:
                agent = replace(agent, answer=external_text)
        elif decision.requires_search:
            gated_text = self._evidence_gate.build_factual_answer(evidence)
            if contract is not None:
                contract = replace(contract, answer=gated_text)
                agent = replace(agent, answer=gated_text, output_contract=contract)
            else:
                agent = replace(agent, answer=gated_text)
        elif provider_response is not None and provider_response.status is ProviderStatus.SUCCESS and provider_response.output_text:
            if contract is not None:
                contract = replace(contract, answer=provider_response.output_text)
                agent = replace(agent, answer=provider_response.output_text, output_contract=contract)
            else:
                agent = replace(agent, answer=provider_response.output_text)
        else:
            source_names = tuple(entry.record.path.rsplit("/", 1)[-1] for entry in self._entries.get(brain.universe_id, ()))
            local_text = build_local_response(brain.intent, brain.normalized.original, self._universe_display_name(brain.universe_id), source_names)
            if local_text:
                if contract is not None:
                    contract = replace(contract, answer=local_text)
                    agent = replace(agent, answer=local_text, output_contract=contract)
                else:
                    agent = replace(agent, answer=local_text)
        if contract is not None:
            validation = contract.validate()
            if not validation.valid:
                safe_answer = "No puedo presentar esta salida porque no superó las comprobaciones de seguridad del expediente."
                contract = replace(contract, response_type=ResponseType.DOUBT, answer=safe_answer, certainty=Confidence.LOW, evidence_sufficient=False, needs_clarification=True, proposed_action="clarification", uncertainty="contract_validation_failed", rule_checks=(*contract.rule_checks, RuleCheck("output_contract", False, "; ".join(validation.issues))))
                agent = replace(agent, answer=safe_answer, output_contract=contract)
        text = "Necesito una aclaración para continuar." if contract is not None and contract.needs_clarification else agent.answer
        return LocalExecution(text, searched, evidence, context, agent, resolution, provider_response)

    def _run_local_provider(self, decision: RouteDecision, brain: BrainResult, agent: AgentResult, context: ContextPack) -> ProviderResponse | None:
        if self._provider_manager is None or not decision.requires_llm:
            return None
        config = self._provider_config
        context_key = context.text or "(no local context available)"
        agent_policy_key = f"{agent.recommendation}|{agent.uncertainty or ''}|{';'.join(agent.conflicts)}"
        cache_key = (
            config.provider_id,
            config.model,
            brain.universe_id,
            agent.agent_id,
            brain.intent.value,
            str(decision.external_api_authorized),
            brain.normalized.normalized,
            f"{context_key}\nPOLICY:{agent_policy_key}",
        )
        cached = self._response_cache.get(cache_key)
        if cached is not None:
            return replace(cached, request_id=f"cache:{cached.request_id}")
        external_instructions = ("This is an explicitly authorized external research call. Treat your output as unverified research material, not as project canon or library truth. Do not claim that your answer has been incorporated into the project. Clearly flag uncertainty or disputed facts.\n" if decision.external_api_authorized else "")
        provider_input = (
            f"You are acting as the {agent.agent_id} agent inside BOT-IA.\n"
            f"Agent guidance: {agent.recommendation}\n"
            "Answer naturally and directly in Spanish unless the user requests otherwise.\n"
            "Do not mention internal routing or provider mechanics unless asked.\n"
            "Use the supplied project context as the source of truth.\n"
            "Never invent established project facts; label inference, uncertainty, and new creative proposals clearly.\n"
            "If the request is creative, you may create new material, but do not silently turn it into canon.\n"
            + external_instructions
            + "\n"
            + f"UNIVERSE: {brain.universe_id}\n"
            + f"INTENT: {brain.intent.value}\n\n"
            + f"CONTEXT:\n{context_key}\n\n"
            + f"USER REQUEST:\n{brain.normalized.original}"
        )
        provider_request = ProviderRequest(config.provider_id, config.model, provider_input, config.max_output_tokens, config.timeout_seconds, f"{config.provider_id}:{agent.agent_id}:{brain.normalized.normalized}", decision.reason)
        response = self._provider_manager.execute(decision, provider_request, fallback_provider=config.fallback_provider).response
        if response.status is ProviderStatus.SUCCESS and response.output_text:
            if len(self._response_cache) >= self._response_cache_limit:
                self._response_cache.pop(next(iter(self._response_cache)))
            self._response_cache[cache_key] = response
        return response

    def _universe_display_name(self, universe_id: str) -> str | None:
        return universe_id

    def _preferred_sources(self, brain: BrainResult) -> tuple[str, ...]:
        if brain.universe_id is None:
            return ()
        index = self._entity_indexes.get(brain.universe_id)
        if index is None:
            return ()
        source_ids: list[str] = []
        seen: set[str] = set()
        for reference in brain.references:
            entity_id = reference.resolved_entity_id
            if entity_id is None or reference.clarification_needed:
                continue
            for entry in index.entries_for(entity_id):
                source_id = entry.record.source_id
                if source_id in seen:
                    continue
                source_ids.append(source_id)
                seen.add(source_id)
        return tuple(source_ids)

    @staticmethod
    def _empty_evidence(query: RetrievalQuery) -> EvidencePack:
        return EvidencePack(query, (), (), (), (), ("search_not_required",), Confidence.NONE, (), Coverage(CoverageStatus.NO_ENCONTRADO, 0, 0, 0))

    @staticmethod
    def _default_rules(brain: BrainResult, decision: RouteDecision) -> tuple[PolicyRule, ...]:
        return (PolicyRule("security_no_invention", RulePriority.SECURITY_NO_INVENTION, "factual_output", "evidence_required"), PolicyRule("conversation_policy", RulePriority.CONVERSATION_POLICY, "response_mode", decision.route.value))


def agent_output_context(agent: AgentResult, brain: BrainResult) -> str:
    return agent.answer
