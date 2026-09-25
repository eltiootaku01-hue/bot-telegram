from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import FanRequest, MediaAsset, RequestStatus


@dataclass(frozen=True, slots=True)
class CamiWorkItem:
    """One operator-facing task ordered by operational risk and urgency."""

    kind: str
    reference_id: int
    priority: int
    title: str
    detail: str
    next_action: str
    due_at: datetime | None = None
    created_at: datetime | None = None
    overdue: bool = False


class CamiWorkboardService:
    """Merge request/media queues into one deterministic operator workboard.

    The workboard does not replace durable queues. It is a read-only routing
    layer that tells the human operator what deserves attention first.
    """

    REQUEST_STATUSES = (
        RequestStatus.NEW.value,
        RequestStatus.NEEDS_INFO.value,
        RequestStatus.PENDING_ADMIN.value,
        RequestStatus.PROCESSING.value,
        RequestStatus.APPROVED.value,
        RequestStatus.SCHEDULED.value,
    )
    MEDIA_STATUSES = (
        "delivery_unknown",
        "cami_inbox",
        "needs_tag",
        "waiting_destination",
        "waiting_schedule",
        "scheduled",
    )

    async def next_items(
        self,
        session: AsyncSession,
        *,
        limit: int = 10,
        now: datetime | None = None,
    ) -> list[CamiWorkItem]:
        if limit <= 0:
            return []
        now = now or utc_now()

        requests = list(
            await session.scalars(
                select(FanRequest)
                .where(FanRequest.status.in_(self.REQUEST_STATUSES))
                .order_by(FanRequest.id.asc())
                .limit(max(limit * 3, 30))
            )
        )
        assets = list(
            await session.scalars(
                select(MediaAsset)
                .where(MediaAsset.status.in_(self.MEDIA_STATUSES))
                .order_by(MediaAsset.id.asc())
                .limit(max(limit * 3, 30))
            )
        )

        items = [self._request_item(request, now=now) for request in requests]
        items.extend(self._media_item(asset, now=now) for asset in assets)
        items.sort(
            key=lambda item: (
                -item.priority,
                item.due_at or datetime.max,
                item.created_at or datetime.max,
                item.kind,
                item.reference_id,
            )
        )
        return items[:limit]

    @staticmethod
    def _request_item(request: FanRequest, *, now: datetime) -> CamiWorkItem:
        status = request.status
        if request.due_at is not None and request.due_at < now:
            priority = 1200
            next_action = "Atender de inmediato: el SLA ya venció."
        elif status == RequestStatus.PENDING_ADMIN.value:
            priority = 1050
            next_action = "Revisar pedido y asociar material cuando esté disponible."
        elif status == RequestStatus.NEEDS_INFO.value:
            priority = 1020
            next_action = "Pedir o completar la información faltante."
        elif status == RequestStatus.NEW.value:
            priority = 980
            next_action = "Validar el pedido y pasarlo a la cola administrativa."
        elif status == RequestStatus.PROCESSING.value:
            priority = 860
            next_action = "Comprobar que exista material y que la publicación avance."
        elif status == RequestStatus.APPROVED.value:
            priority = 820
            next_action = "Programar o enviar el material aprobado."
        else:
            priority = 700
            next_action = "Comprobar la programación pendiente."

        return CamiWorkItem(
            kind="request",
            reference_id=request.id,
            priority=priority,
            title=f"Pedido #{request.id}",
            detail=request.description[:180],
            next_action=next_action,
            due_at=request.due_at,
            created_at=request.created_at,
            overdue=request.due_at is not None and request.due_at < now,
        )

    @staticmethod
    def _media_item(asset: MediaAsset, *, now: datetime) -> CamiWorkItem:
        status = asset.status
        if status == "delivery_unknown":
            priority = 1250
            next_action = "Resolver la entrega ambigua antes de reintentar."
        elif status == "needs_tag":
            priority = 1000
            next_action = "Etiquetar personaje, obra, tags y categoría."
        elif status == "cami_inbox":
            priority = 940
            next_action = "Clasificar el material y decidir su destino."
        elif status == "waiting_destination":
            priority = 900
            next_action = "Elegir comunidad/destino autorizado."
        elif status == "waiting_schedule":
            priority = 880
            next_action = "Definir fecha y hora de publicación."
        else:
            priority = 650
            next_action = "Comprobar que la publicación programada siga en curso."

        created = asset.created_at
        return CamiWorkItem(
            kind="media",
            reference_id=asset.id,
            priority=priority,
            title=f"Material #{asset.id}",
            detail=(
                f"{(asset.character_id or 'sin personaje').replace('-', ' ')} · "
                f"{asset.anime or 'obra sin indicar'}"
            ),
            next_action=next_action,
            due_at=asset.scheduled_at if status == "scheduled" else None,
            created_at=created,
            overdue=False,
        )


def format_cami_workboard(items: list[CamiWorkItem]) -> str:
    """Render the private operator board without Telegram credentials or IDs."""
    if not items:
        return "🧭 <b>Tablero de Cami</b>\n\n✅ No hay trabajo operativo pendiente."

    lines = [
        "🧭 <b>Tablero operativo de Cami</b>",
        "",
        "Ordenado por riesgo y urgencia. Cada línea propone la siguiente acción.",
        "",
    ]
    for index, item in enumerate(items, start=1):
        kind = "🧾" if item.kind == "request" else "🖼️"
        overdue = " 🔴 SLA VENCIDO" if item.overdue else ""
        lines.extend(
            (
                f"{index}. {kind} <b>{item.title}</b>{overdue}",
                f"   {item.detail}",
                f"   ➜ {item.next_action}",
            )
        )
    lines.extend(("", "Este tablero es una vista de trabajo; las colas persistentes siguen siendo la fuente de verdad."))
    return "\n".join(lines)
