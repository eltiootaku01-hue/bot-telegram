from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.core.identity import BotIdentity


_WORDS = re.compile(r"[\wáéíóúüñ]+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ProcessDefinition:
    """Declarative capability contract for one operational bot workflow."""

    id: str
    owner: BotIdentity
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
    """Deterministic process registry used before any optional AI routing.

    The catalog describes *what the system is allowed to do*. A future LLM
    can rank a small candidate set, but it cannot invent a process or action.
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

    def for_identity(self, identity: BotIdentity) -> tuple[ProcessDefinition, ...]:
        return tuple(process for process in self._processes.values() if process.owner is identity)

    def search(
        self,
        query: str,
        *,
        owner: BotIdentity | None = None,
        category: str | None = None,
        limit: int = 8,
    ) -> tuple[ProcessMatch, ...]:
        if limit <= 0:
            return ()
        tokens = set(_WORDS.findall(query.casefold()))
        if not tokens:
            return ()

        matches: list[ProcessMatch] = []
        for process in self._processes.values():
            if owner is not None and process.owner is not owner:
                continue
            if category and process.category.casefold() != category.casefold():
                continue
            searchable = " ".join(
                (
                    process.name,
                    process.category,
                    process.objective,
                    *process.conditions,
                    *process.inputs,
                    *process.outputs,
                )
            ).casefold()
            words = set(_WORDS.findall(searchable))
            overlap = len(tokens & words)
            if overlap == 0:
                continue
            score = float(overlap) + min(process.priority, 100) / 100.0
            if category:
                score += 2.0
            matches.append(ProcessMatch(process=process, score=score))

        matches.sort(key=lambda item: (-item.score, -item.process.priority, item.process.id))
        return tuple(matches[:limit])


def built_in_catalog() -> ProcessCatalog:
    """Production workflow catalog for Cari, Sunna, Cami, Chie and Tío Otaku."""
    def p(
        process_id: str,
        owner: BotIdentity,
        name: str,
        category: str,
        objective: str,
        *,
        conditions: tuple[str, ...] = (),
        inputs: tuple[str, ...] = (),
        outputs: tuple[str, ...] = (),
        actions: tuple[str, ...] = (),
        priority: int = 50,
        cost: float = 1.0,
        requires_ai: bool = False,
    ) -> ProcessDefinition:
        return ProcessDefinition(
            id=process_id,
            owner=owner,
            name=name,
            category=category,
            objective=objective,
            conditions=conditions,
            inputs=inputs,
            outputs=outputs,
            allowed_actions=actions,
            priority=priority,
            cost=cost,
            requires_ai=requires_ai,
        )

    return ProcessCatalog(
        (
            p(
                "cari.cafe.menu",
                BotIdentity.CARI,
                "Abrir Café Otaku",
                "cafe",
                "Mostrar el punto de encuentro y sus servicios deterministas",
                outputs=("message_id",),
                actions=("telegram.send_message",),
                priority=85,
                cost=0.1,
            ),
            p(
                "cari.cafe.recommendation",
                BotIdentity.CARI,
                "Dar recomendación diaria",
                "cafe",
                "Entregar una recomendación diaria reproducible por comunidad y fecha",
                inputs=("chat_id", "day_key"),
                outputs=("recommendation", "message_id"),
                actions=("telegram.send_message", "world.observe"),
                priority=70,
                cost=0.2,
            ),
            p(
                "cari.moderation.warn",
                BotIdentity.CARI,
                "Advertir integrante",
                "moderation",
                "Registrar y comunicar una advertencia solicitada por un administrador",
                conditions=("telegram_admin", "authorized_chat"),
                inputs=("chat_id", "target_user_id", "reason"),
                outputs=("moderation_action_id", "message_id"),
                actions=("telegram.send_message", "moderation.record"),
                priority=90,
                cost=0.3,
            ),
            p(
                "sunna.waifumon.spawn",
                BotIdentity.SUNNA,
                "Crear encuentro WaifuMon",
                "game",
                "Crear un único encuentro activo y publicarlo en la comunidad autorizada",
                conditions=("authorized_chat", "no_active_encounter"),
                inputs=("chat_id",),
                outputs=("encounter_id", "message_id"),
                actions=("db.claim", "telegram.send_message", "world.observe"),
                priority=95,
                cost=0.8,
            ),
            p(
                "sunna.waifumon.capture",
                BotIdentity.SUNNA,
                "Resolver captura WaifuMon",
                "game",
                "Validar una respuesta, capturar el encuentro y acreditar progreso una sola vez",
                conditions=("authorized_chat", "active_encounter", "unique_attempt"),
                inputs=("encounter_id", "user_id", "answer"),
                outputs=("collection_id", "points_balance"),
                actions=("db.claim", "collection.increment", "points.credit", "world.observe"),
                priority=100,
                cost=0.6,
            ),
            p(
                "sunna.gacha.roll",
                BotIdentity.SUNNA,
                "Resolver gacha",
                "game",
                "Ejecutar una tirada determinista y registrar el resultado",
                conditions=("private_chat",),
                inputs=("roll_id", "user_id"),
                outputs=("rarity", "character_id"),
                actions=("rng.deterministic", "db.record", "world.observe"),
                priority=90,
                cost=0.2,
            ),
            p(
                "sunna.trivia.round",
                BotIdentity.SUNNA,
                "Publicar trivia",
                "game",
                "Crear y publicar una ronda de trivia única en la comunidad",
                conditions=("authorized_chat", "no_live_round"),
                inputs=("chat_id", "day_or_slot"),
                outputs=("round_id", "message_id"),
                actions=("db.claim", "telegram.send_message", "world.observe"),
                priority=85,
                cost=0.5,
            ),
            p(
                "cami.media.ingest",
                BotIdentity.CAMI,
                "Ingresar material",
                "media",
                "Registrar una imagen o documento de Telegram sin duplicarla",
                conditions=("media_staff",),
                inputs=("file_id", "file_unique_id", "source_message_id"),
                outputs=("asset_id",),
                actions=("db.upsert", "world.observe"),
                priority=85,
                cost=0.2,
            ),
            p(
                "cami.media.classify",
                BotIdentity.CAMI,
                "Clasificar material",
                "media",
                "Asignar personaje, obra, tags y categoría antes de publicarlo",
                conditions=("media_staff", "asset_exists"),
                inputs=("asset_id", "metadata"),
                outputs=("asset_status",),
                actions=("db.update", "catalog.upsert", "world.observe"),
                priority=95,
                cost=0.3,
            ),
            p(
                "cami.media.schedule",
                BotIdentity.CAMI,
                "Programar publicación",
                "scheduling",
                "Convertir horario local del mundo a UTC y persistir una orden durable",
                conditions=("media_staff", "future_datetime"),
                inputs=("asset_id", "local_datetime", "timezone", "destination"),
                outputs=("job_id", "scheduled_at_utc"),
                actions=("time.local_to_utc", "db.update", "jobs.enqueue"),
                priority=95,
                cost=0.2,
            ),
            p(
                "cami.media.publish",
                BotIdentity.CAMI,
                "Publicar material",
                "media",
                "Enviar material mediante file_id, registrar IDs y recuperar entregas ambiguas",
                conditions=("authorized_destination", "scheduled_asset"),
                inputs=("asset_id", "destination"),
                outputs=("telegram_message_ids", "asset_status"),
                actions=("db.claim", "telegram.send_media", "db.record", "recovery.flag"),
                priority=100,
                cost=1.0,
            ),
            p(
                "cami.request.fulfill",
                BotIdentity.CAMI,
                "Completar pedido",
                "requests",
                "Asociar un material con un pedido y publicarlo en el tema correcto",
                conditions=("media_staff", "pending_request", "authorized_group"),
                inputs=("asset_id", "request_id"),
                outputs=("request_status", "message_id"),
                actions=("db.claim", "jobs.enqueue", "telegram.send_media", "db.record"),
                priority=95,
                cost=0.9,
            ),
            p(
                "cami.publication.recover",
                BotIdentity.CAMI,
                "Resolver entrega ambigua",
                "recovery",
                "Dar una decisión humana segura cuando Telegram pudo aceptar un envío antes de persistir su ID",
                conditions=("media_staff", "delivery_unknown"),
                inputs=("asset_id", "decision"),
                outputs=("asset_status", "request_status"),
                actions=("db.update", "jobs.enqueue"),
                priority=100,
                cost=0.1,
            ),
            p(
                "cami.anime.lookup",
                BotIdentity.CAMI,
                "Consultar catálogo local",
                "catalog",
                "Buscar una obra o personaje en la base local con procedencia explícita",
                inputs=("query",),
                outputs=("matches",),
                actions=("catalog.search", "world.observe"),
                priority=80,
                cost=0.2,
            ),
            p(
                "chie.setup.community",
                BotIdentity.CHIE,
                "Configurar comunidad",
                "setup",
                "Verificar permisos y preparar los temas operativos de Telegram",
                conditions=("telegram_admin", "authorized_chat"),
                inputs=("chat_id",),
                outputs=("setup_status", "topic_ids"),
                actions=("telegram.get_chat_member", "telegram.create_forum_topic", "db.update"),
                priority=100,
                cost=1.5,
            ),
            p(
                "chie.request.intake",
                BotIdentity.CHIE,
                "Recibir pedido",
                "requests",
                "Validar la petición de imagen, cobrar puntos de forma idempotente y crear un ticket",
                conditions=("authorized_chat", "enough_points"),
                inputs=("user_id", "chat_id", "description", "source_message_id"),
                outputs=("request_id", "remaining_points"),
                actions=("points.spend", "db.create", "events.publish"),
                priority=100,
                cost=0.5,
            ),
            p(
                "chie.request.track",
                BotIdentity.CHIE,
                "Consultar pedido propio",
                "requests",
                "Mostrar al usuario únicamente su propio estado de pedido",
                conditions=("request_owner",),
                inputs=("user_id", "chat_id"),
                outputs=("request_status",),
                actions=("db.read",),
                priority=85,
                cost=0.1,
            ),
            p(
                "chie.world.review",
                BotIdentity.CHIE,
                "Revisar Ciudad Animals",
                "world",
                "Analizar métricas agregadas y producir una revisión que no modifica el canon",
                inputs=("world_metrics",),
                outputs=("review",),
                actions=("world.insights", "report.render"),
                priority=80,
                cost=0.3,
            ),
            p(
                "chie.world.propose",
                BotIdentity.CHIE,
                "Proponer expansión del mundo",
                "world",
                "Convertir métricas agregadas en propuestas para revisión humana",
                inputs=("world_metrics", "candidate_scenes"),
                outputs=("proposals",),
                actions=("world.insights", "ai.generate_text"),
                priority=60,
                cost=2.0,
                requires_ai=True,
            ),
            p(
                "tio.operator.inbox",
                BotIdentity.CARI,
                "Gestionar solicitud de Tío Otaku",
                "operator",
                "Mostrar contexto a la persona que opera manualmente a Tío Otaku",
                conditions=("admin_user",),
                inputs=("operator_request_id",),
                outputs=("context",),
                actions=("db.read", "telegram.send_message"),
                priority=100,
                cost=0.2,
            ),
        )
    )
