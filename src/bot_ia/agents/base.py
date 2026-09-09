"""Validación común que impide a un agente operar fuera de su expediente."""

from __future__ import annotations

from .models import AgentRequest, AgentResult, AgentStatus


class BaseAgent:
    AGENT_ID = ""

    def validate(self, request: AgentRequest) -> str | None:
        if request.agent_id != self.AGENT_ID:
            return "wrong_agent"
        if request.context_pack.universe_id != request.universe_id:
            return "context_universe_mismatch"
        if request.evidence_pack.query.universe_id != request.universe_id:
            return "evidence_universe_mismatch"
        if request.state is not None and request.state.universe_id != request.universe_id:
            return "state_universe_mismatch"
        return None

    def rejected(self, reason: str) -> AgentResult:
        return AgentResult(self.AGENT_ID, AgentStatus.REJECTED, "Request rejected by local safety checks.", (), (), reason, (), "Provide an internally consistent agent request.")
