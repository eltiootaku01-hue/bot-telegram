from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.core.time import utc_now
from app.db.world_models import WorldReview
from app.services.world import WorldInsight, WorldService


@dataclass(frozen=True, slots=True)
class IdentityReview:
    identity: BotIdentity
    hot: tuple[tuple[str, int], ...]
    cold: tuple[tuple[str, int], ...]
    unseen: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class WorldReviewReport:
    review_type: str
    period_key: str
    generated_at: datetime
    identities: tuple[IdentityReview, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "review_type": self.review_type,
            "period_key": self.period_key,
            "generated_at": self.generated_at.isoformat(),
            "identities": [
                {
                    "identity": item.identity.value,
                    "hot": [[key, count] for key, count in item.hot],
                    "cold": [[key, count] for key, count in item.cold],
                    "unseen": [[key, label] for key, label in item.unseen],
                }
                for item in self.identities
            ],
        }


class WorldCuratorService:
    """Build and persist human-reviewable world snapshots from aggregate data only."""

    DAILY = "daily"

    def __init__(self, world: WorldService | None = None) -> None:
        self.world = world or WorldService()

    async def build_daily(
        self,
        session: AsyncSession,
        *,
        day_key: str,
        limit: int = 5,
    ) -> WorldReviewReport:
        if not day_key.strip():
            raise ValueError("day_key cannot be empty")
        if limit <= 0:
            raise ValueError("limit must be positive")

        identities: list[IdentityReview] = []
        for identity in BotIdentity:
            insight = await self.world.insights(
                session,
                bot_identity=identity,
                limit=limit,
            )
            identities.append(self._identity_review(identity, insight))

        generated_at = utc_now()
        report = WorldReviewReport(
            review_type=self.DAILY,
            period_key=day_key,
            generated_at=generated_at,
            identities=tuple(identities),
        )

        existing = await session.scalar(
            select(WorldReview).where(
                WorldReview.review_type == self.DAILY,
                WorldReview.period_key == day_key,
            )
        )
        if existing is not None:
            return self._decode(existing)

        row = WorldReview(
            review_type=report.review_type,
            period_key=report.period_key,
            generated_at=generated_at,
            report_json=json.dumps(
                report.to_payload(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(WorldReview).where(
                    WorldReview.review_type == self.DAILY,
                    WorldReview.period_key == day_key,
                )
            )
            if existing is None:
                raise
            return self._decode(existing)
        return report

    async def latest_daily(
        self,
        session: AsyncSession,
    ) -> WorldReviewReport | None:
        row = await session.scalar(
            select(WorldReview)
            .where(WorldReview.review_type == self.DAILY)
            .order_by(WorldReview.generated_at.desc(), WorldReview.id.desc())
            .limit(1)
        )
        return self._decode(row) if row is not None else None

    @staticmethod
    def _identity_review(identity: BotIdentity, insight: WorldInsight) -> IdentityReview:
        return IdentityReview(
            identity=identity,
            hot=tuple(insight.hot),
            cold=tuple(insight.cold),
            unseen=tuple(insight.unseen),
        )

    @staticmethod
    def _decode(row: WorldReview) -> WorldReviewReport:
        try:
            payload = json.loads(row.report_json)
            identities = tuple(
                IdentityReview(
                    identity=BotIdentity(item["identity"]),
                    hot=tuple((str(key), int(count)) for key, count in item.get("hot", [])),
                    cold=tuple((str(key), int(count)) for key, count in item.get("cold", [])),
                    unseen=tuple((str(key), str(label)) for key, label in item.get("unseen", [])),
                )
                for item in payload["identities"]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid stored world review #{row.id}") from exc

        generated_raw = payload.get("generated_at")
        generated_at = row.generated_at
        if isinstance(generated_raw, str):
            try:
                generated_at = datetime.fromisoformat(generated_raw)
            except ValueError:
                generated_at = row.generated_at

        return WorldReviewReport(
            review_type=str(payload.get("review_type", row.review_type)),
            period_key=str(payload.get("period_key", row.period_key)),
            generated_at=generated_at,
            identities=identities,
        )


def format_world_review(report: WorldReviewReport) -> str:
    lines = [
        f"🌍 <b>Revisión {report.review_type} · {report.period_key}</b>",
        "",
        "Snapshot agregado para revisión humana. No contiene texto libre de conversaciones.",
        "",
    ]
    for item in report.identities:
        lines.append(f"<b>{item.identity.value.title()}</b>")
        if item.hot:
            lines.append("🔥 " + ", ".join(f"{key} ({count})" for key, count in item.hot))
        if item.cold:
            lines.append("❄️ " + ", ".join(f"{key} ({count})" for key, count in item.cold))
        if item.unseen:
            lines.append("👀 " + ", ".join(key for key, _ in item.unseen))
        if not item.hot and not item.cold and not item.unseen:
            lines.append("· sin señales todavía")
        lines.append("")
    lines.extend(
        (
            "La IA puede usar este snapshot como insumo opcional.",
            "No modifica automáticamente canon, personajes ni catálogo.",
        )
    )
    return "\n".join(lines)
