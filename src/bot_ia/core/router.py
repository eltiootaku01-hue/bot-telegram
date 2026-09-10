"""Router puro: decide una ruta, nunca ejecuta proveedores ni búsquedas."""

from __future__ import annotations

from .models import BrainResult, Intent, Route, RouteDecision


class Router:
    _SEARCH_INTENTS = frozenset({Intent.FACTUAL, Intent.CHARACTER, Intent.CANON, Intent.CONTINUITY, Intent.EXTERNAL_RESEARCH})

    def decide(self, result: BrainResult) -> RouteDecision:
        if result.state_status == "rejected":
            return RouteDecision(Route.LOCAL, "state change rejected", result.confidence, result.intent, result.universe_id, clarification=result.clarification)
        if result.ambiguity or result.intent is Intent.CLARIFICATION_NEEDED:
            return RouteDecision(Route.CLARIFICATION, "clarification required", result.confidence, result.intent, result.universe_id, clarification=result.clarification)
        if result.intent in {Intent.GREETING, Intent.HELP, Intent.KNOWLEDGE_OVERVIEW, Intent.ORGANIZATION, Intent.UNIVERSE_CHANGE}:
            return RouteDecision(Route.LOCAL, "deterministic local request", result.confidence, result.intent, result.universe_id)
        if result.intent is Intent.EDITORIAL_REVIEW:
            return RouteDecision(
                Route.AGENT,
                "editorial review uses the editor agent and an explicit writing provider",
                result.confidence,
                result.intent,
                result.universe_id,
                requires_agent=True,
                requires_llm=True,
                agent_id="editor",
            )
        if result.intent in {Intent.CREATIVE_WRITING, Intent.IDEA}:
            return RouteDecision(Route.LLM, "creative request requires future LLM", result.confidence, result.intent, result.universe_id, requires_llm=True, agent_id="ia_chan")
        if result.intent in self._SEARCH_INTENTS:
            return RouteDecision(Route.SEARCH, "factual evidence lookup required", result.confidence, result.intent, result.universe_id, requires_search=True)
        return RouteDecision(Route.CLARIFICATION, "intent not established", result.confidence, result.intent, result.universe_id, clarification="Indica qué deseas consultar o crear.")
