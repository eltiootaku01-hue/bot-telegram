from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable


_WORDS = re.compile(r"[\wáéíóúüñ]+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ProcessDefinition:
    id: str
    name: str
    category: str
    objective: str
    conditions: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    priority: int = 0
    cost: float = 1.0
    requires_ai: bool = False


@dataclass(frozen=True, slots=True)
class ProcessMatch:
    process: ProcessDefinition
    score: float


class ProcessCatalog:
    """Deterministic process registry and lightweight relevance search.

    This experiment deliberately does not call an LLM. A later AI router may
    evaluate only the small candidate set returned here; it never invents an
    executable process or bypasses allowed_actions.
    """

    def __init__(self, processes: Iterable[ProcessDefinition] = ()) -> None:
        self._processes: dict[str, ProcessDefinition] = {}
        for process in processes:
            self.register(process)

    def register(self, process: ProcessDefinition) -> None:
        if not process.id.strip():
            raise ValueError("process id must not be empty")
        if process.id in self._processes:
            raise ValueError(f"duplicate process id: {process.id}")
        if process.priority < 0:
            raise ValueError("priority must be >= 0")
        if process.cost < 0:
            raise ValueError("cost must be >= 0")
        self._processes[process.id] = process

    def get(self, process_id: str) -> ProcessDefinition | None:
        return self._processes.get(process_id)

    def all(self) -> tuple[ProcessDefinition, ...]:
        return tuple(self._processes.values())

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 20,
    ) -> tuple[ProcessMatch, ...]:
        if limit <= 0:
            return ()
        tokens = set(_WORDS.findall(query.casefold()))
        matches: list[ProcessMatch] = []
        for process in self._processes.values():
            if category and process.category.casefold() != category.casefold():
                continue
            searchable = " ".join((process.name, process.objective, process.category)).casefold()
            words = set(_WORDS.findall(searchable))
            overlap = len(tokens & words)
            category_bonus = 2.0 if category and process.category.casefold() == category.casefold() else 0.0
            priority_bonus = min(process.priority, 100) / 100.0
            score = float(overlap) + category_bonus + priority_bonus
            if score > 0:
                matches.append(ProcessMatch(process, score))
        matches.sort(key=lambda item: (-item.score, -item.process.priority, item.process.id))
        return tuple(matches[:limit])


def built_in_catalog() -> ProcessCatalog:
    """Small deterministic seed; expand only with tested processes."""
    return ProcessCatalog(
        (
            ProcessDefinition(
                id="telegram.reply",
                name="Responder mensaje",
                category="telegram",
                objective="Enviar una respuesta de texto a un mensaje recibido",
                inputs=("chat_id", "text"),
                outputs=("message_id",),
                allowed_actions=("telegram.send_message",),
                priority=80,
                cost=0.1,
                requires_ai=False,
            ),
            ProcessDefinition(
                id="telegram.moderation.warn",
                name="Advertir usuario",
                category="moderation",
                objective="Enviar una advertencia a un usuario cuando una regla lo requiere",
                conditions=("moderation_rule_matched", "admin_policy_allows_warning"),
                inputs=("chat_id", "user_id", "reason"),
                outputs=("message_id",),
                allowed_actions=("telegram.send_message", "moderation.record_warning"),
                priority=90,
                cost=0.2,
                requires_ai=False,
            ),
            ProcessDefinition(
                id="chat.summarize",
                name="Resumir conversación",
                category="chat",
                objective="Crear un resumen breve de mensajes de una conversación",
                inputs=("messages",),
                outputs=("summary",),
                allowed_actions=("ai.generate_text",),
                priority=40,
                cost=2.0,
                requires_ai=True,
            ),
        )
    )
