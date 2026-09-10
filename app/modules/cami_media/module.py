from datetime import datetime
from html import escape

from aiogram import Bot, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.jobs import JobQueue
from app.core.module import BotModule
from app.core.identity import BotIdentity
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import FanRequest, MediaAsset, RequestStatus, User
from app.services.forum_topics import ForumTopicService
from app.ui.media_keyboards import cami_media_actions, cami_pending_requests, cami_publish_destination


class CamiMediaModule(BotModule):
    """Private media desk: classify, schedule, archive and fulfill fan requests."""

    name = "cami-media"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.jobs = JobQueue()
        self.topics = ForumTopicService(database)

    def setup(self) -> None:
        self.router.message.register(self.receive_photo, F.photo)
        self.router.message.register(self.receive_schedule_or_tags, F.text)
        self.router.callback_query.register(self.media_action, F.data.startswith("cami:media:"))
        self.router.callback_query.register(self.link_request, F.data.startswith("cami:req:link:"))

    async def receive_photo(self, message: Message) -> None:
        if message.chat.type != "private" or not message.photo:
            return
        photo = message.photo[-1]
        async with self.database.session() as session:
            asset = await session.scalar(select(MediaAsset).where(MediaAsset.telegram_file_id == photo.file_id))
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

    async def receive_schedule_or_tags(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None or not message.text:
            return
        async with self.database.session() as session:
            asset = await session.scalar(
                select(MediaAsset).where(
                    MediaAsset.source_chat_id == message.chat.id,
                    MediaAsset.status.in_(["needs_tag", "waiting_schedule"]),
                ).order_by(MediaAsset.id.desc())
            )
            if asset is None:
                return
            if asset.status == "needs_tag":
                parts = [part.strip() for part in message.text.split("|")]
                if len(parts) < 2:
                    await message.answer("🏷️ Usá <code>Personaje | Anime | tags | categoría</code>.")
                    return
                asset.character_id = parts[0].lower().replace(" ", "-")
                asset.anime = parts[1]
                asset.tags = ",".join(tag.strip().lower() for tag in (parts[2].split(",") if len(parts) > 2 else []))
                asset.category = parts[3] if len(parts) > 3 else "waifu"
                asset.status = "tagged"
                await session.commit()
                await message.answer("🏷️ Etiquetas guardadas. El material queda en la biblioteca para decidir su publicación.")
                return

            try:
                scheduled_at = datetime.strptime(message.text.strip(), "%d/%m/%Y %H:%M")
            except ValueError:
                await message.answer("🕒 Formato inválido. Ejemplo: <code>25/09/2026 21:30</code>.")
                return
            if scheduled_at <= datetime.utcnow():
                await message.answer("🕒 Esa fecha ya pasó. Elegí una fecha futura.")
                return
            asset.scheduled_at = scheduled_at
            asset.status = "scheduled"
            await session.commit()
            await self.jobs.enqueue(
                session,
                "media.publish",
                {"asset_id": asset.id, "destination": asset.publish_destination or "both"},
                dedupe_key=f"media-publish:{asset.id}:{scheduled_at.isoformat()}",
                run_at=scheduled_at,
            )
        await message.answer("🗓️ <b>Programado.</b> La orden quedó persistida para que sobreviva a un reinicio.")

    async def media_action(self, callback: CallbackQuery, bot: Bot) -> None:
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
            if asset.source_chat_id != callback.message.chat.id:
                await callback.answer("Ese material no pertenece a este chat.", show_alert=True)
                return

            if action == "tag":
                asset.status = "needs_tag"
                await session.commit()
                await callback.message.edit_text(
                    "🏷️ <b>Listo para etiquetar.</b>\nMandame:\n"
                    "<code>Asuna | Sword Art Online | cabello azul, uniforme | waifu</code>"
                )
                await callback.answer()
                return

            if action == "schedule":
                asset.status = "waiting_destination"
                await session.commit()
                await callback.message.edit_text(
                    "🗓️ ¿Dónde querés publicarlo?\n"
                    "<b>Página + tema del grupo</b> mantiene ambos con el mismo segmento.",
                    reply_markup=cami_publish_destination(asset_id),
                )
                await callback.answer()
                return

            if action == "request":
                requests = await session.scalars(
                    select(FanRequest).where(
                        FanRequest.status.in_([RequestStatus.PENDING_ADMIN.value, RequestStatus.PROCESSING.value])
                    ).order_by(FanRequest.created_at.asc()).limit(8)
                )
                pending = list(requests)
                if not pending:
                    await callback.answer("No hay pedidos pendientes.", show_alert=True)
                    return
                await callback.message.edit_text(
                    "📨 <b>¿A qué pedido corresponde esta imagen?</b>\n"
                    "Elegí el pedido; después la publicaré en <b>#pedidos</b> etiquetando al integrante."
                    ,
                    reply_markup=cami_pending_requests(
                        [(request.id, f"#{request.id} · {request.description}") for request in pending]
                    ),
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
                    "🕒 Decime cuándo querés enviarlo en formato <code>DD/MM/YYYY HH:MM</code>."
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

    async def link_request(self, callback: CallbackQuery, bot: Bot) -> None:
        if callback.message is None or callback.data is None or callback.message.chat.type != "private":
            await callback.answer("Acción inválida.", show_alert=True)
            return
        try:
            request_id = int(callback.data.rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer("Pedido inválido.", show_alert=True)
            return

        async with self.database.session() as session:
            asset = await session.scalar(
                select(MediaAsset).where(
                    MediaAsset.source_chat_id == callback.message.chat.id,
                    MediaAsset.status == "cami_inbox",
                ).order_by(MediaAsset.id.desc())
            )
            request = await session.get(FanRequest, request_id)
            if asset is None or request is None or request.status not in {
                RequestStatus.PENDING_ADMIN.value,
                RequestStatus.PROCESSING.value,
            }:
                await callback.answer("El material o pedido ya no está disponible.", show_alert=True)
                return
            asset.request_id = request.id
            asset.status = "request_ready"
            request.status = RequestStatus.PROCESSING.value
            await session.commit()
            request_user = await session.get(User, request.user_id)
            user_name = escape((request_user.first_name if request_user else "integrante") or "integrante")
            user_tag = f'<a href="tg://user?id={request.user_id}">{user_name}</a>'
            setup = await session.scalar(select(SetupSession).where(
                SetupSession.bot_identity == BotIdentity.CHIE.value,
                SetupSession.status == "configured",
            ).order_by(SetupSession.id.desc()))
            if setup is None:
                await callback.answer("Chie todavía no tiene un grupo configurado.", show_alert=True)
                return
            group_id = setup.chat_id

        thread_id = await self.topics.get_thread_id(group_id, "pedidos")
        if thread_id is None:
            await callback.answer("No encuentro el tema #pedidos.", show_alert=True)
            return
        try:
            await bot.send_photo(
                group_id,
                asset.telegram_file_id,
                message_thread_id=thread_id,
                caption=(
                    f"🎨 <b>Pedido #{request_id} completado</b>\n"
                    f"👤 {user_tag}\n"
                    f"📝 {escape(request.description)}\n\n"
                    "Cami dejó el pedido listo en su tema correspondiente."
                ),
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            async with self.database.session() as session:
                fresh = await session.get(FanRequest, request_id)
                if fresh:
                    fresh.status = RequestStatus.PENDING_ADMIN.value
                fresh_asset = await session.get(MediaAsset, asset.id)
                if fresh_asset:
                    fresh_asset.status = "cami_inbox"
                await session.commit()
            raise

        async with self.database.session() as session:
            fresh = await session.get(FanRequest, request_id)
            if fresh:
                fresh.status = RequestStatus.COMPLETED.value
                fresh.updated_at = datetime.utcnow()
            fresh_asset = await session.get(MediaAsset, asset.id)
            if fresh_asset:
                fresh_asset.status = "published_request"
            await session.commit()
        await callback.message.edit_text(
            f"✅ <b>Pedido #{request_id} enviado a #pedidos.</b>\n"
            "El integrante quedó etiquetado y el pedido pasó a completado."
        )
        await callback.answer("Pedido publicado.")
