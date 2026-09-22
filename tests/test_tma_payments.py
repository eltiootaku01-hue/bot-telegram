from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.models import Chat, GameItemInventory, TmaStarPurchase
from app.services.tma_payments import (
    TmaPaymentError,
    TmaPaymentService,
    parse_payload,
)


def test_parse_payload_extracts_signed_invoice_metadata() -> None:
    parsed = parse_payload("tma:777:premium_ticket:0123456789abcdef0123456789abcdef")
    assert parsed.user_id == 777
    assert parsed.product == "premium_ticket"
    assert parsed.nonce == "0123456789abcdef0123456789abcdef"


def test_validate_checkout_rejects_wrong_user_currency_or_price() -> None:
    service = TmaPaymentService(
        Settings(
            tma_premium_ticket_price_stars=10,
            tma_starter_pack_price_stars=25,
        )
    )
    payload = "tma:777:premium_ticket:0123456789abcdef0123456789abcdef"

    with pytest.raises(TmaPaymentError, match="user"):
        service.validate_checkout(
            payload=payload,
            user_id=778,
            currency="XTR",
            amount=10,
        )
    with pytest.raises(TmaPaymentError, match="XTR"):
        service.validate_checkout(
            payload=payload,
            user_id=777,
            currency="USD",
            amount=10,
        )
    with pytest.raises(TmaPaymentError, match="amount"):
        service.validate_checkout(
            payload=payload,
            user_id=777,
            currency="XTR",
            amount=11,
        )


@pytest.mark.asyncio
async def test_fulfill_is_idempotent_by_telegram_charge_id() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    async with database.session() as session:
        session.add(Chat(id=-100123, type="supergroup", title="Test"))
    
    service = TmaPaymentService(Settings(tma_premium_ticket_price_stars=10))

    payload = "tma:777:premium_ticket:0123456789abcdef0123456789abcdef"
    async with database.session(write=True) as session:
        first = await service.fulfill(
            session,
            user_id=777,
            first_name="Johan",
            last_name=None,
            username="tester",
            payload=payload,
            currency="XTR",
            amount=10,
            telegram_payment_charge_id="charge-1",
            provider_payment_charge_id=None,
            chat_id=-100123,
        )

    async with database.session(write=True) as session:
        second = await service.fulfill(
            session,
            user_id=777,
            first_name="Johan",
            last_name=None,
            username="tester",
            payload=payload,
            currency="XTR",
            amount=10,
            telegram_payment_charge_id="charge-1",
            provider_payment_charge_id=None,
            chat_id=-100123,
        )

    assert first.id == second.id
    assert second.fulfilled is True

    async with database.session() as session:
        purchases = list(await session.scalars(TmaStarPurchase.__table__.select()))
        items = list(
            await session.scalars(
                GameItemInventory.__table__.select().where(
                    GameItemInventory.item_key == "premium_ticket"
                )
            )
        )

    assert len(purchases) == 1
    assert len(items) == 1
    assert items[0].quantity == 1

    await database.close()


@pytest.mark.asyncio
async def test_same_invoice_payload_can_be_paid_again_with_new_charge_id() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    async with database.session() as session:
        session.add(Chat(id=-100123, type="supergroup", title="Test"))

    service = TmaPaymentService(Settings(tma_premium_ticket_price_stars=10))
    payload = "tma:777:premium_ticket:0123456789abcdef0123456789abcdef"

    for charge_id in ("charge-1", "charge-2"):
        async with database.session(write=True) as session:
            await service.fulfill(
                session,
                user_id=777,
                first_name="Johan",
                last_name=None,
                username="tester",
                payload=payload,
                currency="XTR",
                amount=10,
                telegram_payment_charge_id=charge_id,
                provider_payment_charge_id=None,
                chat_id=-100123,
            )

    async with database.session() as session:
        purchases = list(await session.scalars(TmaStarPurchase.__table__.select()))
        items = list(
            await session.scalars(
                GameItemInventory.__table__.select().where(
                    GameItemInventory.item_key == "premium_ticket"
                )
            )
        )

    assert len(purchases) == 2
    assert len(items) == 1
    assert items[0].quantity == 2

    await database.close()
