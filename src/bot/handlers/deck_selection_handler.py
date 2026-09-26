# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes


logger = logging.getLogger(__name__)


# Inventario temporal. En producción debe sustituirse por una consulta a DB.
MOCK_INVENTORY: Dict[str, List[Dict[str, str]]] = {
    "waifu": [
        {"id": "w1", "name": "Nicole Demara", "stat": "ATK 120 / DEF 80"},
        {"id": "w2", "name": "Cari (Pibara)", "stat": "ATK 100 / DEF 110"},
        {"id": "w3", "name": "Cami (Pibara)", "stat": "ATK 115 / DEF 95"},
    ],
    "equip": [
        {"id": "e1", "name": "Maletín Armado", "stat": "+20 ATK"},
        {"id": "e2", "name": "Bandeja de Mesera Reforzada", "stat": "+25 DEF"},
        {"id": "e3", "name": "Capuchón Capibara", "stat": "+15 ATK / +10 DEF"},
    ],
    "magic": [
        {"id": "m1", "name": "Propina Generosa", "stat": "Cura 30 HP"},
        {"id": "m2", "name": "Distracción de Té", "stat": "Anula 1 ataque"},
        {"id": "m3", "name": "Descuento de Empleado", "stat": "+30% Daño Crítico"},
    ],
}


DeckState = Dict[str, Optional[Dict[str, str]]]
SLOT_NAMES = {"waifu": "Waifu", "equip": "Equipo", "magic": "Magia"}
VALID_SLOTS = frozenset(SLOT_NAMES)


def _get_deck_state(context: ContextTypes.DEFAULT_TYPE) -> DeckState:
    """Obtiene o inicializa la selección de mazo del usuario."""
    deck = context.user_data.get("deck_building")

    if not isinstance(deck, dict):
        deck = {"waifu": None, "equip": None, "magic": None}
        context.user_data["deck_building"] = deck

    for slot in VALID_SLOTS:
        if slot not in deck:
            deck[slot] = None

    return deck


def _build_deck_status_text(deck: DeckState, active_slot: str) -> str:
    """Genera el estado actual del mazo."""
    waifu_str = (
        f"✅ {deck['waifu']['name']}" if deck["waifu"] else "❌ _Sin seleccionar_"
    )
    equip_str = (
        f"✅ {deck['equip']['name']}" if deck["equip"] else "❌ _Sin seleccionar_"
    )
    magic_str = (
        f"✅ {deck['magic']['name']}" if deck["magic"] else "❌ _Sin seleccionar_"
    )

    return (
        "🃏 **Selección de Mazo para Duelo**\n\n"
        f"👤 **1. Waifu:** {waifu_str}\n"
        f"⚔️ **2. Equipo:** {equip_str}\n"
        f"✨ **3. Magia:** {magic_str}\n\n"
        f"👉 _Seleccionando categoría:_ **{SLOT_NAMES.get(active_slot, 'Menú')}**"
    )


def _build_keyboard(deck: DeckState, active_slot: str) -> InlineKeyboardMarkup:
    """Construye el teclado para el slot activo."""
    buttons: List[List[InlineKeyboardButton]] = []

    buttons.append(
        [
            InlineKeyboardButton("👤 Waifu", callback_data="deck_slot:waifu"),
            InlineKeyboardButton("⚔️ Equipo", callback_data="deck_slot:equip"),
            InlineKeyboardButton("✨ Magia", callback_data="deck_slot:magic"),
        ]
    )

    available_cards = MOCK_INVENTORY.get(active_slot, [])
    selected_card_id = (
        deck[active_slot]["id"] if deck.get(active_slot) else None
    )

    for card in available_cards:
        prefix = "🔘 " if card["id"] == selected_card_id else "⚪️ "
        label = f"{prefix}{card['name']} ({card['stat']})"
        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"deck_pick:{active_slot}:{card['id']}",
                )
            ]
        )

    action_row: List[InlineKeyboardButton] = []
    if all(deck.get(slot) for slot in VALID_SLOTS):
        action_row.append(
            InlineKeyboardButton(
                "✅ ¡Confirmar Mazo!",
                callback_data="deck_confirm",
            )
        )

    action_row.append(
        InlineKeyboardButton("❌ Cancelar", callback_data="deck_cancel")
    )
    buttons.append(action_row)

    return InlineKeyboardMarkup(buttons)


async def start_deck_selection_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[Message]:
    """Inicia el proceso interactivo de selección de mazo."""
    if update.message is None or update.effective_chat is None:
        return None

    context.user_data["deck_building"] = {
        "waifu": None,
        "equip": None,
        "magic": None,
    }

    deck = _get_deck_state(context)
    active_slot = "waifu"

    return await update.message.reply_text(
        _build_deck_status_text(deck, active_slot),
        reply_markup=_build_keyboard(deck, active_slot),
        parse_mode="Markdown",
    )


async def deck_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Procesa los callbacks del selector de mazo."""
    query = update.callback_query
    if query is None or not query.data:
        return

    await query.answer()
    data = query.data
    deck = _get_deck_state(context)

    if data.startswith("deck_slot:"):
        active_slot = data.removeprefix("deck_slot:")

        if active_slot not in VALID_SLOTS:
            await query.answer("⚠️ Categoría inválida.", show_alert=True)
            return

        await query.edit_message_text(
            _build_deck_status_text(deck, active_slot),
            reply_markup=_build_keyboard(deck, active_slot),
            parse_mode="Markdown",
        )
        return

    if data.startswith("deck_pick:"):
        parts = data.split(":", 2)
        if len(parts) != 3:
            await query.answer("⚠️ Selección inválida.", show_alert=True)
            return

        _, slot, card_id = parts
        if slot not in VALID_SLOTS:
            await query.answer("⚠️ Categoría inválida.", show_alert=True)
            return

        selected = next(
            (
                card
                for card in MOCK_INVENTORY.get(slot, [])
                if card["id"] == card_id
            ),
            None,
        )

        if selected is None:
            await query.answer("⚠️ Carta no disponible.", show_alert=True)
            return

        deck[slot] = selected
        await query.edit_message_text(
            _build_deck_status_text(deck, slot),
            reply_markup=_build_keyboard(deck, slot),
            parse_mode="Markdown",
        )
        return

    if data == "deck_confirm":
        if not all(deck.get(slot) for slot in VALID_SLOTS):
            await query.answer(
                "⚠️ Debes seleccionar una carta para cada categoría.",
                show_alert=True,
            )
            return

        summary = (
            "⚔️ **¡Mazo Confirmado!** ⚔️\n\n"
            f"👤 **Waifu:** {deck['waifu']['name']}\n"
            f"⚔️ **Equipo:** {deck['equip']['name']}\n"
            f"✨ **Magia:** {deck['magic']['name']}\n\n"
            "¡Listo para entrar al combate!"
        )
        await query.edit_message_text(summary, parse_mode="Markdown")
        return

    if data == "deck_cancel":
        context.user_data.pop("deck_building", None)
        await query.edit_message_text("❌ Selección de mazo cancelada.")
        return

    await query.answer("⚠️ Acción no reconocida.", show_alert=True)
