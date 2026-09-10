"""Servicio de aplicación: une estado, Cerebro y Router sin conocer Telegram."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable

from bot_ia.contracts import SessionState

from .brain import LocalBrain
from .models import BrainRequest, BrainResult, EntityCandidate, Route, RouteDecision
from .router import Router


CandidateProvider = Callable[[str], tuple[EntityCandidate, ...]]
Executor = Callable[[BrainResult, RouteDecision], str | None]


@dataclass(frozen=True, slots=True)
class ApplicationRequest:
    user_id: str
    conversation_id: str
    message: str


@dataclass(frozen=True, slots=True)
class ApplicationResponse:
    text: str
    brain: BrainResult
    decision: RouteDecision
    execution: object | None = None


class InMemorySessionStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], SessionState] = {}

    def get(self, user_id: str, conversation_id: str) -> SessionState | None:
        return self._states.get((user_id, conversation_id))

    def put(self, user_id: str, conversation_id: str, state: SessionState) -> None:
        self._states[(user_id, conversation_id)] = state

    def get_or_create(
        self,
        user_id: str,
        conversation_id: str,
        universe_id: str | None,
    ) -> SessionState | None:
        state = self.get(user_id, conversation_id)
        if state is not None or universe_id is None:
            return state

        state = SessionState(
            f"telegram:{user_id}:{conversation_id}",
            universe_id,
            datetime.now(timezone.utc) + timedelta(hours=8),
        )
        self.put(user_id, conversation_id, state)
        return state


class BotApplication:
    def __init__(
        self,
        brain: LocalBrain,
        router: Router,
        sessions: InMemorySessionStore,
        *,
        default_universe_id: str | None = None,
        candidate_provider: CandidateProvider | None = None,
        executor: Executor | object | None = None,
    ) -> None:
        self._brain = brain
        self._router = router
        self._sessions = sessions
        self._default_universe_id = default_universe_id
        self._candidate_provider = candidate_provider or (lambda _universe_id: ())
        self._executor = executor

    def handle(self, request: ApplicationRequest) -> ApplicationResponse:
        state = self._sessions.get_or_create(
            request.user_id,
            request.conversation_id,
            self._default_universe_id,
        )

        universe_id = state.universe_id if state is not None else None
        candidates = (
            self._candidate_provider(universe_id)
            if universe_id is not None
            else ()
        )

        brain = self._brain.process(
            BrainRequest(
                request.message,
                request.user_id,
                request.conversation_id,
                state,
                universe_id=universe_id,
                candidates=candidates,
            )
        )

        # A first-turn universe change can succeed before a session exists.
        # Materialize the new session only after the Brain validates the target.
        if (
            state is None
            and brain.state_status == "updated"
            and brain.universe_id is not None
        ):
            state = SessionState(
                f"telegram:{request.user_id}:{request.conversation_id}",
                brain.universe_id,
                datetime.now(timezone.utc) + timedelta(hours=8),
            )
            brain = replace(brain, state=state)

        decision = self._router.decide(brain)

        if brain.state is not None:
            self._sessions.put(
                request.user_id,
                request.conversation_id,
                brain.state,
            )

        execution = None
        workflow_required = (
            self._executor is not None
            and not (
                universe_id is None
                and decision.route in {Route.LOCAL, Route.CLARIFICATION}
            )
        )
        if workflow_required:
            if hasattr(self._executor, "execute"):
                execution = self._executor.execute(request, brain, decision)
            else:
                execution = self._executor(brain, decision)

        text = (
            execution
            if isinstance(execution, str)
            else getattr(execution, "text", None)
        )

        return ApplicationResponse(
            text or self._local_message(decision),
            brain,
            decision,
            None if isinstance(execution, str) else execution,
        )

    @staticmethod
    def _local_message(decision: RouteDecision) -> str:
        if decision.route is Route.LOCAL:
            return (
                "Solicitud local procesada."
                if decision.reason != "state change rejected"
                else f"Cambio de estado rechazado: {decision.clarification}."
            )
        if decision.route is Route.CLARIFICATION:
            return decision.clarification or "Necesito una aclaración para continuar."
        if decision.route is Route.SEARCH:
            return "La búsqueda local está preparada para recuperar evidencia."
        if decision.route is Route.AGENT:
            return f"El expediente está preparado para el agente {decision.agent_id}."
        return f"La solicitud está preparada para el proveedor del agente {decision.agent_id}."
