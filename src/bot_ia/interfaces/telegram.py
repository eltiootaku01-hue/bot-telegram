# -*- coding: utf-8 -*-
"""Capa de Telegram: conversación natural + menús contextuales sin hoja de comandos."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bot_ia.core.application import ApplicationRequest, ApplicationResponse, BotApplication
from bot_ia.core.waitress_session_manager import TavernError, TavernReply, WaitressSessionManager
from bot_ia.librarian.models import CoverageStatus

from .telegram_outbox import TelegramOutboxError, TelegramOutboxStore
from .group_setup import GroupSetupError, GroupSetupStore, TelegramGroupSetup
from .cafe_orders import BebidaOrderFlow, build_bebida_summary
from .hardening import MutexGuard
from .order_support import ComplaintStore, OrderConfirmation, new_order_id, order_destination
from .auto_moderation import moderate
from .cafe_economy import CafeWalletStore, draw_gacha, economy_price_text, pity_text, purchase_bebida_order, quote_bebida_order
from .cafe_immersion import waitress_dialogue, waitress_exclusive_dialogue
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
    followups: tuple["TelegramOutbound", ...] = ()

    def payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"chat_id": self.chat_id, "text": self.text}
        if self.message_thread_id is not None:
            payload["message_thread_id"] = int(self.message_thread_id)
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
    return TelegramInbound(user_id, chat_id, text)


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
    )

    def __init__(
        self,
        application: BotApplication,
        *,
        tavern_manager: WaitressSessionManager | None = None,
    ) -> None:
        self._application = application
        self._tavern_manager = tavern_manager
        self._wallet_store = CafeWalletStore(Path.cwd())
        self._waifu_registry = WaifuRegistry(Path.cwd())
        self._bebida_flow = BebidaOrderFlow(
            allowed_tags=self._waifu_registry.danbooru_whitelist(),
        )
        self._complaint_store = ComplaintStore(Path.cwd())
        self._pending_orders: dict[str, OrderConfirmation] = {}
        self._last_orders: dict[str, OrderConfirmation] = {}
        self._callback_mutex = MutexGuard()

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

    def _admin_followup(self, complaint) -> TelegramOutbound | None:
        admin_chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
        if not admin_chat:
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

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" in update:
            return self.handle_callback(update)
        inbound = parse_update(update)
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
        if command in {"/21", "/blackjack", "/apuestas", "/apuesta"}:
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
                    GroupSetupStore(Path.cwd()),
                )
                summary = "\n".join(
                    f"• {room.name} → topic {room.external_id}"
                    for room in result.rooms
                )
                feeds = GroupSetupStore(Path.cwd()).get_feeds("telegram", inbound.conversation_id)
                feed_text = "\n".join(f"• {name}: {url}" for name, url in feeds)
                privacy_note = (
                    "\n\n⚠️ Telegram: #pedidos se crea como tema del foro; "
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
                    "🥤 Elige producto:",
                    "bebida",
                    ((("Carta TCG", "bebida:product_type:Carta TCG"), ("Naipe", "bebida:product_type:Naipe")), (("Waifumon", "bebida:product_type:Waifumon"),)),
                )
            quote = quote_bebida_order(
                existing=True,
                target_rarity="R",
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
                existing=True,
                target_rarity=pending.rarity,
            )
            if not quote.can_afford:
                return TelegramOutbound(callback.conversation_id, "❌ Saldo insuficiente al confirmar. No se descontaron puntos.", "bebida")
            self._pending_orders.pop(callback.user_id, None)
            self._last_orders[callback.user_id] = pending
            return TelegramOutbound(
                callback.conversation_id,
                "✅ Pedido " + pending.order_id + " confirmado.\n"
                + pending.destination + "\n"
                + pending.rarity + " · " + str(pending.cost) + " puntos descontados.",
                "bebida",
                (((("📣 Queja / Reembolso", "complaint:help"),)),),
            )
        if callback.data == "complaint:help":
            return TelegramOutbound(
                callback.conversation_id,
                "📣 Para presentar un reclamo escribe /queja <texto>.\n"
                "Puedes solicitar reembolso, conversión a imagen o dejar una sugerencia.",
                "complaint",
            )
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
    ) -> None:
        self._client, self._adapter, self._config = client, adapter, config or PollingConfig()
        self._sleeper, self._logger, self._running, self._offset = sleeper, logger or (lambda _: None), True, None
        self._outbox = outbox_store
        self._pending_delivery: tuple[int, TelegramOutbound, int, tuple[int, ...]] | None = None

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
        room_key = str(update.get("room_key", "general"))
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
            if decision.action == "ban":
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

    def run(self, *, max_cycles: int | None = None) -> PollingResult:
        if max_cycles is not None and max_cycles < 0:
            raise ValueError("max_cycles cannot be negative")
        polls = received = processed = skipped = sent = errors = cycles = consecutive_failures = 0
        while self._running and (max_cycles is None or cycles < max_cycles):
            cycles += 1

            if self._pending_delivery is not None:
                pending_id, pending_outbound, next_chunk, pending_message_ids = self._pending_delivery
                message_ids = list(pending_message_ids)

                def acknowledge_pending_chunk(
                    acknowledged: int,
                    chunk_result: dict[str, object],
                ) -> None:
                    if self._outbox is None:
                        return
                    self._outbox.ack_chunk(pending_id, acknowledged)
                    self._append_message_ids(message_ids, chunk_result)

                try:
                    result = self._client.send(
                        pending_outbound,
                        start_chunk=next_chunk,
                        on_chunk_ack=acknowledge_pending_chunk,
                    )
                    self._append_message_ids(message_ids, result)
                    self._schedule_auto_delete_if_needed(
                        pending_outbound,
                        message_ids,
                    )
                except TelegramPartialDeliveryError as error:
                    errors += 1
                    self._pending_delivery = (
                        pending_id,
                        pending_outbound,
                        error.next_chunk_index,
                        tuple(message_ids),
                    )
                    self._logger(
                        "telegram pending response delivery failed after partial send"
                    )
                    self._sleeper(self._config.retry_delay_seconds)
                    continue
                except TelegramTransportError:
                    errors += 1
                    self._logger(
                        "telegram pending response delivery failed"
                    )
                    self._sleeper(self._config.retry_delay_seconds)
                    continue
                except (TelegramApiError, TelegramInputError):
                    self._pending_delivery = None
                    self._offset = pending_id + 1
                    skipped += 1
                    self._logger(
                        "telegram pending response rejected"
                    )
                    continue

                if self._outbox is not None:
                    try:
                        self._outbox.mark_delivered(pending_id)
                    except TelegramOutboxError:
                        errors += 1
                        self._logger("telegram outbox could not mark pending update delivered")
                        self._sleeper(self._config.retry_delay_seconds)
                        continue
                self._pending_delivery = None
                self._offset = pending_id + 1
                processed += 1
                sent += 1
                continue

            try:
                updates = self._client.get_updates(
                    offset=self._offset,
                    timeout_seconds=self._config.poll_timeout_seconds,
                )
            except TelegramTransportError:
                errors += 1
                consecutive_failures += 1
                self._logger(
                    "telegram polling transport error"
                )
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
                if callback_key and not self._callback_mutex.try_acquire(callback_key):
                    self._offset = update_id + 1
                    skipped += 1
                    self._logger("telegram callback dropped by local mutex")
                    continue

                if self._outbox is not None:
                    try:
                        existing = self._outbox.get(update_id)
                    except TelegramOutboxError:
                        existing = None
                        self._logger("telegram outbox record is corrupt; update will be reprocessed")
                    if existing is not None:
                        if existing.status == "DELIVERED":
                            if callback_key:
                                self._callback_mutex.release(callback_key)
                            self._offset = update_id + 1
                            skipped += 1
                            continue
                        if existing.status == "PENDING":
                            if callback_key:
                                self._callback_mutex.release(callback_key)
                            self._pending_delivery = (
                                update_id,
                                existing.outbound,
                                existing.next_chunk,
                                (),
                            )
                            break

                try:
                    moderation_outbound = self._moderate_raw_update(update)
                    outbound = (
                        moderation_outbound
                        if moderation_outbound is not None
                        else self._adapter.handle_update(update)
                    )
                except TelegramInputError:
                    if callback_key:
                        self._callback_mutex.release(callback_key)
                    self._offset = update_id + 1
                    skipped += 1
                    self._logger("telegram update rejected")
                    continue
                except Exception as error:
                    if callback_key:
                        self._callback_mutex.release(callback_key)
                    self._offset = update_id + 1
                    skipped += 1
                    self._logger(
                        f"telegram update processing failed: {type(error).__name__}"
                    )
                    continue

                try:
                    message_ids: list[int] = []
                    if self._outbox is not None:
                        record = self._outbox.create_pending(update_id, outbound)
                        start_chunk = record.next_chunk

                        def acknowledge_chunk(
                            acknowledged: int,
                            chunk_result: dict[str, object],
                        ) -> None:
                            self._outbox.ack_chunk(update_id, acknowledged)
                            self._append_message_ids(message_ids, chunk_result)

                        result = self._client.send(
                            outbound,
                            start_chunk=start_chunk,
                            on_chunk_ack=acknowledge_chunk,
                        )
                    else:
                        result = self._client.send(outbound)
                    self._append_message_ids(message_ids, result)
                    self._schedule_auto_delete_if_needed(
                        outbound,
                        message_ids,
                    )
                    if self._outbox is not None:
                        self._outbox.mark_delivered(update_id)
                    for followup in outbound.followups:
                        try:
                            self._client.send(followup)
                        except TelegramTransportError as error:
                            self._logger(
                                f"telegram followup delivery failed: {type(error).__name__}"
                            )
                except TelegramPartialDeliveryError as error:
                    self._pending_delivery = (
                        update_id,
                        outbound,
                        error.next_chunk_index,
                        tuple(message_ids),
                    )
                    if callback_key:
                        self._callback_mutex.release(callback_key)
                    self._logger(
                        "telegram response delivery deferred after partial send"
                    )
                    break
                except TelegramTransportError:
                    self._pending_delivery = (
                        update_id,
                        outbound,
                        0,
                        tuple(message_ids),
                    )
                    if callback_key:
                        self._callback_mutex.release(callback_key)
                    self._logger(
                        "telegram response delivery deferred for retry"
                    )
                    break
                except (TelegramApiError, TelegramInputError):
                    if self._outbox is not None:
                        try:
                            self._outbox.mark_failed(update_id)
                        except TelegramOutboxError:
                            self._logger("telegram outbox could not mark update failed")
                    self._offset = update_id + 1
                    skipped += 1
                    if callback_key:
                        self._callback_mutex.release(callback_key)
                    self._logger(
                        "telegram response delivery rejected"
                    )
                    continue

                if callback_key:
                    self._callback_mutex.release(callback_key)
                self._offset = update_id + 1
                processed += 1
                sent += 1

            if self._running and not updates:
                self._sleeper(self._config.idle_delay_seconds)

        return PollingResult(
            polls,
            received,
            processed,
            skipped,
            sent,
            errors,
            not self._running,
        )
