from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from html import escape

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update

from app.core.access import is_authorized_community
from app.media.library import MediaLibrary
from app.services.anime_catalog import AnimeCatalogService
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity
from app.core.jobs import JobQueue
from app.core.module import BotModule
from app.core.time import local_to_utc, utc_now
from app.services.community import CommunityResolver
from app.services.requests import RequestService
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import FanRequest, MediaAsset, RequestStatus
from app.services.forum_topics import ForumTopicService
from app.services.world import WorldService
from app.ui.media_keyboards import (
    cami_media_actions,
    cami_pending_requests,
    cami_publish_destination,
    cami_publication_recovery,
)

logger = logging.getLogger(__name__)


class CamiMediaStates(StatesGroup):
    waiting_tags = State()
    waiting_schedule = State()


class CamiMediaModule(BotModule):
    """Private media desk: classify, schedule, archive and fulfill fan requests."""

    name = "cami-media"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.jobs = JobQueue()
        self.topics = ForumTopicService(database)
        self.settings = settings or get_settings()
        self.world = WorldService()
        self.community = CommunityResolver(self.settings)
        self.anime = AnimeCatalogService()
        self.library = MediaLibrary()
        self.requests = RequestService()

    async def _observe_action(
        self,
        action_key: str,
        user_id: int,
        chat_id: int | None = None,
    ) -> None:
        """Record Cami usage without affecting the main workflow."""
        try:
            async with self.database.session() as session:
                await self.world.observe_action(
                    session,
                    bot_identity=BotIdentity.CAMI,
                    action_key=action_key,
                    user_id=user_id,
                    chat_id=chat_id,
                )
        except Exception:
            logger.exception("World observation failed for Cami action=%s user=%s", action_key, user_id)

    def setup(self) -> None:
        self.router.message.register(self.receive_photo, F.photo)
        self.router.message.register(self.recovery_command, Command("recuperar_publicaciones"))
        self.router.message.register(self.catalog_command, Command("catalogo"))
        self.router.message.register(self.anime_command, Command("anime"))
        self.router.message.register(self.anime_detail_command, Command("anime_ficha"))
        self.router.message.register(self.request_queue_command, Command("cola_pedidos"))
        self.router.message.register(self.media_queue_command, Command("cola_media"))
        self.router.message.register(
            self.receive_schedule_or_tags,
            CamiMediaStates.waiting_tags,
            CamiMediaStates.waiting_schedule,
        )
        self.router.callback_query.register(self.media_action, F.data.startswith("cami:media:"))
        self.router.callback_query.register(self.link_request, F.data.startswith("cami:req:link:"))
        self.router.callback_query.register(self.recover_publication, F.data.startswith("cami:recovery:"))

    def _is_media_staff(self, message: Message, *, user_id: int | None = None) -> bool:
        """Only the explicitly configured owner may operate Cami's private media desk."""
        actor_id = user_id if user_id is not None else (
            message.from_user.id if message.from_user is not None else None
        )
        return bool(
            message.chat.type == "private"
            and self.settings.master_user_id
            and actor_id == self.settings.master_user_id
        )

    async def receive_photo(self, message: Message, state: FSMContext) -> None:
        if not self._is_media_staff(message) or not message.photo:
            return
        photo = message.photo[-1]
        await state.clear()
        async with self.database.session() as session:
            asset = await self.library.find_existing(
                session,
                telegram_file_id=photo.file_id,
                telegram_unique_id=photo.file_unique_id,
                source_chat_id=message.chat.id,
                source_message_id=message.message_id,
            )
            created = asset is None
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
            elif asset.telegram_file_id != photo.file_id:
                asset.telegram_file_id = photo.file_id
                await session.flush()
            asset_id = asset.id

        if created:
            text = "🗂️ <b>Recibido.</b> ¿Qué querés que haga con este material?"
        else:
            text = (
                f"♻️ <b>Este material ya estaba en la biblioteca como #{asset_id}.</b>\n"
                "No se creó un duplicado; podés continuar trabajando sobre el registro existente."
            )
        await message.answer(text, reply_markup=cami_media_actions(asset_id))
        await self._observe_action("media_ingest" if created else "media_duplicate", message.from_user.id)

    async def receive_schedule_or_tags(self, message: Message, state: FSMContext) -> None:
        if not self._is_media_staff(message) or not message.text:
            return
        data = await state.get_data()
        asset_id = data.get("asset_id")
        if not isinstance(asset_id, int):
            return
        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            if (
                asset is None
                or asset.source_chat_id != message.chat.id
                or asset.status not in {"needs_tag", "waiting_schedule"}
            ):
                await state.clear()
                return
            if asset.status == "needs_tag":
                parts = [part.strip() for part in message.text.split("|")]
                if len(parts) < 2:
                    await message.answer("🏷️ Usá <code>Personaje | Anime | tags | categoría</code>.")
                    return
                asset.character_id = parts[0].lower().replace(" ", "-")
                asset.anime = parts[1]
                asset.tags = ",".join(
                    tag.strip().lower() for tag in (parts[2].split(",") if len(parts) > 2 else [])
                )
                asset.category = parts[3] if len(parts) > 3 else "waifu"
                asset.status = "tagged"
                await self.anime.upsert_work(
                    session,
                    work_id=f"media:{hashlib.sha256(asset.anime.casefold().encode("utf-8")).hexdigest()}",
                    title=asset.anime,
                    status="unverified",
                    notes=(
                        "Derivado del catálogo de medios; requiere verificación antes de tratarlo como ficha factual.",
                    ),
                )
                await session.commit()
                await message.answer(
                    "🏷️ Etiquetas guardadas. El material queda en la biblioteca para decidir su publicación."
                )
                await self._observe_action("media_tag", message.from_user.id)
                await state.clear()
                return

            try:
                scheduled_at = local_to_utc(
                    datetime.strptime(message.text.strip(), "%d/%m/%Y %H:%M"),
                    self.settings.bot_world_timezone,
                )
            except ValueError:
                await message.answer("🕒 Formato inválido. Ejemplo: <code>25/09/2026 21:30</code>.")
                return
            if scheduled_at <= utc_now():
                await message.answer("🕒 Esa fecha ya pasó. Elegí una fecha futura.")
                return

            target_chat_id: int | None = None
            if asset.request_id is not None:
                request = await session.get(FanRequest, asset.request_id)
                if request is None:
                    await message.answer("😰 El pedido asociado ya no existe.")
                    return
                target_chat_id = request.chat_id
            else:
                target_chat_id = await self.community.for_user(session, message.from_user.id)
                if target_chat_id is None:
                    await message.answer(
                        "😰 Necesito una comunidad definida para esta publicación. "
                        "Con varias comunidades, el administrador debe pertenecer a la comunidad destino."
                    )
                    return

            if not is_authorized_community(self.settings, target_chat_id):
                await message.answer("😰 La comunidad destino ya no está autorizada para publicar.")
                return

            asset.publish_group_chat_id = target_chat_id
            asset.scheduled_at = scheduled_at
            asset.status = "scheduled"
            await self.jobs.enqueue(
                session,
                "media.publish",
                {"asset_id": asset.id, "destination": asset.publish_destination or "both"},
                dedupe_key=f"media-publish:{asset.id}:{scheduled_at.isoformat()}",
                run_at=scheduled_at,
            )
        await message.answer("🗓️ <b>Programado.</b> La orden quedó persistida para que sobreviva a un reinicio.")
        await self._observe_action("media_schedule", message.from_user.id)
        await state.clear()

    async def catalog_command(self, message: Message) -> None:
        """Search the published media catalog without exposing private storage data."""
        if message.chat.type not in {"private", "group", "supergroup"} or message.from_user is None:
            return

        parts = (message.text or "").split(maxsplit=1)
        query = parts[1].strip() if len(parts) == 2 else ""
        async with self.database.session() as session:
            statement = (
                select(MediaAsset)
                .where(
                    MediaAsset.status.in_(
                        ["published", "published_request"]
                    )
                )
                .order_by(MediaAsset.updated_at.desc(), MediaAsset.id.desc())
                .limit(10)
            )
            if query:
                pattern = f"%{query}%"
                from sqlalchemy import or_

                statement = (
                    statement.where(
                        or_(
                            MediaAsset.character_id.ilike(pattern),
                            MediaAsset.anime.ilike(pattern),
                            MediaAsset.tags.ilike(pattern),
                            MediaAsset.category.ilike(pattern),
                        )
                    )
                )
            rows = list(await session.scalars(statement))

        if not rows:
            await message.answer(
                "📚 No encontré material publicado que coincida con esa búsqueda."
                if query
                else "📚 Todavía no hay material publicado en el catálogo."
            )
            await self._observe_action("catalog_empty", message.from_user.id, message.chat.id)
            return

        title = "📚 <b>Catálogo de Cami</b>" + (f" · <i>{escape(query)}</i>" if query else "")
        lines = [title, ""]
        for asset in rows:
            character = escape((asset.character_id or "sin personaje").replace("-", " "))
            anime = escape(asset.anime or "obra no indicada")
            tags = [
                tag.strip()
                for tag in (asset.tags or "").split(",")
                if tag.strip()
            ]
            tag_text = " ".join(f"#{escape(tag)}" for tag in tags[:5])
            line = f"• <b>{character}</b> — {anime}"
            if tag_text:
                line += f" · {tag_text}"
            lines.append(line)

        await message.answer("\n".join(lines))
        await self._observe_action("catalog_search" if query else "catalog_latest", message.from_user.id, message.chat.id)

    async def anime_command(self, message: Message) -> None:
        """Search only local anime/manga metadata; runtime never calls the web."""
        if message.chat.type not in {"private", "group", "supergroup"} or message.from_user is None:
            return

        parts = (message.text or "").split(maxsplit=1)
        query = parts[1].strip() if len(parts) == 2 else ""
        async with self.database.session() as session:
            rows = await self.anime.search_works(session, query, limit=10)

        if not rows:
            await message.answer(
                "📖 No hay fichas locales que coincidan con esa búsqueda."
                if query
                else "📖 Todavía no hay fichas locales de anime/manga cargadas."
            )
            await self._observe_action(
                "anime_search_empty" if query else "anime_catalog_empty",
                message.from_user.id,
                message.chat.id,
            )
            return

        title = "📖 <b>Archivo local de anime/manga</b>"
        if query:
            title += f" · <i>{escape(query)}</i>"
        lines = [title, ""]
        for row in rows:
            line = f"• <b>{escape(row.title)}</b> · {escape(row.media_type)} · {escape(row.status)}"
            if row.year_start is not None:
                years = str(row.year_start)
                if row.year_end is not None and row.year_end != row.year_start:
                    years += f"–{row.year_end}"
                line += f" · {years}"
            if row.genres:
                line += f" · {escape(', '.join(row.genres[:4]))}"
            lines.append(line)
            if row.summary_short:
                lines.append(f"  {escape(row.summary_short)}")
            elif row.notes:
                lines.append(f"  <i>{escape(row.notes[0])}</i>")

        await message.answer("\n".join(lines))
        await self._observe_action(
            "anime_search" if query else "anime_catalog",
            message.from_user.id,
            message.chat.id,
        )


    async def anime_detail_command(self, message: Message) -> None:
        """Show one local anime/manga record with its known characters and aliases."""
        if message.chat.type not in {"private", "group", "supergroup"} or message.from_user is None:
            return

        parts = (message.text or "").split(maxsplit=1)
        query = parts[1].strip() if len(parts) == 2 else ""
        if not query:
            await message.answer(
                "📖 Indicá una obra o personaje. Ejemplo: <code>/anime_ficha Asuna</code>"
            )
            return

        async with self.database.session() as session:
            matches = await self.anime.search_works(session, query, limit=6)
            if len(matches) == 0:
                await message.answer("📖 No encontré una ficha local para esa búsqueda.")
                await self._observe_action(
                    "anime_detail_empty",
                    message.from_user.id,
                    message.chat.id,
                )
                return
            if len(matches) > 1:
                lines = [
                    f"📖 <b>Encontré {len(matches)} fichas</b>. Afiná la búsqueda:",
                    "",
                ]
                lines.extend(
                    f"• <code>{escape(row.id)}</code> — <b>{escape(row.title)}</b>"
                    for row in matches
                )
                await message.answer("\n".join(lines))
                await self._observe_action(
                    "anime_detail_ambiguous",
                    message.from_user.id,
                    message.chat.id,
                )
                return

            row = matches[0]
            characters = await self.anime.characters_for_work(
                session,
                row.id,
                limit=20,
            )

        verification = (
            "verificada"
            if row.last_verified is not None
            else "no verificada"
        )
        lines = [
            f"📖 <b>{escape(row.title)}</b>",
            f"ID: <code>{escape(row.id)}</code>",
            f"Estado: <b>{escape(row.status)}</b> · fuente {verification}",
        ]
        if row.media_type:
            lines.append(f"Tipo: {escape(row.media_type)}")
        if row.year_start is not None:
            years = str(row.year_start)
            if row.year_end is not None and row.year_end != row.year_start:
                years += f"–{row.year_end}"
            lines.append(f"Año: {years}")
        if row.episodes is not None:
            lines.append(f"Episodios: {row.episodes}")
        if row.studio:
            lines.append(f"Estudio: {escape(row.studio)}")
        if row.genres:
            lines.append(f"Géneros: {escape(', '.join(row.genres[:8]))}")
        if row.themes:
            lines.append(f"Temas: {escape(', '.join(row.themes[:8]))}")
        if row.summary_short:
            lines.extend(("", f"<b>Resumen:</b> {escape(row.summary_short)}"))
        if characters:
            lines.extend(("", "<b>Personajes registrados:</b>"))
            for character in characters:
                item = f"• {escape(character.name)}"
                aliases = ", ".join(character.aliases[:5])
                if aliases:
                    item += f" · aliases: {escape(aliases)}"
                lines.append(item)
        else:
            lines.extend(("", "No hay personajes registrados para esta ficha."))
        lines.extend(
            (
                "",
                "ℹ️ Esta ficha pertenece al catálogo local. Cami no completa datos faltantes con IA.",
            )
        )
        await message.answer("\n".join(lines))
        await self._observe_action(
            "anime_detail",
            message.from_user.id,
            message.chat.id,
        )

    async def request_queue_command(self, message: Message) -> None:
        """Show Cami's durable request queue without exposing private user data publicly."""
        if not self._is_media_staff(message):
            return

        async with self.database.session() as session:
            communities = await self.community.configured(session)
            summaries = [
                await self.requests.queue_summary(session, chat_id=chat_id)
                for chat_id in communities
            ]

        if not summaries:
            await message.answer(
                "📭 No hay comunidades autorizadas configuradas para la cola de pedidos."
            )
            await self._observe_action("request_queue_empty", message.from_user.id)
            return

        pending = sum(summary.pending for summary in summaries)
        processing = sum(summary.processing for summary in summaries)
        overdue = sum(summary.overdue for summary in summaries)
        completed_recent = sum(summary.completed_recent for summary in summaries)
        oldest = min(
            (
                summary.oldest_pending_at
                for summary in summaries
                if summary.oldest_pending_at is not None
            ),
            default=None,
        )
        age_text = "sin pedidos pendientes"
        if oldest is not None:
            age_minutes = max(0, int((utc_now() - oldest).total_seconds() // 60))
            if age_minutes < 60:
                age_text = f"{age_minutes} min"
            elif age_minutes < 1440:
                age_text = f"{age_minutes // 60} h {age_minutes % 60} min"
            else:
                age_text = f"{age_minutes // 1440} d"

        lines = [
            "📋 <b>Cola operativa de Cami</b>",
            "",
            f"🟡 Pendientes: <b>{pending}</b>",
            f"🔵 Procesando: <b>{processing}</b>",
            f"🔴 Vencidos: <b>{overdue}</b>",
            f"🟢 Completados hoy: <b>{completed_recent}</b>",
            f"⏱️ Antigüedad del pedido pendiente más antiguo: <b>{age_text}</b>",
            "",
            f"🏠 Comunidades activas: <b>{len(communities)}</b>",
            "La cola usa estados persistentes; reiniciar Cami no borra los pedidos.",
        ]
        await message.answer("\n".join(lines))
        await self._observe_action("request_queue_view", message.from_user.id)

    async def media_queue_command(self, message: Message) -> None:
        """Show the current media pipeline so an operator can act before backlog grows."""
        if not self._is_media_staff(message):
            return

        async with self.database.session() as session:
            summary = await self.library.queue_summary(session)

        age_text = "sin material pendiente"
        if summary.oldest_actionable_at is not None:
            age_minutes = max(
                0,
                int((utc_now() - summary.oldest_actionable_at).total_seconds() // 60),
            )
            if age_minutes < 60:
                age_text = f"{age_minutes} min"
            elif age_minutes < 1440:
                age_text = f"{age_minutes // 60} h {age_minutes % 60} min"
            else:
                age_text = f"{age_minutes // 1440} d"

        lines = [
            "🗂️ <b>Cola de medios de Cami</b>",
            "",
            f"📥 Bandeja: <b>{summary.inbox}</b>",
            f"🏷️ Esperando tags: <b>{summary.needs_tag}</b>",
            f"🕒 Esperando programación: <b>{summary.waiting_schedule}</b>",
            f"📅 Programados: <b>{summary.scheduled}</b>",
            f"📤 Publicando: <b>{summary.publishing}</b>",
            f"⚠️ Entrega ambigua: <b>{summary.delivery_unknown}</b>",
            f"✅ Publicados: <b>{summary.published}</b>",
            f"⏱️ Antigüedad del trabajo pendiente más antiguo: <b>{age_text}</b>",
        ]
        if summary.delivery_unknown:
            lines.extend(
                (
                    "",
                    "⚠️ Hay entregas ambiguas que requieren revisión humana antes de reintentar.",
                    "Usá <code>/recuperar_publicaciones</code> para abrir sus decisiones.",
                )
            )
        await message.answer("\n".join(lines))
        await self._observe_action("media_queue_view", message.from_user.id)

    async def recovery_command(self, message: Message) -> None:
        if not self._is_media_staff(message):
            return
        async with self.database.session() as session:
            assets = list(await session.scalars(
                select(MediaAsset)
                .where(MediaAsset.status == "delivery_unknown")
                .order_by(MediaAsset.id.asc())
                .limit(20)
            ))
        if not assets:
            await message.answer("✅ No hay publicaciones con entrega ambigua.")
            return
        for asset in assets:
            kind = f"pedido #{asset.request_id}" if asset.request_id else "publicación programada"
            await message.answer(
                f"⚠️ <b>Material #{asset.id}</b> · {kind}\n"
                "Telegram pudo haber recibido el envío antes de que se guardara el ID.",
                reply_markup=cami_publication_recovery(asset.id),
            )

    async def recover_publication(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.data is None or not self._is_media_staff(callback.message, user_id=callback.from_user.id):
            await callback.answer("Esta recuperación es privada.", show_alert=True)
            return
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer("Recuperación inválida.", show_alert=True)
            return
        action = parts[2]
        try:
            asset_id = int(parts[3])
        except ValueError:
            await callback.answer("Material inválido.", show_alert=True)
            return

        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            if asset is None or asset.status != "delivery_unknown":
                await callback.answer("Ese material ya fue resuelto.", show_alert=True)
                return

            if action == "confirm":
                request = await session.get(FanRequest, asset.request_id) if asset.request_id else None
                if request is not None:
                    request.status = RequestStatus.COMPLETED.value
                    request.updated_at = utc_now()
                    asset.status = "published_request"
                else:
                    asset.status = "published"
                asset.updated_at = utc_now()
                await session.commit()
                await callback.message.edit_text(f"✅ Material #{asset_id} marcado como publicado.")
                await self._observe_action("publication_recovery_confirm", callback.from_user.id)
                await callback.answer("Confirmado.")
                return

            if action == "discard":
                request = await session.get(FanRequest, asset.request_id) if asset.request_id else None
                if request is not None and request.status == RequestStatus.PROCESSING.value:
                    request.status = RequestStatus.REJECTED.value
                    request.updated_at = utc_now()
                asset.status = "archived"
                asset.updated_at = utc_now()
                await session.commit()
                await callback.message.edit_text(f"📦 Material #{asset_id} descartado.")
                await self._observe_action("publication_recovery_discard", callback.from_user.id)
                await callback.answer("Descartado.")
                return

            if action == "retry":
                request = await session.get(FanRequest, asset.request_id) if asset.request_id else None
                now = utc_now().isoformat()
                if request is not None:
                    request.status = RequestStatus.PROCESSING.value
                    request.updated_at = utc_now()
                    asset.status = "request_ready"
                    await self.jobs.enqueue(
                        session,
                        "media.request_publish",
                        {"asset_id": asset.id, "request_id": request.id},
                        dedupe_key=f"media-request:{request.id}:recovery:{now}",
                    )
                else:
                    asset.status = "scheduled"
                    asset.updated_at = utc_now()
                    await self.jobs.enqueue(
                        session,
                        "media.publish",
                        {"asset_id": asset.id, "destination": asset.publish_destination or "both"},
                        dedupe_key=f"media-publish:{asset.id}:recovery:{now}",
                    )
                await callback.message.edit_text(f"🔁 Material #{asset_id} puesto nuevamente en cola.")
                await self._observe_action("publication_recovery_retry", callback.from_user.id)
                await callback.answer("Reintentando.")
                return

        await callback.answer("Acción no implementada.", show_alert=True)

    async def media_action(
        self,
        callback: CallbackQuery,
        bot: Bot,
        state: FSMContext,
    ) -> None:
        if callback.message is None or callback.data is None:
            await callback.answer("Acción inválida.", show_alert=True)
            return
        if not self._is_media_staff(callback.message, user_id=callback.from_user.id):
            await callback.answer("Esta bandeja es privada.", show_alert=True)
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
                await state.set_state(CamiMediaStates.waiting_tags)
                await state.update_data(asset_id=asset_id)
                await callback.message.edit_text(
                    "🏷️ <b>Listo para etiquetar.</b>\nMandame:\n"
                    "<code>Asuna | Sword Art Online | cabello azul, uniforme | waifu</code>"
                )
                await callback.answer()
                return

            if action == "schedule":
                asset.status = "waiting_destination"
                await session.commit()
                await state.clear()
                await callback.message.edit_text(
                    "🗓️ ¿Dónde querés publicarlo?\n"
                    "<b>Página + tema del grupo</b> mantiene ambos con el mismo segmento.",
                    reply_markup=cami_publish_destination(asset_id),
                )
                await callback.answer()
                return

            if action == "request":
                requests = await session.scalars(
                    select(FanRequest)
                    .where(FanRequest.status == RequestStatus.PENDING_ADMIN.value)
                    .order_by(FanRequest.created_at.asc())
                    .limit(8)
                )
                pending = list(requests)
                if not pending:
                    await callback.answer("No hay pedidos pendientes.", show_alert=True)
                    return
                await callback.message.edit_text(
                    "📨 <b>¿A qué pedido corresponde esta imagen?</b>\n"
                    "Elegí el pedido; después la publicaré en <b>#pedidos</b> etiquetando al integrante.",
                    reply_markup=cami_pending_requests(
                        asset_id,
                        [(request.id, f"#{request.id} · {request.description}") for request in pending],
                    ),
                )
                await callback.answer()
                return

            if action == "archive":
                asset.status = "archived"
                await session.commit()
                await state.clear()
                await callback.message.edit_text("📦 Archivado. No se publicará.")
                await self._observe_action("media_archive", callback.from_user.id)
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
                await state.set_state(CamiMediaStates.waiting_schedule)
                await state.update_data(asset_id=asset_id)
                await callback.message.edit_text(
                    "🕒 Decime cuándo querés enviarlo en formato <code>DD/MM/YYYY HH:MM</code>."
                )
                await self._observe_action("media_destination_set", callback.from_user.id)
                await callback.answer()
                return

            if action == "cancel":
                asset.status = "cami_inbox"
                await session.commit()
                await state.clear()
                await callback.message.edit_text(
                    "↩️ Cancelado. El material vuelve a la bandeja de Cami.",
                    reply_markup=cami_media_actions(asset_id),
                )
                await self._observe_action("media_cancel", callback.from_user.id)
                await callback.answer()
                return

        await callback.answer("Acción no implementada.", show_alert=True)

    async def link_request(self, callback: CallbackQuery, bot: Bot) -> None:
        if callback.message is None or callback.data is None or not self._is_media_staff(callback.message, user_id=callback.from_user.id):
            await callback.answer("Acción inválida.", show_alert=True)
            return
        parts = callback.data.split(":")
        if len(parts) != 5:
            await callback.answer("Pedido inválido.", show_alert=True)
            return
        try:
            asset_id = int(parts[3])
            request_id = int(parts[4])
        except ValueError:
            await callback.answer("Pedido inválido.", show_alert=True)
            return

        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            if asset is None or asset.source_chat_id != callback.message.chat.id:
                await callback.answer("No encuentro ese material.", show_alert=True)
                return
            if asset.request_id is not None:
                await callback.answer("Este material ya está asociado a un pedido.", show_alert=True)
                return

            request = await session.get(FanRequest, request_id)
            if request is None:
                await callback.answer("No encuentro ese pedido.", show_alert=True)
                return
            if not is_authorized_community(self.settings, request.chat_id):
                await callback.answer("La comunidad de ese pedido ya no está autorizada.", show_alert=True)
                return

            claimed = await session.execute(
                update(FanRequest)
                .where(
                    FanRequest.id == request_id,
                    FanRequest.status == RequestStatus.PENDING_ADMIN.value,
                )
                .values(status=RequestStatus.PROCESSING.value)
            )
            if claimed.rowcount != 1:
                await session.rollback()
                await callback.answer("Ese pedido ya fue tomado o completado.", show_alert=True)
                return

            setup = await session.scalar(
                select(SetupSession)
                .where(
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
            )
            if setup is None:
                await session.rollback()
                await callback.answer("Chie todavía no tiene un grupo configurado.", show_alert=True)
                return

            asset.request_id = request_id
            asset.publish_group_chat_id = request.chat_id
            asset.status = "request_ready"
            await self.jobs.enqueue(
                session,
                "media.request_publish",
                {"asset_id": asset_id, "request_id": request_id},
                dedupe_key=f"media-request:{request_id}",
            )

        await callback.message.edit_text(
            f"🕒 <b>Pedido #{request_id} puesto en cola.</b>\n"
            "Cami lo publicará en #pedidos y marcará el pedido como completado cuando Telegram confirme el envío."
        )
        await callback.answer("Pedido en cola.")
