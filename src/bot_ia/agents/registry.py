"""Despacho explícito de agentes ya seleccionados por el Router/Cerebro."""

from __future__ import annotations

from bot_ia.core.models import Intent

from .adapters import EditorAgent, HistorianAgent, IAChanAgent, ResearcherAgent
from .models import AgentRequest, AgentResult


class AgentRegistry:
    def __init__(self) -> None:
        agents = (IAChanAgent(), HistorianAgent(), EditorAgent(), ResearcherAgent())
        self._agents = {agent.AGENT_ID: agent for agent in agents}
        self._intent_targets = {
            Intent.CREATIVE_WRITING: "ia_chan", Intent.IDEA: "ia_chan",
            Intent.EDITORIAL_REVIEW: "editor", Intent.CANON: "historian",
            Intent.CONTINUITY: "historian", Intent.EXTERNAL_RESEARCH: "researcher",
        }

    def agent_for_intent(self, intent: Intent) -> str | None:
        return self._intent_targets.get(intent)

    def dispatch(self, request: AgentRequest) -> AgentResult:
        agent = self._agents.get(request.agent_id)
        if agent is None:
            return IAChanAgent().rejected("unknown_agent")
        return agent.run(request)
