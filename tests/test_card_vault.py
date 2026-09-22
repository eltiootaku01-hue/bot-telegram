from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.card_vault.contracts import CardRegistration, CardRarity
from app.card_vault.service import CardVaultService
from app.db.card_vault_models import CardHolderType, CardInventory, TransactionHistory
from app.db.database import Database
from app.db.models import CardDefinition


@pytest.fixture
async def database(tmp_path: Path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'vault.db'}")
    await database.create_schema()
    yield database
    await database.close()


def make_png(path: Path) -> None:
    image = Image.new("RGB", (1200, 800), "white")
    image.save(path, "PNG")


@pytest.mark.asyncio
async def test_register_card_stores_original_and_thumbnail(database: Database, tmp_path: Path) -> None:
    source = tmp_path / "rei.png"
    make_png(source)
    service = CardVaultService(tmp_path / "assets", tmp_path / "thumbs")

    async with database.session() as session:
        card = await service.register_card(
            session,
            CardRegistration(
                card_id="rei-001",
                card_code="#001",
                character_id="rei-ayanami",
                character_name="Rei Ayanami",
                anime_origin="Neon Genesis Evangelion",
                rarity=CardRarity.R,
                asset_path=source,
                collection_points=5,
                custom_emoji_id="premium-emoji-1",
            ),
        )

    assert card.card_code == "#001"
    assert card.coin_value == 5
    assert card.telegram_protected is True
    assert card.custom_emoji_id == "premium-emoji-1"
    assert card.asset_path is not None and Path(card.asset_path).is_file()
    assert card.thumbnail_path is not None and Path(card.thumbnail_path).is_file()
    assert card.asset_sha256


@pytest.mark.asyncio
async def test_inventory_transfer_is_idempotent(database: Database, tmp_path: Path) -> None:
    source = tmp_path / "asuna.png"
    make_png(source)
    service = CardVaultService(tmp_path / "assets", tmp_path / "thumbs")

    async with database.session() as session:
        await service.register_card(
            session,
            CardRegistration(
                card_id="asuna-001",
                card_code="#002",
                character_id="asuna",
                character_name="Asuna",
                anime_origin="Sword Art Online",
                rarity=CardRarity.SSR,
                asset_path=source,
            ),
        )
        await service.adjust_inventory(
            session,
            card_id="asuna-001",
            holder_type=CardHolderType.BANK,
            holder_key="main-bank",
            delta=3,
        )

    async with database.session() as session:
        first = await service.transfer(
            session,
            card_id="asuna-001",
            from_type=CardHolderType.BANK,
            from_key="main-bank",
            to_type=CardHolderType.USER,
            to_key="42",
            quantity=2,
            actor_user_id=42,
            reference_id="roll:100",
        )

    async with database.session() as session:
        second = await service.transfer(
            session,
            card_id="asuna-001",
            from_type=CardHolderType.BANK,
            from_key="main-bank",
            to_type=CardHolderType.USER,
            to_key="42",
            quantity=2,
            actor_user_id=42,
            reference_id="roll:100",
        )

    assert first == second

    async with database.session() as session:
        bank = await session.scalar(
            select(CardInventory).where(
                CardInventory.holder_type == CardHolderType.BANK.value,
                CardInventory.holder_key == "main-bank",
            )
        )
        user = await session.scalar(
            select(CardInventory).where(
                CardInventory.holder_type == CardHolderType.USER.value,
                CardInventory.holder_key == "42",
            )
        )

    assert bank is not None and bank.quantity == 1
    assert user is not None and user.quantity == 2


@pytest.mark.asyncio
async def test_transaction_history_is_append_only(database: Database) -> None:
    async with database.session() as session:
        row = TransactionHistory(
            idempotency_key="manual:1",
            transaction_type="card_mint",
            coin_delta=1,
            source="test",
        )
        session.add(row)
        await session.flush()

    with pytest.raises(IntegrityError):
        async with database.session() as session:
            await session.execute(
                TransactionHistory.__table__.update()
                .where(TransactionHistory.idempotency_key == "manual:1")
                .values(source="tampered")
            )

    async with database.session() as session:
        stored = await session.scalar(
            select(TransactionHistory).where(
                TransactionHistory.idempotency_key == "manual:1"
            )
        )

    assert stored is not None
    assert stored.source == "test"
