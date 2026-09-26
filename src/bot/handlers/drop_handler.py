# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from src.services.drop_service import spawn_card_drop, claim_card_drop

# Configuración de motor de base de datos para los handlers
engine = create_engine("sqlite:///bot_database.db", echo=False)


async def cmd_spawn_drop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando de prueba (/drop) para forzar la aparición de una carta en el grupo o tema.
    """
    if not update.effective_chat or not update.effective_message:
        return

    chat_id = update.effective_chat.id
    # Obtiene el ID del tema/topic si la función de foros está activa en el grupo
    message_thread_id = update.effective_message.message_thread_id

    with Session(engine) as session:
        drop, card_instance, card = spawn_card_drop(
            session=session,
            group_id=chat_id,
            message_thread_id=message_thread_id
        )

        # Botón con callback conteniendo el ID único del drop
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎴 ¡Reclamar Carta!", callback_data=f"claim_drop:{drop.id}")]
        ])

        caption = (
            f"✨ **¡UNA CARTA SILVESTRE HA APARECIDO!** ✨

"
            f"🎴 **Personaje:** {card.name}
"
            f"⭐ **Rareza:** {card.rarity}
"
            f"🌊 **Elemento:** {card.element or 'Neutro'}

"
            f"¡Sé el primero en presionar el botón para agregarla a tu mazo!"
        )

        # Si la carta tiene imagen se envía como foto, si no como mensaje de texto
        if card.image_url:
            await context.bot.send_photo(
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                photo=card.image_url,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                text=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )


async def handle_claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Procesa cuando un usuario presiona el botón '¡Reclamar Carta!'.
    """
    query = update.callback_query
    if not query or not query.data:
        return

    # Extraer el drop_id del callback_data (ej. "claim_drop:12")
    data_parts = query.data.split(":")
    if len(data_parts) != 2 or data_parts[0] != "claim_drop":
        return

    drop_id = int(data_parts[1])
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    with Session(engine) as session:
        success, message = claim_card_drop(
            session=session,
            drop_id=drop_id,
            user_id=user_id,
            username=username
        )

        if success:
            # Confirmación emergente al usuario
            await query.answer(text="¡Carta reclamada con éxito!", show_alert=False)

            # Modificar el mensaje original desactivando el botón
            claimed_caption = (
                f"{query.message.caption or query.message.text}

"
                f"✅ **{message}**"
            )

            if query.message.photo:
                await query.edit_message_caption(
                    caption=claimed_caption,
                    parse_mode="Markdown",
                    reply_markup=None  # Quita los botones
                )
            else:
                await query.edit_message_text(
                    text=claimed_caption,
                    parse_mode="Markdown",
                    reply_markup=None
                )
        else:
            # Si alguien más la reclamó antes o ya expiró
            await query.answer(text=message, show_alert=True)


def register_drop_handlers(application) -> None:
    """Registra los handlers en la aplicación de python-telegram-bot."""
    application.add_handler(CommandHandler("drop", cmd_spawn_drop))
    application.add_handler(CallbackQueryHandler(handle_claim_callback, pattern=r"^claim_drop:"))
