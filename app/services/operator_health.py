from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.db.models import BotPresenceState, Chat, DurableJob, DomainEvent, MysteryRound, UserChat
from app.db.world_models import WorldCatalogEntry, WorldUsageStat


@dataclass(frozen=True, slots=True)
class OperatorHealthSnapshot:
    configured_communities: int
    authorized_communities: int
    members_seen: int
    pending_jobs: int
    processing_jobs: int
    failed_jobs: int
    pending_events: int
    processing_events: int
    failed_events: int
    active_mysteries: int
    catalog_entries: int
    world_observations: int
    active_identities: int


class OperatorHealthService:
    """Read-only operational snapshot for the human owner.

    The service intentionally exposes counts and state labels only. It never
    returns user message text, API credentials, or raw world observations.
    """

    async def snapshot(
        self,
        session: AsyncSession,
        *,
        authorized_chat_ids: frozenset[int],
    ) -> OperatorHealthSnapshot:
        configured = await session.scalar(
            select(func.count(func.distinct(Chat.id))).where(
                Chat.id.in_(
                    select(DurableJob.id).where(False)
                )
            )
        )
        del configured  # Keep all count queries explicit below.

        configured_chats = await session.scalar(
            select(func.count(func.distinct(UserChat.chat_id))).where(
                UserChat.chat_id.in_(
                    select(Chat.id).where(Chat.type.in_(("group", "supergroup")))
                )
            )
        )
        configured_chat_ids = await session.scalars(
            select(Chat.id).where(Chat.type.in_(("group", "supergroup")))
        )
        configured_ids = {int(chat_id) for chat_id in configured_chat_ids}
        authorized_configured = len(configured_ids & set(authorized_chat_ids))

        pending_jobs = await session.scalar(
            select(func.count()).select_from(DurableJob).where(DurableJob.status == "pending")
        )
        processing_jobs = await session.scalar(
            select(func.count()).select_from(DurableJob).where(DurableJob.status == "processing")
        )
        failed_jobs = await session.scalar(
            select(func.count()).select_from(DurableJob).where(DurableJob.status == "failed")
        )
        pending_events = await session.scalar(
            select(func.count()).select_from(DomainEvent).where(DomainEvent.status == "pending")
        )
        processing_events = await session.scalar(
            select(func.count()).select_from(DomainEvent).where(DomainEvent.status == "processing")
        )
        failed_events = await session.scalar(
            select(func.count()).select_from(DomainEvent).where(DomainEvent.status == "failed")
        )
        active_mysteries = await session.scalar(
            select(func.count()).select_from(MysteryRound).where(MysteryRound.status == "active")
        )
        catalog_entries = await session.scalar(
            select(func.count()).select_from(WorldCatalogEntry).where(WorldCatalogEntry.enabled.is_(True))
        )
        world_observations = await session.scalar(
            select(func.coalesce(func.sum(WorldUsageStat.count), 0)).where(
                WorldUsageStat.scope_type == "world"
            )
        )
        active_identities = await session.scalar(
            select(func.count()).select_from(BotPresenceState).where(
                BotPresenceState.status != "manual_off"
            )
        )

        return OperatorHealthSnapshot(
            configured_communities=int(configured_chats or 0),
            authorized_communities=authorized_configured,
            members_seen=int(
                await session.scalar(select(func.count()).select_from(UserChat)) or 0
            ),
            pending_jobs=int(pending_jobs or 0),
            processing_jobs=int(processing_jobs or 0),
            failed_jobs=int(failed_jobs or 0),
            pending_events=int(pending_events or 0),
            processing_events=int(processing_events or 0),
            failed_events=int(failed_events or 0),
            active_mysteries=int(active_mysteries or 0),
            catalog_entries=int(catalog_entries or 0),
            world_observations=int(world_observations or 0),
            active_identities=int(active_identities or 0),
        )


def format_operator_health(snapshot: OperatorHealthSnapshot) -> str:
    """Render a compact owner-facing report without exposing sensitive data."""
    identities = ", ".join(identity.value for identity in BotIdentity)
    return (
        "🩺 <b>Salud de Ciudad Animals</b>\n\n"
        f"🏠 Comunidades configuradas: <b>{snapshot.configured_communities}</b>\n"
        f"🔐 Comunidades autorizadas: <b>{snapshot.authorized_communities}</b>\n"
        f"👥 Relaciones de miembros registradas: <b>{snapshot.members_seen}</b>\n\n"
        f"📦 Jobs pendientes: <b>{snapshot.pending_jobs}</b> · "
        f"procesando: <b>{snapshot.processing_jobs}</b> · "
        f"fallidos: <b>{snapshot.failed_jobs}</b>\n"
        f"📨 Eventos pendientes: <b>{snapshot.pending_events}</b> · "
        f"procesando: <b>{snapshot.processing_events}</b> · "
        f"fallidos: <b>{snapshot.failed_events}</b>\n"
        f"🕵️ Misterios activos: <b>{snapshot.active_mysteries}</b>\n"
        f"🌍 Catálogo: <b>{snapshot.catalog_entries}</b> · "
        f"observaciones globales: <b>{snapshot.world_observations}</b>\n"
        f"🤖 Identidades activas: <b>{snapshot.active_identities}</b> / {len(identities.split(', '))}\n\n"
        "La revisión es de solo lectura; no ejecuta IA ni modifica datos."
    )
