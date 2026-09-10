from datetime import datetime

from aiogram import F
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.module import BotModule
from app.db.database import Database
from app.db.models import MediaAsset
from app.ui.media_keyboards import cami_media_actions, cami_publish_destination


class CamiMediaModule(BotModule):
    """Private media desk: classify, schedule or archive an image without AI calls."""

    name = "cami-media"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database

    def setup(self) -> None:
        self.router.message.register(self.receive_photo, F.photo)
        self.router.callback_query.register(self.media_action, F.data.startswith("cami:media:"))

    async def receive_photo(self, message: Message) -> None:
        if message.chat.type != "private" or not message.photo:
            return
        photo = message.photo[-1]
        async with self.database.session() as session:
            asset = await session.scalar(
                select(MediaAsset).where(MediaAsset.telegram_file_id == photo.file_id)
            )
            if asset is None:
                asset = MediaAsset(
                    telegram_file_id=photo.file_id,
                    telegram_unique_id=photo.file_unique_id,
                    source_chat_id=message.chat.id,
                    source_message_id=message.message_id,
                    media_type="photo",
                    status="cami_inbox",
                )
                session.add(asset)
                await session.flush()
            asset_id = asset.id
            await session.commit()

        await message.answer(
            "🗂️ <b>Recibido.</b> ¿Qué querés que haga con este material?",
            reply_markup=cami_media_actions(asset_id),
        )

    async def media_action(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.data is None:
            await callback.answer("Acción inválida.", show_alert=True)
            return
        parts = callback.data.split(":")
        if len(parts) < 4:
            await callback.answer("Acción inválida.", show_alert=True)
            return
        action = parts[2]
        try:
            asset_id = int(parts[-1])
        except ValueError:
            await callback.answer("Material inválido.", show_alert=True)
            return

        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            if asset is None:
                await callback.answer("No encuentro ese material.", show_alert=True)
                return

            if action == "tag":
                asset.status = "needs_tag"
                await session.commit()
                await callback.message.edit_text(
                    "🏷️ <b>Listo para etiquetar.</b>\n"
                    "Mandame en un mensaje algo como:\n"
                    "<code>Asuna | Sword Art Online | cabello azul, uniforme | waifu</code>"
                )
                await callback.answer()
                return

            if action == "schedule":
                asset.status = "waiting_destination"
                await session.commit()
                await callback.message.edit_text(
                    "🗓️ ¿Dónde querés publicarlo?\n"
                    "La opción <b>Página + tema del grupo</b> mantiene ambos con el mismo segmento. ",
                    reply_markup=cami_publish_destination(asset_id),
                )
                await callback.answer()
                return

            if action == "archive":
                asset.status = "archived"
                await session.commit()
                await callback.message.edit_text("📦 Archivado. No se publicará.")
                await callback.answer()
                return

            if action == "dest":
                destination = parts[3]
                if destination not in {"both", "group"}:
                    await callback.answer("Destino inválido.", show_alert=True)
                    return
                asset.publish_destination = destination
                asset.publish_page = destination == "both"
                asset.publish_group = True
                asset.status = "waiting_schedule"
                await session.commit()
                await callback.message.edit_text(
                    "🕒 Decime cuándo querés enviarlo en formato "
                    "<code>DD/MM/YYYY HH:MM</code>.\n"
                    "Todavía no publico nada: primero dejo la orden persistida."
                )
                await callback.answer()
                return

            if action == "cancel":
                asset.status = "cami_inbox"
                await session.commit()
                await callback.message.edit_text(
                    "↩️ Cancelado. El material vuelve a la bandeja de Cami.",
                    reply_markup=cami_media_actions(asset_id),
                )
                await callback.answer()
                return

        await callback.answer("Acción no implementada.", show_alert=True)
