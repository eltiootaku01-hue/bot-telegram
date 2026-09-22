from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utc_now
from app.db.models import CardDefinition, CardRollClaim, GameCardCollection
from app.db.repositories import MemberRepository


ALLOWED_RARITIES = frozenset({"C", "R", "SR", "SSR", "UR"})
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_CARD_ID_BASE_LENGTH = 72


@dataclass(frozen=True, slots=True)
class CardRollResult:
    definition: CardDefinition
    copies: int
    already_claimed: bool


class CardDefinitionService:
    """SQLite-backed admin card catalog and public /roll pool."""

    def __init__(self, settings: Settings | None = None, *, rng=None) -> None:
        self.settings = settings or Settings()
        self.rng = rng or secrets.SystemRandom()

    @staticmethod
    def validate_metadata(
        *,
        character_name: str,
        anime_origin: str,
        rarity: str,
        source_provider: str,
        collection_points: int,
    ) -> None:
        if not character_name.strip():
            raise ValueError("El nombre del personaje es obligatorio.")
        if not anime_origin.strip():
            raise ValueError("El anime/serie de origen es obligatorio.")
        if rarity not in ALLOWED_RARITIES:
            raise ValueError("Rareza inválida. Usá C, R, SR, SSR o UR.")
        if not source_provider.strip():
            raise ValueError("El proveedor de origen es obligatorio.")
        if collection_points < 0:
            raise ValueError("collection_points no puede ser negativo.")

    @staticmethod
    def _slug(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:MAX_CARD_ID_BASE_LENGTH]

    async def create_definition(
        self,
        session: AsyncSession,
        *,
        character_name: str,
        character_id: str | None,
        anime_origin: str,
        rarity: str,
        source_provider: str,
        collection_points: int,
        image_filename: str,
    ) -> CardDefinition:
        self.validate_metadata(
            character_name=character_name,
            anime_origin=anime_origin,
            rarity=rarity,
            source_provider=source_provider,
            collection_points=collection_points,
        )
        stem = self._slug(character_id or character_name) or "card"
        name_slug = self._slug(character_name)
        if name_slug and stem != name_slug and len(stem) < 32:
            stem = f"{stem}-{name_slug}"
        base = f"{stem}-{rarity.lower()}"
        for _ in range(32):
            candidate = f"{base}-{secrets.token_hex(2)}"
            if len(candidate) > 128:
                candidate = candidate[:123] + secrets.token_hex(2)
            if await session.get(CardDefinition, candidate) is not None:
                continue
            definition = CardDefinition(
                id=candidate,
                character_id=(character_id or stem)[:100],
                character_name=character_name.strip()[:255],
                anime_origin=anime_origin.strip()[:255],
                rarity=rarity,
                image_url=f"assets/cards/{image_filename}",
                source_provider=source_provider.strip()[:128],
                collection_points=collection_points,
                active=True,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(definition)
            try:
                await session.flush()
            except IntegrityError:
                continue
            return definition
        raise RuntimeError("No se pudo generar un ID único para la carta.")

    async def active_definitions(self, session: AsyncSession) -> list[CardDefinition]:
        result = await session.scalars(
            select(CardDefinition)
            .where(CardDefinition.active.is_(True))
            .order_by(CardDefinition.id.asc())
        )
        return list(result)

    async def roll(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        source_message_id: int,
    ) -> CardRollResult | None:
        existing_claim = await session.scalar(
            select(CardRollClaim)
            .where(
                CardRollClaim.user_id == user_id,
                CardRollClaim.chat_id == chat_id,
                CardRollClaim.source_message_id == source_message_id,
            )
        )
        if existing_claim is not None:
            definition = await session.get(CardDefinition, existing_claim.card_definition_id)
            if definition is None:
                raise RuntimeError("La carta reclamada ya no existe.")
            collection = await session.scalar(
                select(GameCardCollection).where(
                    GameCardCollection.profile_id
                    == (
                        await MemberRepository().get_or_create_game_profile(
                            session, user_id, chat_id, commit=False
                        )
                    ).id,
                    GameCardCollection.card_id == f"definition:{definition.id}",
                )
            )
            return CardRollResult(
                definition=definition,
                copies=collection.copies if collection is not None else 0,
                already_claimed=True,
            )

        definitions = await self.active_definitions(session)
        if not definitions:
            return None

        definition = self.rng.choice(definitions)
        claim = CardRollClaim(
            card_definition_id=definition.id,
            user_id=user_id,
            chat_id=chat_id,
            source_message_id=source_message_id,
            created_at=utc_now(),
        )
        try:
            async with session.begin_nested():
                session.add(claim)
                await session.flush()
        except IntegrityError:
            claim = await session.scalar(
                select(CardRollClaim).where(
                    CardRollClaim.user_id == user_id,
                    CardRollClaim.chat_id == chat_id,
                    CardRollClaim.source_message_id == source_message_id,
                )
            )
            if claim is None:
                raise
            definition = await session.get(CardDefinition, claim.card_definition_id)
            if definition is None:
                raise RuntimeError("La carta reclamada ya no existe.")
            profile = await MemberRepository().get_or_create_game_profile(
                session, user_id, chat_id, commit=False
            )
            collection = await session.scalar(
                select(GameCardCollection).where(
                    GameCardCollection.profile_id == profile.id,
                    GameCardCollection.card_id == f"definition:{definition.id}",
                )
            )
            return CardRollResult(
                definition=definition,
                copies=collection.copies if collection is not None else 0,
                already_claimed=True,
            )

        profile = await MemberRepository().get_or_create_game_profile(
            session, user_id, chat_id, commit=False
        )
        card_id = f"definition:{definition.id}"
        existing = await session.scalar(
            select(GameCardCollection).where(
                GameCardCollection.profile_id == profile.id,
                GameCardCollection.card_id == card_id,
            )
        )
        if existing is not None:
            updated = await session.execute(
                update(GameCardCollection)
                .where(
                    GameCardCollection.id == existing.id,
                    GameCardCollection.card_id == card_id,
                )
                .values(
                    copies=GameCardCollection.copies + 1,
                    updated_at=utc_now(),
                )
            )
            if updated.rowcount != 1:
                raise RuntimeError("La colección cambió durante el /roll.")
            await session.flush()
            await session.refresh(existing)
            copies = existing.copies
        else:
            row = GameCardCollection(
                profile_id=profile.id,
                card_id=card_id,
                character_id=definition.character_id,
                card_tier=definition.rarity,
                variant="custom",
                outfit="admin_upload",
                copies=1,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            try:
                async with session.begin_nested():
                    session.add(row)
                    await session.flush()
            except IntegrityError:
                existing = await session.scalar(
                    select(GameCardCollection).where(
                        GameCardCollection.profile_id == profile.id,
                        GameCardCollection.card_id == card_id,
                    )
                )
                if existing is None:
                    raise
                await session.execute(
                    update(GameCardCollection)
                    .where(GameCardCollection.id == existing.id)
                    .values(copies=GameCardCollection.copies + 1, updated_at=utc_now())
                )
                await session.flush()
                await session.refresh(existing)
                copies = existing.copies
            else:
                copies = 1

        return CardRollResult(
            definition=definition,
            copies=copies,
            already_claimed=False,
        )


def safe_card_filename(filename: str, content_type: str) -> str:
    suffix = ALLOWED_IMAGE_TYPES.get(content_type)
    if suffix is None:
        raise ValueError("Formato de imagen no permitido. Usá JPG, PNG o WEBP.")
    original = Path(filename or "card")
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", original.stem).strip("-")[:48] or "card"
    return f"{stem}-{secrets.token_hex(8)}{suffix}"


def validate_image_bytes(data: bytes, content_type: str) -> None:
    if content_type == "image/jpeg":
        valid = data.startswith(b"\xff\xd8\xff")
    elif content_type == "image/png":
        valid = data.startswith(b"\x89PNG\r\n\x1a\n")
    elif content_type == "image/webp":
        valid = data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP"
    else:
        valid = False
    if not valid:
        raise ValueError("El archivo no coincide con un JPG, PNG o WEBP válido.")
