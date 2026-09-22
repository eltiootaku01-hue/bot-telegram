from __future__ import annotations

import logging

from aiogram import F
from aiogram.types import Message, PreCheckoutQuery

from app.core.access import is_authorized_community
from app.core.config import Settings
from app.core.module import BotModule
from app.db.database import Database
from app.services.tma_payments import TmaPaymentError, TmaPaymentService

logger = logging.getLogger(__name__)


class TmaPaymentsModule(BotModule):
    """Telegram Stars checkout and exactly-once digital fulfillment."""

    name = "tma-payments"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or Settings()
        self.service = TmaPaymentService(self.settings)

    def setup(self) -> None:
        self.router.pre_checkout_query.register(self.pre_checkout)
        self.router.message.register(self.successful_payment, F.successful_payment)

    async def pre_checkout(self, query: PreCheckoutQuery) -> None:
        try:
            self.service.validate_checkout(
                payload=query.invoice_payload,
                user_id=query.from_user.id,
                currency=query.currency,
                amount=query.total_amount,
            )
            async with self.database.session() as session:
                chat_id = await self.service.community_id(session)
                if not is_authorized_community(self.settings, chat_id):
                    raise TmaPaymentError("La comunidad configurada no está autorizada.")
        except TmaPaymentError as exc:
            await query.answer(ok=False, error_message=str(exc)[:200])
            return
        await query.answer(ok=True)

    async def successful_payment(self, message: Message) -> None:
        payment = message.successful_payment
        user = message.from_user
        if payment is None or user is None:
            return

        try:
            async with self.database.session(write=True) as session:
                chat_id = await self.service.community_id(session)
                if not is_authorized_community(self.settings, chat_id):
                    raise TmaPaymentError("La comunidad configurada ya no está autorizada.")

                purchase = await self.service.fulfill(
                    session,
                    user_id=user.id,
                    first_name=user.first_name or "Telegram user",
                    last_name=user.last_name,
                    username=user.username,
                    payload=payment.invoice_payload,
                    currency=payment.currency,
                    amount=payment.total_amount,
                    telegram_payment_charge_id=payment.telegram_payment_charge_id,
                    provider_payment_charge_id=payment.provider_payment_charge_id,
                    chat_id=chat_id,
                )
        except TmaPaymentError as exc:
            logger.exception(
                "Stars payment requires review user=%s charge=%s",
                user.id,
                payment.telegram_payment_charge_id,
            )
            await message.answer(
                "⚠️ Telegram confirmó tu pago, pero la entrega automática quedó retenida "
                "para revisión. El cobro no se vuelve a procesar."
            )
            return

        product_label = (
            "Ticket Premium" if purchase.product == "premium_ticket" else "Starter Pack"
        )
        await message.answer(
            f"✅ <b>Compra confirmada</b>\n"
            f"{product_label} · {purchase.amount} ⭐\n"
            "La recompensa digital ya quedó registrada en tu cuenta."
        )
