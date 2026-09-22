from __future__ import annotations

from collections.abc import Callable

from aiogram import Bot
from aiogram.types import LabeledPrice

from app.api.dtos import InvoiceResponseDTO
from app.api.tma_auth import TmaAuthContext
from app.core.config import Settings


class TmaStarsService:
    """Telegram Stars invoice adapter for digital Mini App products.

    This service only creates invoices. Product fulfillment belongs to the
    Telegram payment-update path and must happen after a verified successful
    payment is persisted idempotently.
    """

    PRODUCTS: dict[str, tuple[int, str, str]] = {
        "premium_ticket": (10, "Ticket Premium", "Ticket Premium para WaifuMon"),
        "starter_pack": (25, "Starter Pack", "Pack inicial digital de WaifuMon"),
    }

    def __init__(
        self,
        settings: Settings,
        bot_factory: Callable[[str], Bot] | None = None,
    ) -> None:
        self.settings = settings
        self.bot_factory = bot_factory

    async def create_invoice_link(
        self,
        context: TmaAuthContext,
        *,
        product: str,
    ) -> InvoiceResponseDTO:
        if product not in self.PRODUCTS:
            raise ValueError(f"Unsupported Stars product: {product}")

        token = self.settings.token_for(self.settings.tma_bot_identity.value)
        if not token:
            raise RuntimeError("Telegram payment bot is not configured")

        amount, title, description = self.PRODUCTS[product]
        if product == "premium_ticket":
            amount = self.settings.tma_premium_ticket_price_stars
        elif product == "starter_pack":
            amount = self.settings.tma_starter_pack_price_stars
        if amount <= 0:
            raise RuntimeError(f"Invalid Stars price for {product}")

        payload = f"tma:{context.user.id}:{product}:{self._nonce()}"
        bot = self.bot_factory(token) if self.bot_factory is not None else Bot(token=token)
        try:
            invoice_link = await bot.create_invoice_link(
                title=title,
                description=description,
                payload=payload,
                currency="XTR",
                prices=[LabeledPrice(label=title, amount=amount)],
            )
        finally:
            await bot.session.close()

        return InvoiceResponseDTO(
            product=product,
            currency="XTR",
            amount=amount,
            invoice_link=invoice_link,
            payload=payload,
        )

    @staticmethod
    def _nonce() -> str:
        from secrets import token_hex

        return token_hex(16)

    async def handle_pre_checkout(self, update) -> bool:
        """Skeleton for future pre-checkout verification.

        The final implementation should validate the invoice payload/product and
        answer the Telegram pre-checkout query within Telegram's deadline.
        """
        raise NotImplementedError("pre_checkout handling is intentionally not enabled yet")

    async def handle_successful_payment(self, update) -> None:
        """Skeleton for idempotent digital-product fulfillment.

        The final implementation must persist Telegram's charge identifier
        before granting Tickets Premium or other digital inventory.
        """
        raise NotImplementedError("successful payment fulfillment is not enabled yet")
