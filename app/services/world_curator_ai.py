from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.provider import BrainClient, LLMProviderError, LLMRequest
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldProposal, WorldReview
from app.services.process_catalog import built_in_catalog
from app.services.world_curator import WorldReviewReport


CURATOR_PERSONA = (
    "Sos una curadora interna de datos para Ciudad Animals. "
    "No sos Cari, Cami, Sunna ni Chie. No hables como personaje. "
    "Analizás únicamente el snapshot agregado que recibís."
)

CURATOR_RULES = (
    "Proponé como máximo 5 cambios pequeños y concretos. "
    "Cada propuesta debe distinguir una idea de una afirmación factual. "
    "No inventes canon, biografías, poderes, cronologías ni hechos que no estén en el snapshot. "
    "No propongas borrar ni reescribir personajes existentes. "
    "No incluyas datos personales ni texto de conversaciones. "
    "Respondé SOLO JSON con esta forma: "
    '{"proposals":[{"title":"...","idea":"...","reason":"...","affected_identities":["cari"]}]}'
)


@dataclass(frozen=True, slots=True)
class WorldProposalItem:
    title: str
    idea: str
    reason: str
    affected_identities: tuple[BotIdentity, ...]


@dataclass(frozen=True, slots=True)
class StoredWorldProposals:
    proposal_id: int
    review_id: int
    generator: str
    status: str
    items: tuple[WorldProposalItem, ...]


class WorldCuratorAIService:
    """Optional AI proposal layer; it never writes canon or catalog entries."""

    def __init__(
        self,
        settings: Settings | None = None,
        brain: BrainClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.brain = brain or BrainClient(self.settings)

    async def propose_for_database(
        self,
        database: Database,
        *,
        review_id: int,
        report: WorldReviewReport,
    ) -> StoredWorldProposals:
        """Generate outside the DB transaction, then persist in a short transaction."""
        if not self.settings.ai_for(BotIdentity.CHIE):
            raise LLMProviderError("AI curator is disabled for Chie")

        generator = self._generator_name()
        async with database.session() as session:
            review_row = await session.get(WorldReview, review_id)
            if review_row is None:
                raise ValueError(f"World review #{review_id} does not exist")
            if (
                report.review_type != review_row.review_type
                or report.period_key != review_row.period_key
            ):
                raise ValueError("World review report does not match persisted review")
            existing = await session.scalar(
                select(WorldProposal).where(
                    WorldProposal.review_id == review_row.id,
                    WorldProposal.generator == generator,
                )
            )
            if existing is not None:
                return self._decode(existing)

        request = self._request_for_report(report)
        raw = await self.brain.generate(request)
        items = self._parse(raw)

        return await self._persist_generated(
            database,
            review_id=review_id,
            generator=generator,
            items=items,
        )

    def _request_for_report(self, report: WorldReviewReport) -> LLMRequest:
        catalog = built_in_catalog()
        process_lines: list[str] = []
        for identity in BotIdentity:
            for process in catalog.for_identity(identity):
                process_lines.append(
                    f"{process.id} | {identity.value} | {process.name} | {process.category}"
                )

        system_extra = (
            CURATOR_RULES
            + " "
            + "Cuando una propuesta se refiera a una capacidad operativa, solo puede apoyarse "
              "en un process id de la siguiente lista. No inventes process ids, herramientas ni "
              "acciones ejecutables fuera de ella:\n"
            + "\n".join(process_lines)
        )

        return LLMRequest(
            identity=BotIdentity.CHIE,
            user_text=json.dumps(
                report.to_payload(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            persona=CURATOR_PERSONA,
            system_extra=system_extra,
            max_tokens=600,
            max_user_chars=8000,
            temperature=0.2,
        )

    async def _persist_generated(
        self,
        database: Database,
        *,
        review_id: int,
        generator: str,
        items: tuple[WorldProposalItem, ...],
    ) -> StoredWorldProposals:
        payload = {
            "proposals": [
                {
                    "title": item.title,
                    "idea": item.idea,
                    "reason": item.reason,
                    "affected_identities": [
                        identity.value for identity in item.affected_identities
                    ],
                }
                for item in items
            ]
        }
        async with database.session(write=True) as session:
            existing = await session.scalar(
                select(WorldProposal).where(
                    WorldProposal.review_id == review_id,
                    WorldProposal.generator == generator,
                )
            )
            if existing is not None:
                return self._decode(existing)

            row = WorldProposal(
                review_id=review_id,
                generator=generator,
                status="pending",
                payload_json=json.dumps(
                    payload,
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
                    select(WorldProposal).where(
                        WorldProposal.review_id == review_id,
                        WorldProposal.generator == generator,
                    )
                )
                if existing is None:
                    raise
                return self._decode(existing)

            return StoredWorldProposals(
                proposal_id=row.id,
                review_id=review_id,
                generator=generator,
                status=row.status,
                items=items,
            )

    async def propose(
        self,
        session: AsyncSession,
        *,
        review_row: WorldReview,
        report: WorldReviewReport,
    ) -> StoredWorldProposals:
        if not self.settings.ai_for(BotIdentity.CHIE):
            raise LLMProviderError("AI curator is disabled for Chie")

        if report.review_type != review_row.review_type or report.period_key != review_row.period_key:
            raise ValueError("World review report does not match persisted review")

        generator = self._generator_name()
        existing = await session.scalar(
            select(WorldProposal).where(
                WorldProposal.review_id == review_row.id,
                WorldProposal.generator == generator,
            )
        )
        if existing is not None:
            return self._decode(existing)

        request = self._request_for_report(report)
        raw = await self.brain.generate(request)
        items = self._parse(raw)
        payload = {
            "proposals": [
                {
                    "title": item.title,
                    "idea": item.idea,
                    "reason": item.reason,
                    "affected_identities": [
                        identity.value for identity in item.affected_identities
                    ],
                }
                for item in items
            ]
        }
        row = WorldProposal(
            review_id=review_row.id,
            generator=generator,
            status="pending",
            payload_json=json.dumps(
                payload,
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
                select(WorldProposal).where(
                    WorldProposal.review_id == review_row.id,
                    WorldProposal.generator == generator,
                )
            )
            if existing is None:
                raise
            return self._decode(existing)

        return StoredWorldProposals(
            proposal_id=row.id,
            review_id=review_row.id,
            generator=generator,
            status=row.status,
            items=items,
        )

    async def decide(
        self,
        session: AsyncSession,
        *,
        proposal_id: int,
        approved: bool,
    ) -> bool:
        status = "accepted" if approved else "rejected"
        result = await session.execute(
            update(WorldProposal)
            .where(
                WorldProposal.id == proposal_id,
                WorldProposal.status == "pending",
            )
            .values(status=status)
        )
        return result.rowcount == 1

    def _generator_name(self) -> str:
        provider = self.settings.llm_provider.strip().lower() or "auto"
        model = self.settings.llm_model.strip()
        if not model and provider == "ollama":
            model = self.settings.ollama_model.strip()
        return f"brain:{provider}:{model or 'default'}"

    @classmethod
    def _parse(cls, raw: str) -> tuple[WorldProposalItem, ...]:
        cleaned = raw.strip()
        fence = chr(96) * 3
        if cleaned.startswith(fence):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith(fence):
                lines = lines[1:]
            if lines and lines[-1].strip() == fence:
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("AI curator returned invalid JSON") from exc

        if not isinstance(data, dict) or not isinstance(data.get("proposals"), list):
            raise LLMProviderError("AI curator returned an invalid proposal payload")

        proposals = data["proposals"]
        if not 1 <= len(proposals) <= 5:
            raise LLMProviderError("AI curator must return between 1 and 5 proposals")

        result: list[WorldProposalItem] = []
        for index, raw_item in enumerate(proposals):
            if not isinstance(raw_item, dict):
                raise LLMProviderError(f"Invalid curator proposal #{index + 1}")
            title = cls._text(raw_item.get("title"), "title", index, 120)
            idea = cls._text(raw_item.get("idea"), "idea", index, 600)
            reason = cls._text(raw_item.get("reason"), "reason", index, 600)
            affected = raw_item.get("affected_identities", [])
            if not isinstance(affected, list):
                raise LLMProviderError(
                    f"Invalid affected_identities in curator proposal #{index + 1}"
                )

            identities: list[BotIdentity] = []
            for value in affected:
                if not isinstance(value, str):
                    raise LLMProviderError(
                        f"Invalid affected identity in curator proposal #{index + 1}"
                    )
                try:
                    identities.append(BotIdentity(value.strip().lower()))
                except ValueError as exc:
                    raise LLMProviderError(
                        f"Unknown affected identity in curator proposal #{index + 1}"
                    ) from exc

            result.append(
                WorldProposalItem(
                    title=title,
                    idea=idea,
                    reason=reason,
                    affected_identities=tuple(dict.fromkeys(identities)),
                )
            )
        return tuple(result)

    @staticmethod
    def _text(value: object, field: str, index: int, max_length: int) -> str:
        if not isinstance(value, str):
            raise LLMProviderError(
                f"Curator proposal #{index + 1} field {field!r} must be a string"
            )
        value = value.strip()
        if not value:
            raise LLMProviderError(
                f"Curator proposal #{index + 1} field {field!r} cannot be empty"
            )
        if len(value) > max_length:
            value = value[:max_length].rstrip()
        return value

    @classmethod
    def _decode(cls, row: WorldProposal) -> StoredWorldProposals:
        try:
            data = json.loads(row.payload_json)
            items = cls._parse(json.dumps(data, ensure_ascii=False))
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid stored world proposal #{row.id}") from exc
        return StoredWorldProposals(
            proposal_id=row.id,
            review_id=row.review_id,
            generator=row.generator,
            status=row.status,
            items=items,
        )


def format_world_proposals(stored: StoredWorldProposals) -> str:
    lines = [
        f"💡 <b>Propuestas de Ciudad Animals</b> · {escape(stored.generator)} · {escape(stored.status)}",
        "",
        "Estas ideas son no confiables y requieren revisión humana.",
        "No modifican automáticamente canon, personajes ni catálogo.",
        "",
    ]
    for index, item in enumerate(stored.items, start=1):
        identities = ", ".join(
            identity.value.title() for identity in item.affected_identities
        )
        lines.extend(
            (
                f"<b>{index}. {escape(item.title)}</b>",
                escape(item.idea),
                f"Motivo: {escape(item.reason)}",
                f"Personajes relacionados: {identities or 'ninguno indicado'}",
                "",
            )
        )
    return "\n".join(lines)
