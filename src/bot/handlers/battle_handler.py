# -*- coding: utf-8 -*-

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from src.db.models import ActiveMatch
from src.services.battle_service import execute_turn
from src.services.match_service import finish_match

logger = logging.getLogger(__name__)

engine = create_engine("sqlite:///bot_database.db", echo=False)


def _render_hp_bar(
    current_hp: int,
    max_hp: int = 1000,
    length: int = 10,
) -> str:
    """Genera una barra visual de HP segura para Markdown."""
    current_hp = max(0, min(current_hp, max_hp))
    filled = int(round((current_hp / max_hp) * length))
    bar = "█" * filled + "░" * (length - filled)
    return f"HP [{bar}] {current_hp}/{max_hp}"


def _build_battle_keyboard(match_id: str) -> InlineKeyboardMarkup:
    """Construye los botones de acción del combate."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚔️ Atacar",
                    callback_data=f"battle_act:{match_id}:ATTACK",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏳️ Rendirse",
                    callback_data=f"battle_surrender:{match_id}",
                )
            ],
        ]
    )


def _get_match_from_callback(session: Session, query) -> ActiveMatch | None:
    """Carga el duelo y valida que el mensaje siga perteneciendo a su grupo."""
    if not query.message or not query.message.chat:
        return None

    match_id = query.data.split(":")[1]
    match = session.get(ActiveMatch, match_id)

    if not match or match.group_id != query.message.chat.id:
        return None

    return match


async def battle_action_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Procesa una acción de combate desde un botón Inline."""
    del context

    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return

    data_parts = query.data.split(":")
    if len(data_parts) != 3 or data_parts[0] != "battle_act":
        await query.answer("Acción de combate no válida.", show_alert=True)
        return

    match_id = data_parts[1]
    action_type = data_parts[2].upper()
    acting_player_id = query.from_user.id

    with Session(engine) as session:
        match = _get_match_from_callback(session, query)
        if not match:
            await query.answer(
                "❌ El duelo no existe o pertenece a otro grupo.",
                show_alert=True,
            )
            return

        if acting_player_id not in (match.player1_id, match.player2_id):
            await query.answer(
                "❌ No participas en este duelo.",
                show_alert=True,
            )
            return

        result = execute_turn(
            session=session,
            match_id=match_id,
            acting_player_id=acting_player_id,
            action_type=action_type,
        )

        if not result["success"]:
            await query.answer(
                result.get("error", "No fue posible procesar la acción."),
                show_alert=True,
            )
            return

        await query.answer("⚔️ ¡Acción ejecutada!")
        session.refresh(match)

        p1_bar = _render_hp_bar(result["is_p1_hp"])
        p2_bar = _render_hp_bar(result["is_p2_hp"])
        log_text = result["combat_log"]

        if result["match_ended"]:
            winner_id = result["winner_id"]
            loser_id = (
                match.player2_id
                if winner_id == match.player1_id
                else match.player1_id
            )

            end_text = (
                "💥 **¡DUELO FINALIZADO!** 💥\n\n"
                f"🔴 **Jugador 1 ({match.player1_id}):** {p1_bar}\n"
                f"🔵 **Jugador 2 ({match.player2_id}):** {p2_bar}\n\n"
                f"📜 **Última Acción:**\n{log_text}\n\n"
                f"🏆 **¡GANADOR:** {winner_id}!\n"
                f"💀 **Derrotado:** {loser_id}\n\n"
                "✨ Las cartas apostadas han sido transferidas "
                "al inventario del vencedor."
            )

            await query.edit_message_text(
                end_text,
                reply_markup=None,
                parse_mode="Markdown",
            )
            return

        next_turn_id = result["next_turn_player_id"]
        status_text = (
            "⚔️ **DUELO EN CURSO**\n\n"
            f"🔴 **Jugador 1 ({match.player1_id}):** {p1_bar}\n"
            f"🔵 **Jugador 2 ({match.player2_id}):** {p2_bar}\n\n"
            f"📜 **Último Suceso:**\n{log_text}\n\n"
            f"👉 **Turno activo:** {next_turn_id}"
        )

        await query.edit_message_text(
            status_text,
            reply_markup=_build_battle_keyboard(match_id),
            parse_mode="Markdown",
        )


async def battle_surrender_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Procesa la rendición voluntaria de un participante."""
    del context

    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return

    data_parts = query.data.split(":")
    if len(data_parts) != 2 or data_parts[0] != "battle_surrender":
        await query.answer(
            "Solicitud de rendición no válida.",
            show_alert=True,
        )
        return

    surrendering_player_id = query.from_user.id
    match_id = data_parts[1]

    with Session(engine) as session:
        match = _get_match_from_callback(session, query)

        if not match:
            await query.answer(
                "❌ El duelo no existe o pertenece a otro grupo.",
                show_alert=True,
            )
            return

        if match.status != "IN_PROGRESS":
            await query.answer(
                "El duelo no está en curso.",
                show_alert=True,
            )
            return

        if surrendering_player_id not in (match.player1_id, match.player2_id):
            await query.answer(
                "❌ No eres participante de este duelo.",
                show_alert=True,
            )
            return

        winner_id = (
            match.player2_id
            if surrendering_player_id == match.player1_id
            else match.player1_id
        )

        success, finish_message = finish_match(
            session=session,
            match_id=match_id,
            winner_id=winner_id,
        )

        if not success:
            await query.answer(f"❌ {finish_message}", show_alert=True)
            return

        await query.answer("🏳️ Has abandonado el combate.")

        surrender_text = (
            "🏳️ **¡DUELO CONCLUIDO POR RENDICIÓN!**\n\n"
            f"El jugador {surrendering_player_id} ha izado la bandera blanca.\n\n"
            f"🏆 **Ganador por abandono:** {winner_id}\n"
            "💰 Las cartas apostadas fueron resueltas por el "
            "motor de finalización del duelo."
        )

        await query.edit_message_text(
            surrender_text,
            reply_markup=None,
            parse_mode="Markdown",
        )


def register_battle_handlers(app: Application) -> None:
    """Registra callbacks de ataque y rendición."""
    app.add_handler(
        CallbackQueryHandler(
            battle_action_callback,
            pattern=r"^battle_act:",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            battle_surrender_callback,
            pattern=r"^battle_surrender:",
        )
    )
