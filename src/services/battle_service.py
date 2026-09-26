# -*- coding: utf-8 -*-

import logging
import math
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import ActiveMatch, CardInstance
from src.services.match_service import finish_match, get_or_create_rental_deck

logger = logging.getLogger(__name__)

DEFAULT_INITIAL_HP = 1000
MINIMUM_DAMAGE_FLOOR = 50


def safe_stat_calculation(
    base_value: int,
    percentage_modifier: float,
    flat_modifier: int,
) -> int:
    """Aplica modificadores de estadísticas con límites seguros."""
    if not isinstance(base_value, int) or isinstance(base_value, bool):
        raise TypeError("base_value debe ser un entero.")
    if not isinstance(flat_modifier, int) or isinstance(flat_modifier, bool):
        raise TypeError("flat_modifier debe ser un entero.")
    if not isinstance(percentage_modifier, (int, float)) or isinstance(
        percentage_modifier, bool
    ):
        raise TypeError("percentage_modifier debe ser numérico.")

    if not math.isfinite(float(percentage_modifier)):
        raise ValueError("percentage_modifier debe ser finito.")

    try:
        total = (base_value + flat_modifier) * (
            1.0 + float(percentage_modifier)
        )
        return max(0, math.floor(total))
    except OverflowError as exc:
        raise ValueError("El cálculo de estadísticas excede el rango permitido.") from exc


def _get_attr(obj: Any, attr: str, default: Any = 0) -> Any:
    """Obtiene un atributo desde dict, CardInstance o su definición Card."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        if attr in obj:
            return obj.get(attr, default)
        card = obj.get("card")
        if isinstance(card, dict):
            return card.get(attr, default)
        return default

    value = getattr(obj, attr, None)
    if value is not None:
        return value

    card = getattr(obj, "card", None)
    if card is not None:
        value = getattr(card, attr, None)
        if value is not None:
            return value

    return default


def _get_effect_code(obj: Any) -> Optional[str]:
    effect = _get_attr(obj, "effect_code", None)
    return str(effect).upper() if effect is not None else None


def calculate_combat_stats(
    waifu: Any,
    equip: Any = None,
    magic: Any = None,
    equip_atk_mod: Optional[int] = None,
    equip_def_mod: Optional[int] = None,
    magic_effect_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calcula estadísticas finales.

    La firma acepta tanto el formato nuevo (objetos/dicts de cartas) como
    el formato numérico histórico de cinco argumentos.
    """
    if (
        isinstance(waifu, int)
        and isinstance(equip, int)
        and isinstance(magic, int)
        and equip_atk_mod is not None
        and equip_def_mod is not None
        and magic_effect_code is not None
    ):
        base_atk = waifu
        base_def = equip
        equip_atk = magic
        equip_def = equip_atk_mod
        effect = str(magic_effect_code).upper()
    else:
        base_atk = _get_attr(waifu, "base_atk", _get_attr(waifu, "attack", 1000))
        base_def = _get_attr(waifu, "base_def", _get_attr(waifu, "defense", 800))
        equip_atk = _get_attr(
            equip, "flat_atk_bonus", _get_attr(equip, "attack", 0)
        )
        equip_def = _get_attr(
            equip, "flat_def_bonus", _get_attr(equip, "defense", 0)
        )
        effect = magic_effect_code or _get_effect_code(magic)

    total_atk = safe_stat_calculation(int(base_atk), 0.0, int(equip_atk))
    total_def = safe_stat_calculation(int(base_def), 0.0, int(equip_def))

    double_attack = False
    heal_amount = 0

    if effect == "BERSERK_FORCE":
        total_atk = safe_stat_calculation(total_atk, 0.30, 0)
        total_def = safe_stat_calculation(total_def, -0.30, 0)
    elif effect == "SHIELD_WALL":
        total_def = safe_stat_calculation(total_def, 0.50, 0)
        total_atk = safe_stat_calculation(total_atk, -0.20, 0)
    elif effect == "DOUBLE_ATTACK":
        total_def = safe_stat_calculation(total_def, -0.20, 0)
        double_attack = True
    elif effect == "BASIC_HEAL":
        heal_amount = 250

    return {
        "atk": total_atk,
        "def": total_def,
        "double_attack": double_attack,
        "heal_amount": heal_amount,
        "magic_effect": effect,
    }


def set_player_deck_and_lock(
    session: Session,
    match_id: str,
    player_id: int,
    deck: Dict[str, Dict[str, Any]],
) -> bool:
    """
    Persiste un mazo real de CardInstance en ActiveMatch y bloquea sus cartas
    de forma atómica desde el punto de vista de la transacción SQLAlchemy.

    La función usa owner_id, porque es el campo de propiedad real del modelo
    actual. Las columnas *_instance_id de ActiveMatch almacenan las referencias.
    """
    required_slots = ("waifu", "equip", "magic")
    if not isinstance(deck, dict) or not all(
        isinstance(deck.get(slot), dict) and deck[slot].get("id") is not None
        for slot in required_slots
    ):
        return False

    card_ids = [str(deck[slot]["id"]) for slot in required_slots]
    if len(set(card_ids)) != len(card_ids):
        return False

    match_stmt = (
        select(ActiveMatch)
        .where(ActiveMatch.id == match_id)
        .with_for_update()
    )
    match = session.scalars(match_stmt).first()

    if not match or match.status != "IN_PROGRESS":
        return False

    if player_id == match.player1_id:
        slot_fields = (
            "p1_waifu_instance_id",
            "p1_equip_instance_id",
            "p1_magic_instance_id",
        )
    elif player_id == match.player2_id:
        slot_fields = (
            "p2_waifu_instance_id",
            "p2_equip_instance_id",
            "p2_magic_instance_id",
        )
    else:
        return False

    card_stmt = (
        select(CardInstance)
        .where(
            CardInstance.id.in_(card_ids),
            CardInstance.owner_id == player_id,
            CardInstance.is_locked.is_(False),
        )
        .with_for_update()
    )
    cards = session.scalars(card_stmt).all()

    if len(cards) != len(card_ids):
        session.rollback()
        return False

    cards_by_id = {str(card.id): card for card in cards}
    if set(cards_by_id) != set(card_ids):
        session.rollback()
        return False

    try:
        for field_name, card_id in zip(slot_fields, card_ids):
            setattr(match, field_name, card_id)

        for card in cards:
            card.is_locked = True

        session.commit()
        return True
    except Exception:
        session.rollback()
        logger.exception("No se pudo persistir y bloquear el mazo del duelo %s", match_id)
        return False


def execute_turn(
    session: Session,
    match_id: str,
    acting_player_id: int,
    action_type: str = "ATTACK",
) -> Dict[str, Any]:
    """Resuelve un turno, actualiza HP/turno y finaliza el duelo si corresponde."""
    if action_type != "ATTACK":
        return {"success": False, "error": f"Acción no soportada: {action_type}."}

    match = (
        session.query(ActiveMatch)
        .filter(ActiveMatch.id == match_id)
        .with_for_update()
        .first()
    )

    if not match:
        return {"success": False, "error": "El duelo no existe."}

    if match.status != "IN_PROGRESS":
        return {"success": False, "error": "El duelo no está en curso."}

    current_player_id = (
        match.current_turn_player_id
        if match.current_turn_player_id is not None
        else match.current_turn_id
    )

    if current_player_id != acting_player_id:
        return {"success": False, "error": "No es tu turno de actuar."}

    is_p1_acting = acting_player_id == match.player1_id
    if not is_p1_acting and acting_player_id != match.player2_id:
        return {"success": False, "error": "El jugador no participa en este duelo."}

    defender_id = match.player2_id if is_p1_acting else match.player1_id

    p1_deck = _load_player_deck(session, match, is_p1=True)
    p2_deck = _load_player_deck(session, match, is_p1=False)
    attacker_deck = p1_deck if is_p1_acting else p2_deck
    defender_deck = p2_deck if is_p1_acting else p1_deck

    if match.p1_hp is None:
        match.p1_hp = DEFAULT_INITIAL_HP
    if match.p2_hp is None:
        match.p2_hp = DEFAULT_INITIAL_HP

    attacker_hp = match.p1_hp if is_p1_acting else match.p2_hp
    defender_hp = match.p2_hp if is_p1_acting else match.p1_hp

    attacker_stats = calculate_combat_stats(
        attacker_deck["waifu"],
        attacker_deck["equipment"],
        attacker_deck["magic"],
    )
    defender_stats = calculate_combat_stats(
        defender_deck["waifu"],
        defender_deck["equipment"],
        defender_deck["magic"],
    )

    log_lines = []

    if attacker_stats["heal_amount"] > 0:
        recovered = attacker_stats["heal_amount"]
        attacker_hp = min(DEFAULT_INITIAL_HP, attacker_hp + recovered)
        log_lines.append(
            f"✨ ¡Usó **Poción/Magia** y recuperó +{recovered} HP!"
        )

    raw_damage = attacker_stats["atk"] - defender_stats["def"]
    damage_per_hit = max(MINIMUM_DAMAGE_FLOOR, raw_damage)
    hits = 2 if attacker_stats["double_attack"] else 1
    total_damage = damage_per_hit * hits

    if hits == 2:
        log_lines.append(
            f"⚔️⚡ ¡Ataque Doble! Inflige 2 golpes de {damage_per_hit} de daño."
        )
    else:
        log_lines.append(
            f"⚔️ Inflige {total_damage} de daño "
            f"(ATK: {attacker_stats['atk']} vs DEF: {defender_stats['def']})."
        )

    defender_hp = max(0, defender_hp - total_damage)

    if is_p1_acting:
        match.p1_hp = attacker_hp
        match.p2_hp = defender_hp
    else:
        match.p2_hp = attacker_hp
        match.p1_hp = defender_hp

    match_ended = False
    winner_id = None

    if defender_hp <= 0:
        match_ended = True
        winner_id = acting_player_id
        log_lines.append(
            f"💥 ¡HP del rival reducido a 0! "
            f"**Jugador {acting_player_id}** gana el duelo."
        )

        success, finish_message = finish_match(
            session,
            match_id=match.id,
            winner_id=winner_id,
        )
        if not success:
            session.rollback()
            return {"success": False, "error": finish_message}

        log_lines.append(f"🏁 {finish_message}")
    else:
        next_turn = defender_id
        match.current_turn_player_id = next_turn
        match.current_turn_id = next_turn
        session.commit()
        log_lines.append(
            f"🔄 Fin del turno. Es el turno del **Jugador {next_turn}**."
        )

    return {
        "success": True,
        "match_id": match.id,
        "acting_player_id": acting_player_id,
        "damage_dealt": total_damage,
        "attacker_hp": attacker_hp,
        "defender_hp": defender_hp,
        "is_p1_hp": match.p1_hp,
        "is_p2_hp": match.p2_hp,
        "next_turn_player_id": (
            match.current_turn_player_id if not match_ended else None
        ),
        "match_ended": match_ended,
        "winner_id": winner_id,
        "combat_log": "\n".join(log_lines),
    }


def _load_player_deck(
    session: Session,
    match: ActiveMatch,
    is_p1: bool,
) -> Dict[str, Any]:
    """Carga cartas seleccionadas y completa slots faltantes con rentals."""
    w_id = match.p1_waifu_instance_id if is_p1 else match.p2_waifu_instance_id
    e_id = match.p1_equip_instance_id if is_p1 else match.p2_equip_instance_id
    m_id = match.p1_magic_instance_id if is_p1 else match.p2_magic_instance_id

    waifu = (
        session.query(CardInstance).filter(CardInstance.id == w_id).first()
        if w_id
        else None
    )
    equip = (
        session.query(CardInstance).filter(CardInstance.id == e_id).first()
        if e_id
        else None
    )
    magic = (
        session.query(CardInstance).filter(CardInstance.id == m_id).first()
        if m_id
        else None
    )

    user_id = match.player1_id if is_p1 else match.player2_id
    existing_items = [item for item in (waifu, equip, magic) if item is not None]

    return get_or_create_rental_deck(
        session,
        user_id=user_id,
        user_inventory=existing_items,
    )
