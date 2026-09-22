from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.community_models import SetupSession
from app.db.models import Chat, GameItemInventory, GameProfile, TmaStarPurchase
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
        purchases = list(await session.scalars(select(TmaStarPurchase)))
        items = list(
            await session.scalars(
                select(GameItemInventory).where(
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
        purchases = list(await session.scalars(select(TmaStarPurchase)))
        items = list(
            await session.scalars(
                select(GameItemInventory).where(
                    GameItemInventory.item_key == "premium_ticket"
                )
            )
        )

    assert len(purchases) == 2
    assert len(items) == 1
    assert items[0].quantity == 2

    await database.close()



@pytest.mark.asyncio
async def test_starter_pack_credits_tickets_and_coins() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    async with database.session() as session:
        session.add(Chat(id=-100123, type="supergroup", title="Test"))

    service = TmaPaymentService(
        Settings(
            tma_premium_ticket_price_stars=10,
            tma_starter_pack_price_stars=25,
        )
    )
    payload = "tma:888:starter_pack:fedcba9876543210fedcba9876543210"

    async with database.session(write=True) as session:
        await service.fulfill(
            session,
            user_id=888,
            first_name="Buyer",
            last_name=None,
            username="buyer",
            payload=payload,
            currency="XTR",
            amount=25,
            telegram_payment_charge_id="starter-charge-1",
            provider_payment_charge_id=None,
            chat_id=-100123,
        )

    async with database.session() as session:
        profile = await session.scalar(
            select(GameProfile).where(
                GameProfile.user_id == 888,
                GameProfile.chat_id == -100123,
            )
        )
        tickets = await session.scalar(
            select(GameItemInventory).where(
                GameItemInventory.profile_id == profile.id,
                GameItemInventory.item_key == "premium_ticket",
            )
        )

    assert profile is not None
    assert profile.coins == 250
    assert tickets is not None
    assert tickets.quantity == 3

    await database.close()


@pytest.mark.asyncio
async def test_payment_updates_validate_then_fulfill_once() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.modules.tma_payments.module import TmaPaymentsModule

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as session:
        session.add(Chat(id=-100123, type="supergroup", title="Test"))
        session.add(
            SetupSession(
                user_id=1,
                chat_id=-100123,
                bot_identity="chie",
                status="configured",
            )
        )

    settings = Settings(
        authorized_chat_ids="-100123",
        tma_premium_ticket_price_stars=10,
    )
    module = TmaPaymentsModule(database, settings)

    checkout = SimpleNamespace(
        invoice_payload="tma:777:premium_ticket:0123456789abcdef0123456789abcdef",
        from_user=SimpleNamespace(id=777),
        currency="XTR",
        total_amount=10,
        answer=AsyncMock(),
    )
    await module.pre_checkout(checkout)
    checkout.answer.assert_awaited_once_with(ok=True)

    message = SimpleNamespace(
        from_user=SimpleNamespace(
            id=777,
            first_name="Johan",
            last_name=None,
            username="tester",
        ),
        successful_payment=SimpleNamespace(
            invoice_payload=checkout.invoice_payload,
            currency="XTR",
            total_amount=10,
            telegram_payment_charge_id="charge-module-1",
            provider_payment_charge_id=None,
        ),
        answer=AsyncMock(),
    )
    await module.successful_payment(message)
    assert "Compra confirmada" in message.answer.await_args.args[0]

    await module.successful_payment(message)

    async with database.session() as session:
        purchases = list(await session.scalars(select(TmaStarPurchase)))
        items = list(
            await session.scalars(
                select(GameItemInventory).where(
                    GameItemInventory.item_key == "premium_ticket"
                )
            )
        )

    assert len(purchases) == 1
    assert items[0].quantity == 1
    await database.close()
