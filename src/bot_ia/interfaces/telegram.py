# -*- coding: utf-8 -*-
"""Capa de Telegram: conversación natural + menús contextuales sin hoja de comandos."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import time
from typing import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bot_ia.core.application import ApplicationRequest, ApplicationResponse, BotApplication
from bot_ia.paths import PROJECT_ROOT
from bot_ia.core.waitress_session_manager import TavernError, TavernReply, WaitressSessionManager
from bot_ia.librarian.models import CoverageStatus

from .telegram_outbox import TelegramOutboxError, TelegramOutboxStore, TelegramOutboxRecord
from .telegram_event_ledger import TelegramEventLedger, TelegramEventLedgerError
from .telegram_instance_lock import TelegramInstanceAlreadyRunning, TelegramInstanceLock
from .group_setup import GroupSetupError, GroupSetupStore, TelegramGroupSetup
from .telegram_room_routing import TelegramRoomRouter, TelegramRoomRoutingError
from .telegram_security import (
    is_authorized_admin_destination,
    is_authorized_telegram_forum_route,
    is_authorized_telegram_group,
)
from .cafe_orders import BebidaOrderFlow, build_bebida_summary, build_bebida_prompt, RESOLUTIONS, RENDER_STYLES
from .hardening import MutexGuard
from .xp_audit import PassiveXPTracker, AuditBus
from .order_support import ComplaintStore, OrderConfirmation, OrderStore, new_order_id, order_destination
from .inline_router import InlineRedirectHandler
from .auto_moderation import moderate
from .cafe_immersion import analyze_telegram_comment
from .cafe_economy import CafeWalletStore, draw_gacha, economy_price_text, pity_text, purchase_bebida_order, quote_bebida_order
from .cafe_immersion import waitress_dialogue, waitress_exclusive_dialogue, supervise_admin_publication
from .superadmin import is_superadmin
from .cafe_vip import VipStore, donation_keyboard, vip_policy_text, vip_status_text, validate_donation_event
from .cafe_rooms import sfw_transition, mature_game_message
from gui.waifu_registry import WaifuRegistry
from .tutorials import build_tutorial_text


class TelegramInputError(ValueError):
    pass


MAX_INBOUND_TEXT_CHARS = 24_000
MAX_CALLBACK_DATA_CHARS = 256
MAX_TELEGRAM_HTTP_RESPONSE_BYTES = 1 * 1024 * 1024


class TelegramConfigurationError(RuntimeError):
    pass


class TelegramTransportError(RuntimeError):
    pass


class TelegramHttpError(TelegramTransportError):
    pass


class TelegramApiError(RuntimeError):
    pass


class TelegramPartialDeliveryError(TelegramTransportError):
    def __init__(self, next_chunk_index: int) -> None:
        super().__init__("Telegram delivery failed after a partial message")
        self.next_chunk_index = next_chunk_index


@dataclass(frozen=True, slots=True)
class TelegramInbound:
    user_id: str
    conversation_id: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TelegramCallback:
    user_id: str
    conversation_id: str
    data: str


@dataclass(frozen=True, slots=True)
class TelegramOutbound:
    chat_id: str
    text: str
    route: str | None = None
    keyboard: tuple[tuple[tuple[str, str], ...], ...] = ()
    auto_delete_seconds: int | None = None
    message_thread_id: int | None = None
    reply_to_message_id: int | None = None
    followups: tuple["TelegramOutbound", ...] = ()
    photo_file_id: str | None = None

    def payload(self) -> dict[str, object]:
        if self.photo_file_id:
            payload: dict[str, object] = {"chat_id": self.chat_id, "photo": self.photo_file_id}
            if self.text:
                payload["caption"] = self.text
        else:
            payload = {"chat_id": self.chat_id, "text": self.text}
        if self.message_thread_id is not None:
            payload["message_thread_id"] = int(self.message_thread_id)
        if self.reply_to_message_id is not None:
            payload["reply_parameters"] = {"message_id": int(self.reply_to_message_id)}
        if self.keyboard:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row] for row in self._normalized_keyboard()]}
        return payload

    def _normalized_keyboard(self) -> tuple[tuple[tuple[str, str], ...], ...]:
        """Normaliza filas antiguas de dos botones sin romper el contrato nuevo."""
        normalized: list[tuple[tuple[str, str], ...]] = []
        for row in self.keyboard:
            if isinstance(row, tuple) and len(row) == 2 and all(isinstance(value, str) for value in row):
                normalized.append((row,))
                continue
            if not isinstance(row, (tuple, list)):
                raise TelegramInputError("keyboard row must be a button pair or row of button pairs")
            buttons: list[tuple[str, str]] = []
            for button in row:
                if not isinstance(button, (tuple, list)) or len(button) != 2:
                    raise TelegramInputError("keyboard button must contain label and callback_data")
                label, data = button
                if not isinstance(label, str) or not isinstance(data, str):
                    raise TelegramInputError("keyboard label and callback_data must be strings")
                buttons.append((label, data))
            normalized.append(tuple(buttons))
        return tuple(normalized)


def parse_update(update: dict[str, object]) -> TelegramInbound:
    try:
        message = update["message"]
        sender = message["from"]
        chat = message["chat"]
        text = message["text"]
        user_id, chat_id = str(sender["id"]), str(chat["id"])
    except (KeyError, TypeError) as error:
        raise TelegramInputError("update must contain message text, sender and chat") from error
    if not isinstance(text, str) or not text.strip():
        raise TelegramInputError("message text cannot be empty")
    text = text.strip()
    if len(text) > MAX_INBOUND_TEXT_CHARS:
        raise TelegramInputError("message text is too long")
    metadata = update.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return TelegramInbound(user_id, chat_id, text, dict(metadata))


@dataclass(frozen=True, slots=True)
class TelegramInlineQuery:
    query_id: str
    user_id: str
    chat_id: str | None
    query: str


def parse_inline_query_update(update: dict[str, object]) -> TelegramInlineQuery:
    try:
        inline = update["inline_query"]
        sender = inline["from"]
        query_id = inline["id"]
        query = inline.get("query", "")
        chat_type = inline.get("chat_type")
    except (KeyError, TypeError) as error:
        raise TelegramInputError("inline query is invalid") from error
    if not isinstance(sender, dict):
        raise TelegramInputError("inline sender is invalid")
    user_id = str(sender.get("id", "")).strip()
    if not user_id or not isinstance(query_id, str) or not query_id.strip():
        raise TelegramInputError("inline identity is invalid")
    return TelegramInlineQuery(
        query_id.strip(),
        user_id,
        str(chat_type) if chat_type is not None else None,
        str(query),
    )


def parse_callback_update(update: dict[str, object]) -> TelegramCallback:
    try:
        callback = update["callback_query"]
        sender = callback["from"]
        message = callback["message"]
        chat = message["chat"]
        data = callback["data"]
        user_id, chat_id = str(sender["id"]), str(chat["id"])
    except (KeyError, TypeError) as error:
        raise TelegramInputError("callback update is invalid") from error
    if not isinstance(data, str) or not data.strip():
        raise TelegramInputError("callback data cannot be empty")
    data = data.strip()
    if len(data) > MAX_CALLBACK_DATA_CHARS:
        raise TelegramInputError("callback data is too long")
    return TelegramCallback(user_id, chat_id, data)


class TelegramAdapter:
    """Presenta una interfaz visual pequeña; la aplicación sigue siendo agnóstica de Telegram."""

    MAIN_MENU = (
        (("✍️ Escribir novela", "menu:write"), ("📝 Editar texto", "menu:edit")),
        (("📚 Biblioteca", "menu:library"), ("🧭 Continuidad", "menu:continuity")),
        (("💡 Ideas", "menu:ideas"), ("❓ Ayuda", "menu:help")),
        (("🍀 Pity", "pity:show"), ("☕ Puntos", "economy:show")),
        (("✨ VIP / Apoyar", "vip:show"),),
    )

    def __init__(
        self,
        application: BotApplication,
        *,
        tavern_manager: WaitressSessionManager | None = None,
        room_router: TelegramRoomRouter | None = None,
    ) -> None:
        self._application = application
        self._tavern_manager = tavern_manager
        self._wallet_store = CafeWalletStore(PROJECT_ROOT)
        self._waifu_registry = WaifuRegistry(PROJECT_ROOT)
        self._bebida_flow = BebidaOrderFlow(
            allowed_tags=self._waifu_registry.danbooru_whitelist(),
        )
        self._complaint_store = ComplaintStore(PROJECT_ROOT)
        self._vip_store = VipStore(PROJECT_ROOT)
        self._room_router = room_router or TelegramRoomRouter(
            PROJECT_ROOT / "config" / "telegram_rooms.sqlite3"
        )
        self._order_store = OrderStore(PROJECT_ROOT)
        self._pending_orders: dict[str, OrderConfirmation] = {}
        self._last_orders: dict[str, OrderConfirmation] = {}
        self._pending_attachments: dict[str, OrderConfirmation] = {}
        self._inline_handler = InlineRedirectHandler(
            official_ids={
                value.strip()
                for value in os.getenv("TELEGRAM_OFFICIAL_CHAT_IDS", "").split(",")
                if value.strip()
            },
            cafe_url=os.getenv("CAFE_OTAKU_INVITE_URL", "").strip(),
        )
        self._callback_mutex = MutexGuard()
        self._xp_tracker = PassiveXPTracker(PROJECT_ROOT / "config" / "nakama_xp.sqlite3")
        self._audit_bus = AuditBus()

    def _active_maid(self, user_id: str) -> str:
        """Devuelve la mesera activa del turno local; Cami es el fallback."""
        if self._tavern_manager is not None:
            session = self._tavern_manager.get_active_session(str(user_id))
            waitress_id = str(getattr(session, "waitress_id", "") or "").strip()
            if waitress_id:
                return waitress_id.capitalize()
        return "Cami"

    def _affinity_level(self, user_id: str, maid: str) -> int:
        return self._waifu_registry.affinity_level(user_id, maid)

    @staticmethod
    def _admin_ids() -> frozenset[str]:
        raw = os.getenv("TELEGRAM_ADMIN_USER_IDS", "")
        return frozenset(part.strip() for part in raw.split(",") if part.strip())

    def room_key_for_update(self, update: dict[str, object]) -> str:
        """Resuelve la sala real del update sin inventar "general" en un foro."""
        message = update.get("message")
        if not isinstance(message, dict):
            raise TelegramInputError("update sin mensaje Telegram")
        chat = message.get("chat")
        if not isinstance(chat, dict):
            raise TelegramInputError("mensaje sin chat Telegram")
        chat_id = str(chat.get("id", "")).strip()
        if not chat_id:
            raise TelegramInputError("chat_id Telegram vacío")

        chat_type = str(chat.get("type", "")).strip().lower()
        thread_raw = message.get("message_thread_id")
        is_topic = bool(message.get("is_topic_message"))
        thread_id: int | None = None
        if thread_raw is not None:
            try:
                thread_id = int(thread_raw)
            except (TypeError, ValueError) as error:
                raise TelegramInputError(
                    "message_thread_id Telegram inválido"
                ) from error

        if chat_type in {"group", "supergroup"}:
            if not is_authorized_telegram_group(chat_id):
                raise TelegramInputError(
                    "chat Telegram fuera de la allowlist autorizada"
                )

        if thread_id is not None or is_topic:
            if thread_id is None:
                raise TelegramInputError(
                    "mensaje de topic sin message_thread_id"
                )
            if not is_authorized_telegram_forum_route(chat_id, thread_id):
                raise TelegramInputError(
                    "topic Telegram fuera de AUTHORIZED_FORUM_ID"
                )
            try:
                room_key = self._room_router.resolve(chat_id, thread_id)
            except TelegramRoomRoutingError as error:
                raise TelegramInputError(
                    "no se pudo consultar el mapa autoritativo de salas"
                ) from error
            if not room_key:
                raise TelegramInputError(
                    f"topic Telegram no registrado: {chat_id}:{thread_id}"
                )
            return room_key

        return "general"

    def _sync_authorized_bot_join(self, update: dict[str, object]) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        members = message.get("new_chat_members")
        chat = message.get("chat")
        if not isinstance(members, list) or not isinstance(chat, dict):
            return
        if not any(isinstance(member, dict) and bool(member.get("is_bot")) for member in members):
            return
        chat_id = str(chat.get("id", "")).strip()
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not chat_id or not token:
            return
        if not is_authorized_telegram_group(chat_id):
            logger = getattr(self, "_logger", None)
            if callable(logger):
                logger(
                    f"telegram bot role sync denied for unauthorized chat {chat_id}"
                )
            return
        try:
            TelegramGroupSetup(token).configure_authorized_bots(chat_id)
        except GroupSetupError as error:
            self._logger(f"telegram bot role sync skipped: {error}")

    def _admin_followup(self, complaint) -> TelegramOutbound | None:
        admin_chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
        if not is_authorized_admin_destination(admin_chat):
            return None
        thread_raw = os.getenv("TELEGRAM_ADMIN_THREAD_ID", "").strip()
        try:
            thread_id = int(thread_raw) if thread_raw else None
        except ValueError:
            thread_id = None
        text = (
            "📣 NUEVO RECLAMO · Café Otaku\n"
            f"ID: {complaint.complaint_id}\n"
            f"Usuario: {complaint.user_id}\n"
            f"Pedido: {complaint.order_id or 'sin pedido'}\n"
            f"Producto: {complaint.product_type or 'no indicado'}\n"
            f"Puntos pagados: {complaint.points_paid}\n"
            f"Motivo: {complaint.text}"
        )
        keyboard = (
            (
                ("✅ Reembolsar Puntos", f"complaint:refund:{complaint.complaint_id}"),
                ("🔄 Convertir a Imagen", f"complaint:convert_image:{complaint.complaint_id}"),
            ),
            (("❌ Rechazar", f"complaint:reject:{complaint.complaint_id}"),),
        )
        return TelegramOutbound(
            admin_chat,
            text,
            "admin_complaint",
            keyboard,
            message_thread_id=thread_id,
        )

    def _admin_order_followup(self, order: OrderConfirmation) -> TelegramOutbound | None:
        admin_chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
        if not is_authorized_admin_destination(admin_chat):
            return None
        if not admin_chat:
            return None
        thread_raw = os.getenv("TELEGRAM_ADMIN_ORDERS_THREAD_ID", os.getenv("TELEGRAM_ADMIN_THREAD_ID", "")).strip()
        try:
            thread_id = int(thread_raw) if thread_raw else None
        except ValueError:
            thread_id = None
        text = (
            "🧾 PEDIDO · #pedidos\n"
            f"ID: {order.order_id}\n"
            f"Usuario pagador: {order.user_id}\n"
            f"Destino: {order.destination}\n"
            f"Resolución: {order.resolution}\n"
            f"Estilo: {order.render_style}\n"
            "Texto original en español:\n"
            f"{order.summary}\n\n"
            "Prompt optimizado en inglés:\n"
            f"{order.prompt_en}"
        )
        keyboard = ((("📎 Adjuntar / Subir imagen generada", f"order:attach:{order.order_id}"),),)
        return TelegramOutbound(admin_chat, text, "admin_order", keyboard, message_thread_id=thread_id)

    def _order_attach(self, callback: TelegramCallback, order_id: str) -> TelegramOutbound:
        if callback.user_id not in self._admin_ids():
            return TelegramOutbound(callback.conversation_id, "⛔ Acción reservada al equipo administrativo.", "admin")
        order = self._order_store.get(order_id)
        if order is not None:
            self._pending_attachments[callback.user_id] = order
            return TelegramOutbound(
                callback.conversation_id,
                f"📎 Pedido {order_id} listo. Envía ahora la imagen generada como foto a este chat.",
                "admin_order",
            )
        return TelegramOutbound(callback.conversation_id, "⚠️ Pedido no encontrado o expirado.", "admin")
        return TelegramOutbound(callback.conversation_id, "⚠️ Pedido no encontrado o expirado.", "admin")

    def _complaint_response(self, callback: TelegramCallback, action: str, complaint_id: str) -> TelegramOutbound:
        if callback.user_id not in self._admin_ids():
            return TelegramOutbound(callback.conversation_id, "⛔ Esta acción está reservada al equipo administrativo.", "admin")
        try:
            record = self._complaint_store.resolve(
                complaint_id,
                action,
                wallet_store=self._wallet_store,
                registry=self._waifu_registry,
            )
        except ValueError as error:
            return TelegramOutbound(callback.conversation_id, f"📣 Reclamo: {error}", "admin")
        points = record.points_paid if action == "refund" else 0
        return TelegramOutbound(
            callback.conversation_id,
            f"📣 Reclamo #{record.complaint_id}: {record.status}. Ajuste de puntos: {points}.",
            "admin",
        )

    def handle_photo_update(self, update: dict[str, object]) -> TelegramOutbound:
        message = update.get("message")
        if not isinstance(message, dict):
            raise TelegramInputError("photo update missing message")
        sender = message.get("from")
        chat = message.get("chat")
        photos = message.get("photo")
        if not isinstance(sender, dict) or not isinstance(chat, dict) or not isinstance(photos, list) or not photos:
            raise TelegramInputError("invalid photo update")
        admin_id = str(sender.get("id", ""))
        pending = self._pending_attachments.get(admin_id)
        if pending is None:
            raise TelegramInputError("no order is waiting for an attachment")
        largest = photos[-1]
        if not isinstance(largest, dict) or not isinstance(largest.get("file_id"), str):
            raise TelegramInputError("photo file_id missing")
        self._pending_attachments.pop(admin_id, None)
        return TelegramOutbound(
            chat_id=pending.user_id,
            text=f"Pedido {pending.order_id} · {pending.resolution} · {pending.render_style}",
            route="order_delivery",
            photo_file_id=largest["file_id"],
        )

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" in update:
            return self.handle_callback(update)
        message = update.get("message")
        if isinstance(message, dict) and isinstance(message.get("successful_payment"), dict):
            payment = message["successful_payment"]
            user = message.get("from", {})
            user_id = str(user.get("id", "")) if isinstance(user, dict) else ""
            try:
                profile = validate_donation_event(user_id, payment)
            except (TypeError, ValueError):
                return TelegramOutbound(
                    str(message.get("chat", {}).get("id", "")),
                    "⚠️ No se pudo validar la donación Stars. No se modificó el acceso VIP.",
                    "vip_donation_error",
                )
            return TelegramOutbound(
                str(message.get("chat", {}).get("id", "")),
                f"✨ Gracias por apoyar voluntariamente al Café. VIP activado. Stars registradas: {profile.donated_stars}.",
                "vip",
            )
        inbound = parse_update(update)
        room_key = self.room_key_for_update(update)
        inbound = TelegramInbound(
            inbound.user_id,
            inbound.conversation_id,
            inbound.text,
            {
                **inbound.metadata,
                "room_key": room_key,
                "message_thread_id": update.get("message", {}).get("message_thread_id")
                if isinstance(update.get("message"), dict)
                else None,
            },
        )
        self._xp_tracker.record_message(inbound.user_id, "telegram")

        # Explicit Telegram commands must never be intercepted by the
        # comment/reply detector. Command handling remains the authoritative
        # path below, while ordinary replies may enter the comment flow.
        command_candidate = inbound.text.casefold().split()[0]
        comment = (
            None
            if command_candidate.startswith("/")
            else analyze_telegram_comment(update)
        )
        if comment is not None and comment.should_reply:
            return TelegramOutbound(
                inbound.conversation_id,
                comment.text,
                "cari_comments",
                reply_to_message_id=comment.reply_to_message_id,
                auto_delete_seconds=30,
            )
        moderation = moderate(
            inbound.text,
            room_key=str(inbound.metadata.get("room_key", "general")),
            image_tags=tuple(
                str(tag)
                for tag in inbound.metadata.get("image_tags", ())
                if isinstance(tag, str)
            ),
        )
        if moderation.action != "allow":
            return TelegramOutbound(
                inbound.conversation_id,
                moderation.message,
                str(inbound.metadata.get("room_key", "general")),
                auto_delete_seconds=30,
            )
        command = inbound.text.casefold().split()[0]

        if command in {"/start", "/menu"}:
            return TelegramOutbound(
                inbound.conversation_id,
                "¡listo! ¿Qué quieres hacer?",
                "local",
                self.MAIN_MENU,
            )
        if command == "/vip":
            return TelegramOutbound(
                inbound.conversation_id,
                vip_status_text(inbound.user_id, self._vip_store),
                "vip",
                donation_keyboard(),
            )
        if command == "/donar":
            return TelegramOutbound(
                inbound.conversation_id,
                "✨ Apoyar al Café es totalmente voluntario.\n"
                "El acceso SFW y #cantina-18 no depende de ninguna donación.\n"
                "Usa el flujo oficial de Telegram Stars para aportar si lo deseas.",
                "vip_donation",
                donation_keyboard(),
            )
        if command in {"/puntos", "/economia", "/precios"}:
            wallet = self._wallet_store.get(inbound.user_id)
            return TelegramOutbound(
                inbound.conversation_id,
                economy_price_text() + f"\n\nSaldo de {inbound.user_id}: {wallet.points} puntos.",
                "economy",
                ((("🍀 Consultar Pity", "pity:show"),),),
            )
        if command == "/pity":
            return TelegramOutbound(
                inbound.conversation_id,
                pity_text(inbound.user_id, self._wallet_store, maid=self._active_maid(inbound.user_id)),
                "pity",
                ((("🎰 Gacha", "gacha:draw"), ("☕ Puntos", "economy:show")),),
            )
        if command == "/propina":
            parts = inbound.text.split()
            if len(parts) != 3:
                return TelegramOutbound(
                    inbound.conversation_id,
                    "💝 Uso: /propina <Cari|Sunna|Cami|Chie> <puntos>.",
                    "affinity",
                )
            try:
                maid, amount = parts[1], int(parts[2])
                maid, charged, level = self._waifu_registry.tip_waitress(
                    inbound.user_id,
                    maid,
                    amount,
                    self._wallet_store,
                )
            except (ValueError, TypeError) as error:
                return TelegramOutbound(inbound.conversation_id, f"💝 Propina: {error}", "affinity")
            return TelegramOutbound(
                inbound.conversation_id,
                f"💝 {maid} recibió {charged} puntos de propina. Heart Level: {level}/10 ❤️\n"
                f"{waitress_exclusive_dialogue(maid, level) or waitress_dialogue(maid, 'greeting')}",
                "affinity",
                ((("🍀 Ver afinidad", "affinity:show"),),),
            )
        if command == "/afinidad":
            return TelegramOutbound(
                inbound.conversation_id,
                f"❤️ Afinidad del Café Otaku:\n{self._waifu_registry.affinity_summary(inbound.user_id)}",
                "affinity",
            )
        if command == "/mesera":
            return TelegramOutbound(
                inbound.conversation_id,
                waitress_dialogue(self._active_maid(inbound.user_id), "role"),
                "cafe",
            )
        if command == "/21" or command == "/blackjack" or command in {"/apuestas", "/apuesta"}:
            return TelegramOutbound(
                inbound.conversation_id,
                mature_game_message(command.lstrip("/")),
                "cantina_18",
            )
        if command == "/gacha":
            maid = self._active_maid(inbound.user_id)
            try:
                result = draw_gacha(
                    inbound.user_id,
                    self._wallet_store,
                    maid=maid,
                    affinity_level=self._affinity_level(inbound.user_id, maid),
                )
            except ValueError as error:
                return TelegramOutbound(inbound.conversation_id, f"🎰 Gacha: {error}", "gacha")
            return TelegramOutbound(
                inbound.conversation_id,
                f"{waitress_dialogue(maid, 'role')}\n🎰 Resultado: {result.rarity}\n{result.consolation}\nCoste: {result.points_spent} puntos.",
                "gacha",
                ((("🍀 Ver Pity", "pity:show"),),),
            )
        if command == "/tutorial":
            return TelegramOutbound(
                inbound.conversation_id,
                build_tutorial_text(),
                "tutorial",
                ((("🥤 Pedir Bebida Especial", "bebida:start:")),),
            )
        if command == "/bebida":
            argument = inbound.text.partition(" ")[2].strip()
            transition = sfw_transition(argument)
            if transition is not None:
                return TelegramOutbound(
                    inbound.conversation_id,
                    transition.message
                    + "\n➡️ Ve a #cantina-18 y habla con Scarlet o Chloé.",
                    "cantina_18",
                )
            if argument:
                tag = self._waifu_registry.resolve_danbooru_tag(argument)
                if not tag:
                    return TelegramOutbound(
                        inbound.conversation_id,
                        "🥤 Pedido rechazado: el personaje debe existir en la lista blanca local de tags Danbooru.",
                        "bebida",
                    )
            self._bebida_flow.start(inbound.user_id)
            if argument:
                self._bebida_flow.set_character(inbound.user_id, argument, tag)
            order = self._bebida_flow.get(inbound.user_id)
            return TelegramOutbound(
                inbound.conversation_id,
                "🥤 BEBIDA ESPECIAL · CAMI\\n"
                + (
                    "Personaje: " + order.character
                    if order.character_tag
                    else "Primero escribe /bebida <personaje>"
                )
                + "\\nElige grado de exposición:",
                "bebida",
                ((("SFW", "bebida:exposure:SFW"), ("Sugerente", "bebida:exposure:Sugerente")), (("NSFW", "bebida:exposure:NSFW"),)),
            )
        if command == "/queja":
            complaint_text = inbound.text.partition(" ")[2].strip()
            if not complaint_text:
                return TelegramOutbound(
                    inbound.conversation_id,
                    "📣 Uso: /queja <texto>. Puedes indicar una sugerencia, problema o solicitud de reembolso.",
                    "complaint",
                )
            last = self._last_orders.get(inbound.user_id)
            complaint = self._complaint_store.create(
                inbound.user_id,
                inbound.conversation_id,
                complaint_text,
                order_id=last.order_id if last else "",
                product_type=last.product_type if last else "",
                points_paid=last.cost if last else 0,
            )
            admin = self._admin_followup(complaint)
            if admin is None:
                return TelegramOutbound(
                    inbound.conversation_id,
                    f"📣 Reclamo #{complaint.complaint_id} registrado. Configura TELEGRAM_ADMIN_CHAT_ID para recibirlo.",
                    "complaint",
                )
            return TelegramOutbound(
                inbound.conversation_id,
                f"📣 Reclamo #{complaint.complaint_id} enviado al canal administrativo #pedidos-admin.",
                "complaint",
                followups=(admin,),
            )

        if command == "/setup_group":
            try:
                setup = TelegramGroupSetup(os.getenv("TELEGRAM_BOT_TOKEN", ""))
                result = setup.setup_chat(
                    inbound.conversation_id,
                    GroupSetupStore(PROJECT_ROOT),
                )
                summary = "\n".join(
                    f"• {room.name} → topic {room.external_id}"
                    for room in result.rooms
                )
                feeds = GroupSetupStore(PROJECT_ROOT).get_feeds("telegram", inbound.conversation_id)
                feed_text = "\n".join(f"• {name}: {url}" for name, url in feeds)
                privacy_note = (
                    "\n\n⚠️ Telegram: #pedidos-admin se crea como tema del foro; "
                    "Telegram no permite permisos privados por tema. Para privacidad real usa un chat/canal admin separado."
                )
                return TelegramOutbound(
                    inbound.conversation_id,
                    "Estructura Telegram preparada:\n" + summary
                    + "\n\nFeeds configurados:\n" + feed_text
                    + privacy_note,
                    "admin_setup",
                )
            except GroupSetupError as error:
                return TelegramOutbound(
                    inbound.conversation_id,
                    f"No se pudo estructurar el grupo: {error}",
                    "admin_setup_error",
                )

        if command == "/help":
            return TelegramOutbound(
                inbound.conversation_id,
                "Envía lo que necesitas o usa el menú. Puedes escribir, editar, consultar la biblioteca, revisar continuidad o generar ideas.",
                "local",
                self.MAIN_MENU,
            )

        if self._tavern_manager is not None:
            tavern_commands = {
                "/inventario",
                "/turnos",
                "/duelo",
                "/charla",
                "/tradicional",
                "/favorita",
                "/vip",
                "/ayuda_taberna",
                "/guia",
            }
            active_tavern_session = self._tavern_manager.get_active_session(
                inbound.user_id
            )
            if command in tavern_commands:
                try:
                    tavern_reply = self._tavern_manager.command(
                        inbound.user_id,
                        inbound.text,
                    )
                except TavernError as error:
                    tavern_reply = TavernReply(
                        str(error),
                        auto_delete_seconds=45,
                    )
                return TelegramOutbound(
                    inbound.conversation_id,
                    tavern_reply.text,
                    "tavern",
                    tavern_reply.keyboard,
                    tavern_reply.auto_delete_seconds,
                )

            if active_tavern_session is not None:
                try:
                    self._tavern_manager.queue_user_message(
                        inbound.user_id,
                        inbound.text,
                    )
                    return TelegramOutbound(
                        inbound.conversation_id,
                        "💬 Mensaje enviado a la mesera. Estoy esperando su respuesta.",
                        "tavern",
                        (),
                        30,
                    )
                except TavernError as error:
                    return TelegramOutbound(
                        inbound.conversation_id,
                        str(error),
                        "tavern",
                        (),
                        45,
                    )
        response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text))
        return self.from_response(inbound.conversation_id, response)

    def schedule_tavern_auto_delete(
        self,
        chat_id: str,
        message_id: int,
        seconds: int,
    ) -> None:
        if self._tavern_manager is None:
            return
        self._tavern_manager.schedule_auto_delete(
            chat_id,
            message_id,
            seconds=seconds,
        )

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        actions = {
            "menu:write": "Quiero escribir una escena o capítulo. Ayúdame usando los archivos locales del proyecto y la continuidad establecida.",
            "menu:edit": "Quiero editar o revisar un texto usando los archivos locales relevantes como referencia.",
            "menu:library": "¿Qué información y documentos tengo disponibles en la biblioteca local?",
            "menu:continuity": "Quiero revisar la continuidad de lo que estamos escribiendo y saber dónde quedamos.",
            "menu:ideas": "Quiero ideas para continuar la novela usando la continuidad y personajes establecidos.",
        }
        if callback.data == "menu:help":
            return TelegramOutbound(
                callback.conversation_id,
                "Escribe lo que necesitas; BOT-IA decide si basta la información local, si necesita consultar archivos o si conviene pedir autorización antes de usar una API.",
                "local",
                self.MAIN_MENU,
            )
        if callback.data == "menu:main":
            return TelegramOutbound(callback.conversation_id, "Menú principal:", "local", self.MAIN_MENU)
        if callback.data == "vip:show":
            return TelegramOutbound(
                callback.conversation_id,
                vip_status_text(callback.user_id, self._vip_store),
                "vip",
                donation_keyboard(),
            )
        if callback.data == "vip:donate":
            return TelegramOutbound(
                callback.conversation_id,
                "✨ Apoyo voluntario. Elige el flujo oficial de donación de Telegram Stars. "
                "No cambia tu acceso a los canales públicos.",
                "vip_donation",
            )
        if callback.data == "economy:show":
            wallet = self._wallet_store.get(callback.user_id)
            return TelegramOutbound(
                callback.conversation_id,
                economy_price_text() + f"\n\nSaldo: {wallet.points} puntos.",
                "economy",
                ((("🍀 Consultar Pity", "pity:show"),),),
            )
        if callback.data == "pity:show":
            return TelegramOutbound(
                callback.conversation_id,
                pity_text(callback.user_id, self._wallet_store, maid=self._active_maid(callback.user_id)),
                "pity",
                ((("🎰 Gacha", "gacha:draw"), ("☕ Puntos", "economy:show")),),
            )
        if callback.data == "affinity:show":
            return TelegramOutbound(
                callback.conversation_id,
                f"❤️ Afinidad del Café Otaku:\n{self._waifu_registry.affinity_summary(callback.user_id)}",
                "affinity",
            )
        if callback.data == "gacha:draw":
            maid = self._active_maid(callback.user_id)
            try:
                result = draw_gacha(
                    callback.user_id,
                    self._wallet_store,
                    maid=maid,
                    affinity_level=self._affinity_level(callback.user_id, maid),
                )
            except ValueError as error:
                return TelegramOutbound(callback.conversation_id, f"🎰 Gacha: {error}", "gacha")
            return TelegramOutbound(
                callback.conversation_id,
                f"{waitress_dialogue(maid, 'role')}\n🎰 Resultado: {result.rarity}\n{result.consolation}\nCoste: {result.points_spent} puntos.",
                "gacha",
                ((("🍀 Ver Pity", "pity:show"),),),
            )
        if callback.data == "fallback:prompt":
            return TelegramOutbound(callback.conversation_id, "Puedo preparar un prompt para pegar en otra IA web sin enviar tu consulta a ninguna API desde BOT-IA.", "local", (("📋 Generar prompt", "prompt:generate"), ("⬅️ Menú", "menu:main")))
        if callback.data == "fallback:api":
            return TelegramOutbound(callback.conversation_id, "Autorización recibida para esta consulta. BOT-IA puede usar la API configurada sólo para esta petición.", "local", (("⬅️ Menú", "menu:main"),))
        if callback.data == "prompt:generate":
            return TelegramOutbound(callback.conversation_id, "Para generar el prompt exacto necesito que me envíes nuevamente la pregunta que quieres investigar. No se enviará a ninguna API desde este botón.", "local", (("⬅️ Menú", "menu:main"),))
        if callback.data.startswith("bebida:"):
            parts = callback.data.split(":", 2)
            if len(parts) != 3:
                raise TelegramInputError("invalid beverage callback")
            _, field, value = parts
            if field == "noop":
                return TelegramOutbound(
                    callback.conversation_id,
                    build_bebida_summary(self._bebida_flow.get(callback.user_id)),
                    "bebida",
                )
            if field == "start":
                self._bebida_flow.start(callback.user_id)
                return TelegramOutbound(
                    callback.conversation_id,
                    "🥤 BEBIDA ESPECIAL · CAMI\nEscribe /bebida <personaje> para fijar el personaje y luego elige el grado de exposición.",
                    "bebida",
                    ((("SFW", "bebida:exposure:SFW"), ("Sugerente", "bebida:exposure:Sugerente")), (("NSFW", "bebida:exposure:NSFW"),)),
                )
            if field == "exposure" and value.casefold() == "nsfw":
                transition = sfw_transition("nsfw")
                return TelegramOutbound(
                    callback.conversation_id,
                    transition.message
                    + "\n➡️ Ve a #cantina-18 y habla con Scarlet o Chloé.",
                    "cantina_18",
                )
            order = self._bebida_flow.choose(callback.user_id, field, value)
            if field == "exposure":
                return TelegramOutbound(
                    callback.conversation_id,
                    "🥤 Nivel guardado. Elige atrevimiento:",
                    "bebida",
                    ((("Suave", "bebida:boldness:Suave"), ("Atrevido", "bebida:boldness:Atrevido")), (("Máximo", "bebida:boldness:Máximo"),)),
                )
            if field == "boldness":
                return TelegramOutbound(
                    callback.conversation_id,
                    "🥤 Elige destino del pedido:",
                    "bebida",
                    (
                        (("🎴 Carta TCG para el Pool", "bebida:product_type:Carta TCG"),),
                        (("🖼️ Imagen IA Personalizada", "bebida:product_type:Imagen IA Personalizada"),),
                    ),
                )
            if field == "product_type":
                return TelegramOutbound(
                    callback.conversation_id,
                    "🖼️ Selecciona resolución:",
                    "bebida",
                    tuple(((label, f"bebida:resolution:{label}"),) for label in RESOLUTIONS),
                )
            if field == "resolution":
                return TelegramOutbound(
                    callback.conversation_id,
                    "🎨 Selecciona estilo de renderizado:",
                    "bebida",
                    tuple(((label, f"bebida:render_style:{label}"),) for label in RENDER_STYLES),
                )
            is_image = order.product_type.casefold() == "imagen ia personalizada"
            target_rarity = "SPECIAL" if is_image else "R"
            quote = quote_bebida_order(
                existing=not is_image,
                target_rarity=target_rarity,
                points=self._wallet_store.balance(callback.user_id),
            )
            pending = OrderConfirmation(
                order_id=new_order_id(),
                user_id=callback.user_id,
                product_type=order.product_type,
                destination=order_destination(order.product_type),
                rarity=quote.rarity,
                cost=quote.cost,
                summary=build_bebida_summary(order),
                resolution=order.resolution,
                render_style=order.render_style,
                prompt_en=build_bebida_prompt(order),
            )
            self._pending_orders[callback.user_id] = pending
            return TelegramOutbound(
                callback.conversation_id,
                "⚠️ CONFIRMACIÓN PREVIA\n\n"
                + pending.summary
                + "\n\nDestino: " + pending.destination
                + "\nRareza: " + pending.rarity
                + "\nCosto: " + str(pending.cost) + " puntos\n\n"
                + "No se cobrará nada hasta pulsar [✅ Confirmar].",
                "bebida_confirmation",
                (((("✅ Confirmar", "order:confirm"), ("❌ Cancelar", "order:cancel")),),),
            )
        if callback.data == "order:cancel":
            self._pending_orders.pop(callback.user_id, None)
            return TelegramOutbound(callback.conversation_id, "❌ Pedido cancelado. No se descontaron puntos.", "bebida")
        if callback.data == "order:confirm":
            pending = self._pending_orders.get(callback.user_id)
            if pending is None:
                return TelegramOutbound(callback.conversation_id, "⚠️ No hay un pedido pendiente de confirmación.", "bebida")
            quote = purchase_bebida_order(
                self._wallet_store,
                callback.user_id,
                existing=pending.rarity != "SPECIAL",
                target_rarity=pending.rarity,
            )
            if not quote.can_afford:
                return TelegramOutbound(callback.conversation_id, "❌ Saldo insuficiente al confirmar. No se descontaron puntos.", "bebida")
            self._pending_orders.pop(callback.user_id, None)
            self._last_orders[callback.user_id] = pending
            self._order_store.save(pending)
            admin_followup = self._admin_order_followup(pending)
            return TelegramOutbound(
                callback.conversation_id,
                "✅ Pedido " + pending.order_id + " confirmado.\n"
                + pending.destination + "\n"
                + pending.rarity + " · " + str(pending.cost) + " puntos descontados.",
                "bebida",
                (((("📣 Queja / Reembolso", "complaint:help"),)),),
                followups=(admin_followup,) if admin_followup is not None else (),
            )
        if callback.data == "complaint:help":
            return TelegramOutbound(
                callback.conversation_id,
                "📣 Para presentar un reclamo escribe /queja <texto>.\n"
                "Puedes solicitar reembolso, conversión a imagen o dejar una sugerencia.",
                "complaint",
            )
        if callback.data.startswith("order:attach:"):
            return self._order_attach(callback, callback.data.split(":", 2)[2])
        if callback.data.startswith("complaint:"):
            parts = callback.data.split(":", 2)
            if len(parts) != 3:
                raise TelegramInputError("invalid complaint callback")
            return self._complaint_response(callback, parts[1], parts[2])
        if callback.data == "tutorial:show":
            return TelegramOutbound(callback.conversation_id, build_tutorial_text(), "tutorial")
        text = actions.get(callback.data)
        if text is None:
            raise TelegramInputError("unknown Telegram callback")
        response = self._application.handle(ApplicationRequest(callback.user_id, callback.conversation_id, text))
        return self.from_response(callback.conversation_id, response)

    @staticmethod
    def from_response(chat_id: str, response: ApplicationResponse) -> TelegramOutbound:
        keyboard: tuple[tuple[tuple[str, str], ...], ...] = ()
        execution = response.execution
        evidence = getattr(execution, "evidence", None)
        if evidence is not None and getattr(evidence.coverage, "status", None) in {CoverageStatus.NO_ENCONTRADO, CoverageStatus.NO_ESTABLECIDO}:
            keyboard = ((("🔐 Usar API para esta consulta", "fallback:api"),), (("📋 Preparar prompt para otra IA", "fallback:prompt"),), (("⬅️ Menú", "menu:main"),))
        return TelegramOutbound(chat_id, response.text, response.decision.route.value, keyboard)


TelegramTransport = Callable[[str, dict[str, object], float], dict[str, object]]


def _http_post(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read(MAX_TELEGRAM_HTTP_RESPONSE_BYTES + 1)
            if len(raw_body) > MAX_TELEGRAM_HTTP_RESPONSE_BYTES:
                raise TelegramTransportError(
                    "Telegram response body exceeds safety limit"
                )
            decoded = json.loads(raw_body.decode("utf-8"))
    except HTTPError as error:
        status = error.code
        error.close()
        if status in {401, 403}:
            raise TelegramApiError("Telegram authentication or authorization failed") from error
        if status == 429 or status >= 500:
            raise TelegramHttpError(f"Telegram HTTP status {status}") from error
        raise TelegramApiError(f"Telegram HTTP status {status}") from error
    except (TimeoutError, URLError, OSError) as error:
        raise TelegramTransportError("Telegram transport failed") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TelegramTransportError("Telegram returned an invalid response") from error
    if not isinstance(decoded, dict):
        raise TelegramTransportError("Telegram returned an invalid response")
    return decoded


def _split_message(text: str, limit: int = 4096) -> tuple[str, ...]:
    if not text:
        raise TelegramInputError("Telegram text cannot be empty")
    if limit < 1:
        raise ValueError("message limit must be positive")
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit + 1)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return tuple(chunks)


class TelegramApiClient:
    def __init__(self, token: str, *, transport: TelegramTransport | None = None, timeout_seconds: float = 15.0, max_retries: int = 2, retry_delay_seconds: float = 1.0, sleeper: Callable[[float], None] = time.sleep) -> None:
        if not token:
            raise TelegramConfigurationError("Telegram token is required")
        if timeout_seconds <= 0 or max_retries < 0 or retry_delay_seconds < 0:
            raise TelegramConfigurationError("Telegram retry configuration is invalid")
        self._token, self._transport, self._timeout = token, transport or _http_post, timeout_seconds
        self._max_retries, self._retry_delay, self._sleeper = max_retries, retry_delay_seconds, sleeper

    @property
    def token(self) -> str:
        """Token actual; se utiliza sólo para derivar el hash del lock."""
        return self._token

    @classmethod
    def from_environment(cls) -> "TelegramApiClient":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured")
        return cls(token)

    def send(
        self,
        outbound: TelegramOutbound,
        *,
        start_chunk: int = 0,
        on_chunk_ack: Callable[[int, dict[str, object]], None] | None = None,
    ) -> dict[str, object]:
        if outbound.photo_file_id:
            result = self._call("sendPhoto", outbound.payload())
            if on_chunk_ack is not None:
                on_chunk_ack(1, result)
            return dict(result)
        chunks = _split_message(outbound.text)
        if start_chunk < 0 or start_chunk > len(chunks):
            raise TelegramInputError("invalid Telegram chunk index")
        result: dict[str, object] | None = None
        message_ids: list[int] = []
        for index in range(start_chunk, len(chunks)):
            chunk = chunks[index]
            payload = outbound.payload()
            payload["text"] = chunk
            if index < len(chunks) - 1:
                payload.pop("reply_markup", None)
            try:
                result = self._call("sendMessage", payload)
            except TelegramTransportError as error:
                raise TelegramPartialDeliveryError(index) from error
            message_id = result.get("message_id")
            if not isinstance(message_id, int) or isinstance(message_id, bool):
                nested = result.get("result")
                message_id = nested.get("message_id") if isinstance(nested, dict) else None
            if isinstance(message_id, int) and not isinstance(message_id, bool) and message_id > 0:
                message_ids.append(message_id)
            if on_chunk_ack is not None:
                on_chunk_ack(index + 1, result)
        final_result = dict(result) if result is not None else {"ok": True}
        final_result["_bot_ia_message_ids"] = tuple(message_ids)
        return final_result

    def delete_message(self, chat_id: str, message_id: int) -> dict[str, object]:
        chat_id = str(chat_id).strip()
        if not chat_id:
            raise TelegramInputError("chat_id cannot be empty")
        if not isinstance(message_id, int) or message_id < 1:
            raise TelegramInputError("message_id must be a positive integer")
        return self._call(
            "deleteMessage",
            {
                "chat_id": chat_id,
                "message_id": message_id,
            },
        )

    def ban_chat_member(self, chat_id: str, user_id: str) -> dict[str, object]:
        return self._call(
            "banChatMember",
            {"chat_id": str(chat_id), "user_id": int(user_id)},
        )

    def restrict_chat_member(self, chat_id: str, user_id: str, until_date: int) -> dict[str, object]:
        return self._call(
            "restrictChatMember",
            {
                "chat_id": str(chat_id),
                "user_id": int(user_id),
                "permissions": {"can_send_messages": False},
                "until_date": int(until_date),
            },
        )

    def answer_inline_query(self, query_id: str, result: dict[str, object]) -> dict[str, object]:
        if not str(query_id).strip():
            raise TelegramInputError("inline query id cannot be empty")
        return self._call(
            "answerInlineQuery",
            {
                "inline_query_id": str(query_id),
                "results": [result],
                "cache_time": 0,
                "is_personal": True,
            },
        )

    def get_updates(self, *, offset: int | None = None, timeout_seconds: int = 25) -> tuple[dict[str, object], ...]:
        if offset is not None and offset < 0:
            raise TelegramInputError("Telegram offset cannot be negative")
        if timeout_seconds < 0 or timeout_seconds > 50:
            raise TelegramInputError("Telegram polling timeout must be between 0 and 50 seconds")
        payload: dict[str, object] = {"timeout": timeout_seconds}
        if offset is not None:
            payload["offset"] = offset
        response = self._call("getUpdates", payload, timeout_seconds=max(self._timeout, timeout_seconds + 5))
        updates = response.get("result")
        if not isinstance(updates, list) or not all(isinstance(update, dict) for update in updates):
            raise TelegramApiError("Telegram getUpdates response is invalid")
        return tuple(updates)

    def smoke_test(self) -> bool:
        response = self._call("getMe", {})
        return response.get("ok") is True

    def _call(self, method: str, payload: dict[str, object], *, timeout_seconds: float | None = None) -> dict[str, object]:
        timeout = self._timeout if timeout_seconds is None else timeout_seconds
        for attempt in range(self._max_retries + 1):
            try:
                response = self._transport(f"https://api.telegram.org/bot{self._token}/{method}", payload, timeout)
            except (TelegramTransportError, TimeoutError, OSError) as error:
                if attempt >= self._max_retries:
                    raise TelegramTransportError("Telegram transport failed after controlled retries") from error
                self._sleeper(self._retry_delay)
                continue
            if not isinstance(response, dict) or response.get("ok") is not True:
                raise TelegramApiError("Telegram API returned an error")
            return response
        raise AssertionError("unreachable")


@dataclass(frozen=True, slots=True)
class PollingConfig:
    poll_timeout_seconds: int = 25
    idle_delay_seconds: float = 1.0
    retry_delay_seconds: float = 2.0
    max_consecutive_failures: int = 3

    def __post_init__(self) -> None:
        if not 0 <= self.poll_timeout_seconds <= 50 or self.idle_delay_seconds < 0 or self.retry_delay_seconds < 0 or self.max_consecutive_failures < 1:
            raise ValueError("invalid Telegram polling configuration")


@dataclass(frozen=True, slots=True)
class PollingResult:
    polls: int
    updates_received: int
    updates_processed: int
    updates_skipped: int
    responses_sent: int
    transport_errors: int
    stopped: bool


class TelegramPoller:
    def __init__(
        self,
        client: TelegramApiClient,
        adapter: TelegramAdapter,
        *,
        config: PollingConfig | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        logger: Callable[[str], None] | None = None,
        outbox_store: TelegramOutboxStore | None = None,
        event_ledger: TelegramEventLedger | None = None,
        instance_lock: TelegramInstanceLock | None = None,
    ) -> None:
        self._client, self._adapter, self._config = client, adapter, config or PollingConfig()
        self._sleeper, self._logger, self._running, self._offset = sleeper, logger or (lambda _: None), True, None
        self._outbox = outbox_store
        self._event_ledger = event_ledger or TelegramEventLedger(
            PROJECT_ROOT / "config" / "bot_ia_events.sqlite3"
        )
        self._instance_lock = instance_lock or TelegramInstanceLock(
            self._client.token,
            PROJECT_ROOT,
        )
        self._callback_mutex = MutexGuard()
        self._pending_delivery: tuple[TelegramOutboxRecord, tuple[int, ...]] | None = None

    @property
    def offset(self) -> int | None:
        return self._offset

    def stop(self) -> None:
        self._running = False

    @staticmethod
    def _message_ids_from_result(result: object) -> tuple[int, ...]:
        if not isinstance(result, dict):
            return ()
        raw_ids = result.get("_bot_ia_message_ids")
        if isinstance(raw_ids, (list, tuple)):
            ids: list[int] = []
            for value in raw_ids:
                if isinstance(value, int) and not isinstance(value, bool) and value > 0 and value not in ids:
                    ids.append(value)
            if ids:
                return tuple(ids)

        value = result.get("message_id")
        if not isinstance(value, int) or isinstance(value, bool):
            nested = result.get("result")
            value = nested.get("message_id") if isinstance(nested, dict) else None
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return (value,)
        return ()

    @classmethod
    def _append_message_ids(
        cls,
        target: list[int],
        result: object,
    ) -> None:
        for message_id in cls._message_ids_from_result(result):
            if message_id not in target:
                target.append(message_id)

    def _schedule_auto_delete_if_needed(
        self,
        outbound: TelegramOutbound,
        message_ids: list[int] | tuple[int, ...],
    ) -> None:
        auto_delete = outbound.auto_delete_seconds
        schedule = getattr(
            self._adapter,
            "schedule_tavern_auto_delete",
            None,
        )
        if not isinstance(auto_delete, int) or auto_delete <= 0:
            return
        if not callable(schedule):
            return
        for message_id in tuple(dict.fromkeys(message_ids)):
            if isinstance(message_id, int) and not isinstance(message_id, bool) and message_id > 0:
                schedule(
                    outbound.chat_id,
                    message_id,
                    auto_delete,
                )

    def _comment_raw_update(self, update: dict[str, object]) -> TelegramOutbound | None:
        decision = analyze_telegram_comment(update)
        if not decision.should_reply:
            return None
        return TelegramOutbound(
            decision.chat_id,
            decision.text,
            "comments",
            reply_to_message_id=decision.reply_to_message_id,
            auto_delete_seconds=30,
        )

    def _moderate_raw_update(self, update: dict[str, object]) -> TelegramOutbound | None:
        message = update.get("message")
        if not isinstance(message, dict):
            return None
        chat = message.get("chat")
        sender = message.get("from")
        if not isinstance(chat, dict) or not isinstance(sender, dict):
            return None
        text = message.get("text") or message.get("caption") or ""
        if not isinstance(text, str):
            text = ""
        room_resolver = getattr(self._adapter, "room_key_for_update", None)
        if callable(room_resolver):
            room_key = room_resolver(update)
        else:
            room_key = str(update.get("room_key", "general"))
        username = str(sender.get("username", "") or "")
        raw_tags = message.get("image_tags", ())
        image_tags = tuple(tag for tag in raw_tags if isinstance(tag, str)) if isinstance(raw_tags, (list, tuple)) else ()
        cami_decision = supervise_admin_publication(
            text,
            image_tags=image_tags,
            user_id=str(sender.get("id", "")),
            username=username,
            content_kind=str(message.get("content_kind", "text")),
            target_room=room_key,
        )
        if is_superadmin(str(sender.get("id", "")), username) and cami_decision.action not in {"allow", "allow_react"}:
            chat_id = str(chat.get("id", "")).strip()
            message_id = message.get("message_id")
            if not chat_id or not isinstance(message_id, int):
                return None
            try:
                self._client.delete_message(chat_id, message_id)
            except (TelegramTransportError, TelegramApiError, TelegramInputError) as error:
                self._logger(f"telegram Cami Guard action failed: {error}")
            return TelegramOutbound(
                chat_id,
                cami_decision.message,
                cami_decision.target_room or room_key,
                auto_delete_seconds=30,
            )
        decision = moderate(text, room_key=room_key)
        if decision.action == "allow":
            return None
        chat_id = str(chat.get("id", "")).strip()
        message_id = message.get("message_id")
        user_id = sender.get("id")
        if not chat_id or not isinstance(message_id, int) or not isinstance(user_id, int):
            return None
        try:
            self._client.delete_message(chat_id, message_id)
            if decision.action == "ban" and not is_superadmin(str(user_id), str(sender.get("username", ""))):
                self._client.ban_chat_member(chat_id, str(user_id))
        except (TelegramTransportError, TelegramApiError, TelegramInputError) as error:
            self._logger(f"telegram moderation action failed: {error}")
        if decision.action == "ban":
            return TelegramOutbound(chat_id, decision.message, room_key, auto_delete_seconds=30)
        return TelegramOutbound(
            chat_id,
            decision.message,
            decision.target_room or room_key,
            auto_delete_seconds=30,
        )

    @staticmethod
    def _callback_key(update: dict[str, object]) -> str:
        callback = update.get("callback_query")
        if not isinstance(callback, dict):
            return ""
        user = callback.get("from")
        message = callback.get("message")
        user_id = user.get("id") if isinstance(user, dict) else ""
        chat = message.get("chat") if isinstance(message, dict) else None
        chat_id = chat.get("id") if isinstance(chat, dict) else ""
        message_id = message.get("message_id") if isinstance(message, dict) else ""
        data = callback.get("data", "")
        if user_id == "" or chat_id == "" or message_id == "" or not isinstance(data, str):
            return ""
        return f"telegram:button:{user_id}:{chat_id}:{message_id}:{data}"

    def _event_ids(self, update_id: int, update: dict[str, object]) -> tuple[tuple[str, str], ...]:
        events = [("update_id", str(update_id))]
        message = update.get("message")
        if isinstance(message, dict):
            payment = message.get("successful_payment")
            if isinstance(payment, dict):
                charge_id = str(
                    payment.get("telegram_payment_charge_id", "")
                ).strip()
                if charge_id:
                    events.append(("telegram_payment_charge_id", charge_id))
        return tuple(events)

    def _claim_event(self, update_id: int, update: dict[str, object]) -> tuple[bool, bool]:
        event_ids = self._event_ids(update_id, update)
        for event_type, event_id in event_ids:
            try:
                if self._event_ledger.seen(event_type, event_id):
                    return False, True
            except TelegramEventLedgerError:
                raise

        for event_type, event_id in event_ids:
            if not self._event_ledger.claim(
                event_type,
                event_id,
                update_id=update_id,
            ):
                return False, True
        return True, False

    def _mark_events_completed(
        self,
        update_id: int,
        update: dict[str, object],
    ) -> None:
        for event_type, event_id in self._event_ids(update_id, update):
            self._event_ledger.mark_completed(
                event_type,
                event_id,
            )

    def _send_outbox_record(
        self,
        record: TelegramOutboxRecord,
        *,
        message_ids: list[int] | None = None,
    ) -> bool:
        ids = message_ids if message_ids is not None else []
        try:
            def acknowledge(
                acknowledged: int,
                result: dict[str, object],
            ) -> None:
                if record.kind == "main":
                    self._outbox.ack_chunk(record.update_id, acknowledged)
                else:
                    self._outbox.ack_followup_chunk(
                        record.delivery_id,
                        acknowledged,
                    )
                self._append_message_ids(ids, result)

            result = self._client.send(
                record.outbound,
                start_chunk=record.next_chunk,
                on_chunk_ack=acknowledge,
            )
            self._append_message_ids(ids, result)
            self._schedule_auto_delete_if_needed(
                record.outbound,
                ids,
            )
            if record.kind == "main":
                self._outbox.mark_delivered(record.update_id)
            else:
                self._outbox.mark_followup_delivered(record.delivery_id)
            return True
        except TelegramPartialDeliveryError as error:
            self._logger(
                f"telegram {record.kind} delivery partial failure at "
                f"chunk {error.next_chunk_index}"
            )
            self._sleeper(self._config.retry_delay_seconds)
            return False
        except TelegramTransportError as error:
            self._logger(
                f"telegram {record.kind} delivery transport failure: "
                f"{type(error).__name__}"
            )
            self._sleeper(self._config.retry_delay_seconds)
            return False

    def _drain_update_outbox(self, update_id: int) -> bool:
        if self._outbox is None:
            return True
        while True:
            pending = self._outbox.pending_for_update(update_id)
            if not pending:
                return self._outbox.all_delivered(update_id)
            record = pending[0]
            if not self._send_outbox_record(record):
                return False

    def run(self, *, max_cycles: int | None = None) -> PollingResult:
        if max_cycles is not None and max_cycles < 0:
            raise ValueError("max_cycles cannot be negative")

        polls = received = processed = skipped = sent = errors = cycles = consecutive_failures = 0
        acquired = False
        try:
            self._instance_lock.acquire()
            acquired = True
            while self._running and (
                max_cycles is None or cycles < max_cycles
            ):
                cycles += 1

                # Primero recupera entregas durables, incluso después de un
                # cierre abrupto donde Telegram ya había entregado el update.
                if self._outbox is not None:
                    pending_records = self._outbox.pending_unfinished(limit=20)
                    if pending_records:
                        recovered = True
                        for record in pending_records:
                            if not self._send_outbox_record(record):
                                recovered = False
                                break
                            if self._outbox.all_delivered(record.update_id):
                                self._offset = max(
                                    self._offset or 0,
                                    record.update_id + 1,
                                )
                        if not recovered:
                            continue

                try:
                    updates = self._client.get_updates(
                        offset=self._offset,
                        timeout_seconds=self._config.poll_timeout_seconds,
                    )
                except TelegramTransportError:
                    errors += 1
                    consecutive_failures += 1
                    self._logger("telegram polling transport error")
                    if consecutive_failures >= self._config.max_consecutive_failures:
                        self.stop()
                        break
                    self._sleeper(self._config.retry_delay_seconds)
                    continue

                polls += 1
                consecutive_failures = 0
                received += len(updates)

                for update in updates:
                    update_id = update.get("update_id")
                    if (
                        not isinstance(update_id, int)
                        or (
                            self._offset is not None
                            and update_id < self._offset
                        )
                    ):
                        skipped += 1
                        self._logger("telegram update skipped")
                        continue

                    callback_key = self._callback_key(update)
                    if (
                        callback_key
                        and not self._callback_mutex.try_acquire(callback_key)
                    ):
                        skipped += 1
                        errors += 1
                        self._logger(
                            "telegram callback duplicate/concurrent delivery skipped"
                        )
                        break

                    try:
                        claimed, already_seen = self._claim_event(
                            update_id,
                            update,
                        )
                    except TelegramEventLedgerError:
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        errors += 1
                        self._logger(
                            "telegram event ledger unavailable; offset preserved"
                        )
                        self._sleeper(self._config.retry_delay_seconds)
                        break

                    if already_seen:
                        # The effect has already been claimed/completed. Never
                        # re-enter application/economy logic. Only durable
                        # deliveries may still need recovery.
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        if self._outbox is not None:
                            if self._drain_update_outbox(update_id):
                                if self._outbox.all_delivered(update_id):
                                    self._offset = update_id + 1
                                    skipped += 1
                                    continue
                                errors += 1
                                break
                        self._offset = update_id + 1
                        skipped += 1
                        continue

                    if not claimed:
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        errors += 1
                        self._logger(
                            "telegram event could not be claimed; offset preserved"
                        )
                        break

                    try:
                        sync_authorized_bot_join = getattr(
                            self._adapter,
                            "_sync_authorized_bot_join",
                            None,
                        )
                        if callable(sync_authorized_bot_join):
                            sync_authorized_bot_join(update)

                        outbound: TelegramOutbound | None = None
                        moderation_outbound: TelegramOutbound | None = None
                        inline_query = update.get("inline_query")
                        if isinstance(inline_query, dict):
                            inline = parse_inline_query_update(update)
                            result = self._inline_handler.handle(
                                user_id=inline.user_id,
                                query=inline.query,
                                chat_id=inline.chat_id,
                            )
                            self._client.answer_inline_query(
                                inline.query_id,
                                {
                                    "type": "article",
                                    "id": "cafe-redirect",
                                    "title": "☕ Café Otaku",
                                    "description": result.text,
                                    "input_message_content": {
                                        "message_text": result.text
                                    },
                                    "reply_markup": {
                                        "inline_keyboard": [[
                                            {
                                                "text": result.button_label,
                                                "url": result.button_url,
                                            }
                                        ]]
                                    },
                                },
                            )
                            self._mark_events_completed(update_id, update)
                            if callback_key:
                                self._callback_mutex.release(callback_key)
                            self._offset = update_id + 1
                            processed += 1
                            sent += 1
                            continue
                        moderation_outbound = self._moderate_raw_update(update)
                        comment_outbound = (
                            None
                            if moderation_outbound is not None
                            else self._comment_raw_update(update)
                        )
                        if moderation_outbound is not None:
                            outbound = moderation_outbound
                        elif comment_outbound is not None:
                            outbound = comment_outbound
                        elif (
                            isinstance(update.get("message"), dict)
                            and isinstance(
                                update["message"].get("photo"),
                                list,
                            )
                        ):
                            outbound = self._adapter.handle_photo_update(update)
                        else:
                            outbound = self._adapter.handle_update(update)
                    except TelegramInputError:
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        self._event_ledger.mark_completed(
                            "update_id",
                            str(update_id),
                            metadata="input_rejected",
                        )
                        self._offset = update_id + 1
                        skipped += 1
                        continue
                    except Exception as error:
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        errors += 1
                        self._logger(
                            f"telegram update processing failed: "
                            f"{type(error).__name__}; event claim retained"
                        )
                        self._sleeper(
                            max(
                                self._config.retry_delay_seconds,
                                0.1,
                            )
                        )
                        break

                    if outbound is None:
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        self._mark_events_completed(update_id, update)
                        self._offset = update_id + 1
                        processed += 1
                        continue

                    try:
                        if self._outbox is not None:
                            self._outbox.create_pending(
                                update_id,
                                outbound,
                            )
                            self._outbox.create_followups(
                                update_id,
                                outbound.followups,
                            )
                            # Once the durable output exists, the event itself
                            # is safe to consider claimed/completed. A crash
                            # before sending is recovered from the outbox.
                            self._mark_events_completed(
                                update_id,
                                update,
                            )
                            delivered = self._drain_update_outbox(update_id)
                            if not delivered:
                                if callback_key:
                                    self._callback_mutex.release(callback_key)
                                errors += 1
                                break
                        else:
                            message_ids: list[int] = []
                            result = self._client.send(outbound)
                            self._append_message_ids(message_ids, result)
                            self._schedule_auto_delete_if_needed(
                                outbound,
                                message_ids,
                            )
                            self._mark_events_completed(
                                update_id,
                                update,
                            )
                    except TelegramOutboxError as error:
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        errors += 1
                        self._logger(
                            f"telegram outbox persistence failure: {type(error).__name__}"
                        )
                        self._sleeper(self._config.retry_delay_seconds)
                        break
                    except TelegramTransportError:
                        errors += 1
                        if callback_key:
                            self._callback_mutex.release(callback_key)
                        # The outbox already owns the unsent unit; no effect is
                        # re-entered on replay.
                        if self._outbox is not None:
                            self._sleeper(
                                self._config.retry_delay_seconds
                            )
                            break
                        self._sleeper(
                            self._config.retry_delay_seconds
                        )
                        break

                    if callback_key:
                        self._callback_mutex.release(callback_key)

                    if self._outbox is None or self._outbox.all_delivered(update_id):
                        self._offset = update_id + 1
                        processed += 1
                        sent += 1
                    else:
                        errors += 1
                        break

                if self._running and not updates:
                    self._sleeper(self._config.idle_delay_seconds)
        finally:
            if acquired:
                self._instance_lock.release()

        return PollingResult(
            polls,
            received,
            processed,
            skipped,
            sent,
            errors,
            not self._running,
        )
