from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.card_vault.contracts import CardRegistration, CardRarity, CardInventoryView, TransactionResult
from app.core.time import utc_now
from app.db.card_vault_models import CardInventory, CardHolderType, TransactionHistory
from app.db.models import CardDefinition


class CardVaultService:
    """Authoritative local service for card definitions, assets, inventory and audit."""

    CARD_CODE_RE = re.compile(r"^#\d{3,6}$")

    def __init__(
        self,
        asset_root: str | Path = "data/card_assets",
        thumbnail_root: str | Path = "data/card_thumbnails",
    ) -> None:
        self.asset_root = Path(asset_root)
        self.thumbnail_root = Path(thumbnail_root)

    def _validate_registration(self, card: CardRegistration) -> None:
        if not self.CARD_CODE_RE.fullmatch(card.card_code):
            raise ValueError("card_code must use the standardized form #001")
        if not card.card_id.strip():
            raise ValueError("card_id is required")
        if card.collection_points < 0:
            raise ValueError("collection_points must be nonnegative")
        if not card.asset_path.is_file():
            raise FileNotFoundError(card.asset_path)
        try:
            with Image.open(card.asset_path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("asset_path is not a valid image") from exc

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _store_asset(self, card: CardRegistration) -> tuple[Path, Path, str]:
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.thumbnail_root.mkdir(parents=True, exist_ok=True)

        source = card.asset_path.resolve()
        extension = source.suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("card assets must be JPG, PNG or WEBP")
        safe_name = f"{card.card_code[1:]}_{card.card_id.replace('/', '_')}{extension}"
        target = self.asset_root / safe_name
        shutil.copy2(source, target)

        thumbnail = self.thumbnail_root / f"{target.stem}.webp"
        with Image.open(target) as image:
            image = image.convert("RGB")
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            image.save(thumbnail, "WEBP", quality=88, method=6)
        return target, thumbnail, self._sha256(target)

    async def register_card(
        self,
        session: AsyncSession,
        card: CardRegistration,
        *,
        telegram_protected: bool = True,
    ) -> CardDefinition:
        self._validate_registration(card)
        target, thumbnail, digest = self._store_asset(card)

        definition = CardDefinition(
            id=card.card_id,
            card_code=card.card_code,
            character_id=card.character_id,
            character_name=card.character_name,
            anime_origin=card.anime_origin,
            rarity=card.rarity.value,
            image_url="",
            asset_path=str(target),
            thumbnail_path=str(thumbnail),
            asset_sha256=digest,
            source_provider=card.source_provider,
            collection_points=card.collection_points,
            coin_value=card.coin_value,
            telegram_protected=telegram_protected,
            active=True,
            updated_at=utc_now(),
        )
        session.add(definition)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ValueError(f"card_id or card_code already exists: {card.card_id}") from exc
        return definition

    async def get_card(self, session: AsyncSession, card_id: str) -> CardDefinition | None:
        return await session.get(CardDefinition, card_id)

    async def inventory(
        self,
        session: AsyncSession,
        *,
        holder_type: CardHolderType,
        holder_key: str,
    ) -> list[CardInventoryView]:
        rows = await session.execute(
            select(CardInventory, CardDefinition)
            .join(CardDefinition, CardDefinition.id == CardInventory.card_id)
            .where(
                CardInventory.holder_type == holder_type.value,
                CardInventory.holder_key == holder_key,
                CardDefinition.active.is_(True),
            )
            .order_by(CardDefinition.card_code.asc())
        )
        return [
            CardInventoryView(
                card_id=inventory.card_id,
                card_code=definition.card_code or "",
                quantity=inventory.quantity,
                locked_quantity=inventory.locked_quantity,
                available_quantity=inventory.quantity - inventory.locked_quantity,
                holder_type=inventory.holder_type,
                holder_key=inventory.holder_key,
            )
            for inventory, definition in rows.all()
        ]

    async def adjust_inventory(
        self,
        session: AsyncSession,
        *,
        card_id: str,
        holder_type: CardHolderType,
        holder_key: str,
        delta: int,
        user_id: int | None = None,
        lock_delta: int = 0,
    ) -> CardInventory:
        if delta == 0 and lock_delta == 0:
            raise ValueError("inventory adjustment cannot be zero")
        existing = await session.scalar(
            select(CardInventory).where(
                CardInventory.holder_type == holder_type.value,
                CardInventory.holder_key == holder_key,
                CardInventory.card_id == card_id,
            )
        )
        if existing is None:
            if delta < 0 or lock_delta < 0:
                raise ValueError("cannot remove an absent card")
            existing = CardInventory(
                card_id=card_id,
                holder_type=holder_type.value,
                holder_key=holder_key,
                user_id=user_id,
                quantity=delta,
                locked_quantity=lock_delta,
            )
            session.add(existing)
            await session.flush()
            return existing

        new_quantity = existing.quantity + delta
        new_locked = existing.locked_quantity + lock_delta
        if new_quantity < 0 or new_locked < 0 or new_locked > new_quantity:
            raise ValueError("card inventory would become negative or over-locked")
        existing.quantity = new_quantity
        existing.locked_quantity = new_locked
        existing.updated_at = utc_now()
        await session.flush()
        return existing

    async def transfer(
        self,
        session: AsyncSession,
        *,
        card_id: str,
        from_type: CardHolderType,
        from_key: str,
        to_type: CardHolderType,
        to_key: str,
        quantity: int,
        actor_user_id: int | None,
        reference_id: str,
    ) -> TransactionResult:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        idem = f"card-transfer:{reference_id}"
        previous = await session.scalar(
            select(TransactionHistory).where(TransactionHistory.idempotency_key == idem)
        )
        if previous is not None:
            return TransactionResult(
                previous.id,
                previous.idempotency_key,
                previous.coin_delta,
                previous.card_delta,
            )

        await self.adjust_inventory(
            session,
            card_id=card_id,
            holder_type=from_type,
            holder_key=from_key,
            delta=-quantity,
        )
        await self.adjust_inventory(
            session,
            card_id=card_id,
            holder_type=to_type,
            holder_key=to_key,
            delta=quantity,
        )
        row = TransactionHistory(
            idempotency_key=idem,
            transaction_type="card_transfer",
            actor_user_id=actor_user_id,
            card_id=card_id,
            quantity=quantity,
            coin_delta=0,
            card_delta=-quantity,
            source="card_vault",
            reference_type="transfer",
            reference_id=reference_id,
            metadata_json=f'{{"from":"{from_type.value}:{from_key}","to":"{to_type.value}:{to_key}"}}',
        )
        session.add(row)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ValueError("transfer raced with another operation") from exc
        return TransactionResult(row.id, row.idempotency_key, 0, -quantity)

    async def record_coins(
        self,
        session: AsyncSession,
        *,
        actor_user_id: int | None,
        target_user_id: int | None,
        coin_delta: int,
        reason: str,
        idempotency_key: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> TransactionResult:
        if coin_delta == 0:
            raise ValueError("coin_delta cannot be zero")
        previous = await session.scalar(
            select(TransactionHistory).where(
                TransactionHistory.idempotency_key == idempotency_key
            )
        )
        if previous is not None:
            return TransactionResult(
                previous.id,
                previous.idempotency_key,
                previous.coin_delta,
                previous.card_delta,
            )
        row = TransactionHistory(
            idempotency_key=idempotency_key,
            transaction_type=reason,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            coin_delta=coin_delta,
            card_delta=0,
            source="card_vault",
            reference_type=reference_type,
            reference_id=reference_id,
        )
        session.add(row)
        await session.flush()
        return TransactionResult(row.id, row.idempotency_key, coin_delta, 0)
