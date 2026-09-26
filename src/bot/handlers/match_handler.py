# -*- coding: utf-8 -*-

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import ActiveMatch, User
from src.services.match_service import accept_match_challenge, create_match_challenge

logger = logging.getLogger(__name__)
engine = create_engine("sqlite:///bot_database.db", echo=False)


def get_or_create_user(session: Session, telegram_user) -> User:
    """Busca al usuario en la BD o lo registra si es su primera interacción."""
    user = session.get(User, telegram_user.id)
    if not user:
        user = User(
            id=telegram_user.id,
            username=telegram_user.username or telegram_user.first_name
        )
        session.add(user)
        session.commit()
    return user


async def duel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja el comando /duelo en un grupo o supergrupo.
    Soporta:
    - /duelo (Reto abierto a cualquiera en el grupo)
    - Responder a un mensaje con /duelo (Reto directo al autor del mensaje)
    """
    chat = update.effective_chat
    user_p1 = update.effective_user

    # Solo se permite lanzar duelos en grupos o supergrupos
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Los duelos solo pueden organizarse en grupos bajo la supervisión de las meseras.")
        return

    # Verificar si el reto es directo a un usuario mediante respuesta a mensaje
    player2_id = None
    target_name = "Cualquiera en el grupo"

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        if target_user.id == user_p1.id:
            await update.message.reply_text("❌ No puedes desafiarte a ti mismo.")
            return
        if target_user.is_bot:
            await update.message.reply_text("❌ Las meseras no permiten duelos contra bots de la taberna.")
            return

        player2_id = target_user.id
        target_name = target_user.first_name

    with Session(engine) as session:
        # Asegurar que el retador exista en la BD
        get_or_create_user(session, user_p1)

        # Crear el reto a través de match_service.py
        success, message, new_match = create_match_challenge(
            session=session,
            group_id=chat.id,
            player1_id=user_p1.id,
            player2_id=player2_id,
            message_thread_id=update.message.message_thread_id
        )

        if not success:
            await update.message.reply_text(message, parse_mode="Markdown")
            return

        # Botonera interactiva para aceptar o cancelar
        keyboard = [
            [
                InlineKeyboardButton("⚔️ Aceptar Duelo", callback_data=f"accept_duel:{new_match.id}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"decline_duel:{new_match.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Construir el mensaje de la Mesera
        full_text = (
            f"{message}\n\n"
            f"👤 **Retador:** {user_p1.first_name}\n"
            f"🎯 **Desafiado:** {target_name}\n"
            f"⏱️ **Tiempo límite:** 90 segundos"
        )

        await update.message.reply_text(
            text=full_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


async def accept_duel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa el clic en el botón 'Aceptar Duelo' con validaciones de seguridad en el Handler."""
    query = update.callback_query
    match_id = query.data.split(":", 1)[1]
    user_p2 = query.from_user
    current_chat_id = query.message.chat.id

    with Session(engine) as session:
        match = session.get(ActiveMatch, match_id)

        if not match:
            await query.answer("Este duelo ya no existe o fue cancelado.", show_alert=True)
            return

        # 1. Validación de contexto de Chat/Grupo
        if match.group_id != current_chat_id:
            await query.answer("❌ Este duelo pertenece a otro grupo.", show_alert=True)
            return

        # 2. Validación de Auto-Desafío
        if user_p2.id == match.player1_id:
            await query.answer("❌ No puedes aceptar tu propio reto.", show_alert=True)
            return

        # 3. Validación de Autorización para Reto Directo
        if match.player2_id and match.player2_id != 0 and user_p2.id != match.player2_id:
            await query.answer("❌ Este reto fue enviado a otra persona.", show_alert=True)
            return

        # Asegurar que el jugador 2 esté registrado
        get_or_create_user(session, user_p2)

        # Intentar aceptar el reto en la capa de servicio
        success, result_message = accept_match_challenge(
            session=session,
            match_id=match_id,
            player2_id=user_p2.id
        )

        if not success:
            if "expirado" in result_message.lower() or "no está disponible" in result_message.lower():
                await query.edit_message_text(text=f"❌ {result_message}", reply_markup=None, parse_mode="Markdown")
            else:
                await query.answer(text=f"⚠️ {result_message}", show_alert=True)
            return

        # Refrescar la instancia tras confirmación
        session.refresh(match)

        updated_text = (
            f"✨ **¡DUELO CONFIRMADO!** ✨\n\n"
            f"{result_message}\n\n"
            f"🎲 **Mesera asignada:** {match.referee_name}\n"
            f"❤️ **Jugador 1:** HP {match.p1_hp}/100\n"
            f"💙 **Jugador 2:** HP {match.p2_hp}/100\n\n"
            f"💬 *Usen los comandos de batalla para atacar.*"
        )

        await query.answer()
        await query.edit_message_text(text=updated_text, reply_markup=None, parse_mode="Markdown")


async def decline_duel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa la cancelación o rechazo del duelo con autorizaciones estrictas."""
    query = update.callback_query
    match_id = query.data.split(":", 1)[1]
    user_clicking = query.from_user
    current_chat_id = query.message.chat.id

    with Session(engine) as session:
        match = session.get(ActiveMatch, match_id)

        if not match or match.status != "WAITING":
            await query.answer("Esta mesa ya no está disponible.", show_alert=True)
            return

        # 1. Validación de contexto de Chat/Grupo
        if match.group_id != current_chat_id:
            await query.answer("❌ Este duelo pertenece a otro grupo.", show_alert=True)
            return

        # 2. Validación de Autorización para Cancelar
        is_direct_challenge = match.player2_id and match.player2_id != 0
        allowed_users = [match.player1_id, match.player2_id] if is_direct_challenge else [match.player1_id]

        if user_clicking.id not in allowed_users:
            await query.answer("❌ Solo los participantes de este duelo pueden cancelarlo.", show_alert=True)
            return

        referee = match.referee_name
        match.status = "CANCELLED"
        match.staked_card_instance_id = None
        session.commit()

        await query.answer("Duelo cancelado.")
        await query.edit_message_text(
            text=f"☕ *{referee} acomoda las cartas*: «Duelo cancelado. Mesa libre para el siguiente pedido.»",
            reply_markup=None,
            parse_mode="Markdown"
        )


def register_match_handlers(app: Application) -> None:
    """Registra los handlers del módulo de duelos en la aplicación del bot."""
    app.add_handler(CommandHandler("duelo", duel_command))
    app.add_handler(CallbackQueryHandler(accept_duel_callback, pattern=r"^accept_duel:"))
    app.add_handler(CallbackQueryHandler(decline_duel_callback, pattern=r"^decline_duel:"))
