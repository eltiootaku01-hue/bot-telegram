from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utc_now
from app.db.models import Chat, GameItemInventory, GameProfile, TmaStarPurchase, User


PAYLOAD_PREFIX = "tma"
PRODUCT_REWARDS: dict[str, dict[str, int]] = {
    "premium_ticket": {"premium_ticket": 1},
    "starter_pack": {"premium_ticket": 3, "coins": 250},
}


@dataclass(frozen=True, slots=True)
class PaymentPayload:
    user_id: int
    product: str
    nonce: str


class TmaPaymentError(ValueError):
    """Raised when a Telegram Stars payment cannot be validated or fulfilled."""


def parse_payload(payload: str) -> PaymentPayload:
    parts = payload.split(":")
    if len(parts) != 4 or parts[0] != PAYLOAD_PREFIX:
        raise TmaPaymentError("Invalid Telegram Stars invoice payload")
    try:
        user_id = int(parts[1])
    except ValueError as exc:
        raise TmaPaymentError("Invoice payload user id is invalid") from exc
    nonce = parts[3]
    if user_id <= 0 or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise TmaPaymentError("Invoice payload nonce is invalid")
    if parts[2] not in PRODUCT_REWARDS:
        raise TmaPaymentError("Invoice payload product is invalid")
    return PaymentPayload(user_id=user_id, product=parts[2], nonce=nonce)


class TmaPaymentService:
    """Validate Stars payments and deliver digital entitlements exactly once."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def expected_price(self, product: str) -> int:
        if product == "premium_ticket":
            return self.settings.tma_premium_ticket_price_stars
        if product == "starter_pack":
            return self.settings.tma_starter_pack_price_stars
        raise TmaPaymentError("Unknown Stars product")

    def validate_checkout(
        self,
        *,
        payload: str,
        user_id: int,
        currency: str,
        amount: int,
    ) -> PaymentPayload:
        parsed = parse_payload(payload)
        if parsed.user_id != user_id:
            raise TmaPaymentError("Invoice does not belong to this Telegram user")
        if currency != "XTR":
            raise TmaPaymentError("Telegram Stars currency must be XTR")
        expected = self.expected_price(parsed.product)
        if expected <= 0 or amount != expected:
            raise TmaPaymentError("Invoice amount does not match configured product price")
        return parsed

    async def community_id(self, session: AsyncSession) -> int:
        from app.db.community_models import SetupSession

        setup = await session.scalar(
            select(SetupSession.chat_id)
            .where(
                SetupSession.bot_identity == "chie",
                SetupSession.status == "configured",
            )
            .order_by(SetupSession.id.desc())
        )
        if setup is None:
            raise TmaPaymentError("No configured Telegram community")
        return int(setup)

    async def fulfill(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        first_name: str,
        last_name: str | None,
        username: str | None,
        payload: str,
        currency: str,
        amount: int,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
        chat_id: int,
    ) -> TmaStarPurchase:
        parsed = self.validate_checkout(
            payload=payload,
            user_id=user_id,
            currency=currency,
            amount=amount,
        )
        if not telegram_payment_charge_id.strip():
            raise TmaPaymentError("Telegram payment charge id is missing")

        existing = await session.scalar(
            select(TmaStarPurchase).where(
                TmaStarPurchase.telegram_payment_charge_id == telegram_payment_charge_id
            )
        )
        if existing is not None:
            if (
                existing.user_id != user_id
                or existing.product != parsed.product
                or existing.amount != amount
                or existing.currency != currency
                or existing.invoice_payload != payload
            ):
                raise TmaPaymentError("Telegram charge id was reused with conflicting data")
            return existing

        session.add(
            User(
                id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
            )
        )
        try:
            async with session.begin_nested():
                await session.flush()
        except IntegrityError:
            pass

        user = await session.get(User, user_id)
        if user is not None:
            user.first_name = first_name
            user.last_name = last_name
            user.username = username

        community = await session.get(Chat, chat_id)
        if community is None:
            session.add(Chat(id=chat_id, type="supergroup"))

        profile = await session.scalar(
            select(GameProfile).where(
                GameProfile.user_id == user_id,
                GameProfile.chat_id == chat_id,
            )
        )
        if profile is None:
            profile = GameProfile(user_id=user_id, chat_id=chat_id)
            try:
                async with session.begin_nested():
                    session.add(profile)
                    await session.flush()
            except IntegrityError:
                profile = await session.scalar(
                    select(GameProfile).where(
                        GameProfile.user_id == user_id,
                        GameProfile.chat_id == chat_id,
                    )
                )
        if profile is None:
            raise TmaPaymentError("Could not create game profile")

        purchase = TmaStarPurchase(
            user_id=user_id,
            chat_id=chat_id,
            product=parsed.product,
            currency=currency,
            amount=amount,
            invoice_payload=payload,
            telegram_payment_charge_id=telegram_payment_charge_id,
            provider_payment_charge_id=provider_payment_charge_id,
        )
        try:
            async with session.begin_nested():
                session.add(purchase)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(TmaStarPurchase).where(
                    TmaStarPurchase.telegram_payment_charge_id == telegram_payment_charge_id
                )
            )
            if existing is None:
                raise
            return existing

        claimed = await session.execute(
            update(TmaStarPurchase)
            .where(
                TmaStarPurchase.id == purchase.id,
                TmaStarPurchase.fulfilled.is_(False),
            )
            .values(fulfilled=True, fulfilled_at=utc_now())
        )
        if claimed.rowcount != 1:
            stored = await session.get(TmaStarPurchase, purchase.id)
            if stored is None:
                raise TmaPaymentError("Payment purchase disappeared")
            return stored

        for item_key, quantity in PRODUCT_REWARDS[parsed.product].items():
            current = await session.scalar(
                select(GameItemInventory).where(
                    GameItemInventory.profile_id == profile.id,
                    GameItemInventory.item_key == item_key,
                )
            )
            if current is None:
                current = GameItemInventory(
                    profile_id=profile.id,
                    item_key=item_key,
                    quantity=quantity,
                )
                try:
                    async with session.begin_nested():
                        session.add(current)
                        await session.flush()
                except IntegrityError:
                    current = await session.scalar(
                        select(GameItemInventory).where(
                            GameItemInventory.profile_id == profile.id,
                            GameItemInventory.item_key == item_key,
                        )
                    )
                    if current is None:
                        raise
                else:
                    continue

            await session.execute(
                update(GameItemInventory)
                .where(GameItemInventory.id == current.id)
                .values(
                    quantity=GameItemInventory.quantity + quantity,
                    updated_at=utc_now(),
                )
            )

        return purchase
