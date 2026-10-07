# -*- coding: utf-8 -*-

import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import ActiveMatch, CardInstance, User

MATCH_TIMEOUT_SECONDS = 90
BREAK_DURATION_SECONDS = 120

REFEREE_BREAKS: Dict[str, datetime] = {}

REFEREE_PROFILES: Dict[str, Dict[str, str]] = {
    "Cari": {
        "start": "☕ *Cari limpia la mesa con un trapo cansada*: «Bueno, coordinemos esto rápido que mi café se enfría. Tienen 90 segundos para aceptar o me voy a la cocina.»",
        "accept": "⚔️ *Cari se apoya en la mesa y sonríe con sarcasmo*: «¡Al fin! Serví las cartas. Tienen la mesa lista, veamos quién paga la cuenta hoy.»",
        "timeout": "⏳ *Cari suspira y guarda las sillas*: «Pasó minuto y medio y nadie apareció. Devuelvo la carta apostada. Me voy a la cocina a tomar un descanso. Avisen cuando de verdad vayan a pelear.»",
        "busy": "☕ *Cari desde la barra*: «Estoy ocupada o en mi receso de café. Esperen a que se libere una mesa.»"
    },
    "Cami": {
        "start": "🔥 *Cami llega corriendo casi tirando la bandeja*: «¡Llegó la hora del duelo! La mesa está servida. Tienen 90 segundos antes de que me aburra y me vaya a desafiar a otro.»",
        "accept": "⚔️ *Cami da un golpe entusiasta a la mesa*: «¡ESO ES! ¡Desafío aceptado! ¡Abran paso, limpio la zona para la batalla!»",
        "timeout": "⏰ *Cami hace sonar su silbato*: «¡Se acabó el tiempo! Su carta apostada regresa a su mazo. No me hagan perder el tiempo montando una mesa si van a quedarse mirando.»",
        "busy": "🔥 *Cami agitada*: «¡Todas las mesas están ardiendo en duelos o estoy tomando agua! Denme un par de minutos.»"
    },
    "Sunna": {
        "start": "✨ *Sunna acomoda los manteles con elegancia impecable*: «Buenas noches. Supervisaré este encuentro con total neutralidad. Tienen 90 segundos para formalizar la aceptación.»",
        "accept": "⚔️ *Sunna ajusta sus guantes y se inclina cortésmente*: «Desafío aceptado. Que la mejor estrategia y compostura prevalezcan en el campo.»",
        "timeout": "⌛ *Sunna retira las cartas con total serenidad*: «El tiempo reglamentario de espera ha concluido. La carta en garantía se desvincula del duelo y paso a mi receso programado.»",
        "busy": "✨ *Sunna con voz pausada*: «Nos encontramos supervisando partidas o en pausa reglamentaria. Les ruego un momento de paciencia.»"
    }
}


def _begin_immediate(session: Session) -> None:
    """Adquiere la write transaction SQLite antes de leer estado autoritativo."""
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")


def is_referee_on_break(referee_name: str) -> bool:
    break_until = REFEREE_BREAKS.get(referee_name)
    if break_until and datetime.utcnow() < break_until:
        return True
    return False


def set_referee_on_break(referee_name: str):
    REFEREE_BREAKS[referee_name] = datetime.utcnow() + timedelta(seconds=BREAK_DURATION_SECONDS)


def get_available_referee(session: Session) -> Optional[str]:
    busy_stmt = select(ActiveMatch.referee_name).where(
        ActiveMatch.status.in_(["WAITING", "IN_PROGRESS"])
    )
    busy_referees = session.scalars(busy_stmt).all()

    available = [
        r
        for r in REFEREE_PROFILES.keys()
        if r not in busy_referees and not is_referee_on_break(r)
    ]
    return random.choice(available) if available else None


def release_staked_cards(session: Session, match: ActiveMatch) -> None:
    """
    Desbloquea las cartas apostadas o seleccionadas si el duelo no se completa.

    La liberación se concentra aquí para que cancelaciones y expiraciones
    utilicen exactamente la misma ruta de limpieza.
    """
    card_ids = [
        match.p1_staked_card_id,
        match.p2_staked_card_id,
        match.p1_waifu_instance_id,
        match.p1_equip_instance_id,
        match.p1_magic_instance_id,
        match.p2_waifu_instance_id,
        match.p2_equip_instance_id,
        match.p2_magic_instance_id,
        match.staked_card_instance_id,
    ]

    valid_ids = list({str(card_id) for card_id in card_ids if card_id is not None})

    if valid_ids:
        session.query(CardInstance).filter(
            CardInstance.id.in_(valid_ids)
        ).update(
            {"is_locked": False},
            synchronize_session=False,
        )


def _get_card_definition(item: Any) -> Any:
    if isinstance(item, dict):
        return item
    template = getattr(item, "card_template", None)
    if template is not None:
        return template
    return getattr(item, "card", item)


def _get_card_type(item: Any) -> Optional[str]:
    definition = _get_card_definition(item)
    if isinstance(definition, dict):
        value = definition.get("card_type", definition.get("type"))
    else:
        value = getattr(definition, "card_type", getattr(definition, "type", None))
    return str(value).upper() if value is not None else None


def create_rental_card_instance(
    name: str,
    card_type: str,
    atk: int = 0,
    def_val: int = 0,
    effect_code: Optional[str] = None
) -> dict:
    return {
        "id": None,
        "name": name,
        "card_type": str(card_type).upper(),
        "rarity": "R",
        "is_rental": True,
        "base_atk": max(0, int(atk)),
        "base_def": max(0, int(def_val)),
        "effect_code": effect_code,
    }


def get_or_create_rental_deck(
    session: Session,
    user_id: int,
    user_inventory: list
) -> dict:
    del session
    del user_id

    deck = {"waifu": None, "equipment": None, "magic": None}
    slot_by_type = {"WAIFU": "waifu", "EQUIPMENT": "equipment", "MAGIC": "magic"}

    for item in user_inventory or []:
        slot = slot_by_type.get(_get_card_type(item))
        if slot is not None and deck[slot] is None:
            deck[slot] = item

    if deck["waifu"] is None:
        deck["waifu"] = create_rental_card_instance(
            "Waifu Principiante", "WAIFU", atk=1000, def_val=1000
        )
    if deck["equipment"] is None:
        deck["equipment"] = create_rental_card_instance(
            "Escudo de Madera", "EQUIPMENT", atk=100, def_val=200
        )
    if deck["magic"] is None:
        deck["magic"] = create_rental_card_instance(
            "Poción de Taberna", "MAGIC", effect_code="BASIC_HEAL"
        )

    return deck


def create_match_challenge(
    session: Session,
    group_id: int,
    player1_id: int,
    player2_id: Optional[int] = None,
    staked_card_id: Optional[str] = None,
    message_thread_id: Optional[int] = None
) -> Tuple[bool, str, Optional[ActiveMatch]]:
    try:
        _begin_immediate(session)
        participant_ids = {player1_id}
        if player2_id not in (None, 0, player1_id):
            participant_ids.add(player2_id)
        active_stmt = select(ActiveMatch.id).where(
            ActiveMatch.status.in_(["WAITING", "IN_PROGRESS"]),
            or_(
                ActiveMatch.player1_id.in_(participant_ids),
                ActiveMatch.player2_id.in_(participant_ids),
            ),
        )
        if session.scalars(active_stmt).first():
            session.rollback()
            return False, "⚠️ Ya tienes una mesa o duelo en curso. Termina tu partida antes de pedir otra.", None
        referee = get_available_referee(session)
        if not referee:
            session.rollback()
            return False, "☕ *Todas las meseras están en duelos o en su descanso de cocina.* ¡Inténtalo en un par de minutos!", None
        if staked_card_id:
            card_inst = session.get(CardInstance, staked_card_id)
            if not card_inst or card_inst.owner_id != player1_id:
                session.rollback()
                return False, "⚠️ No posees la carta que intentas apostar en el duelo.", None
        new_match = ActiveMatch(
            id=str(uuid.uuid4()),
            group_id=group_id,
            message_thread_id=message_thread_id,
            player1_id=player1_id,
            player2_id=player2_id or 0,
            p1_hp=100,
            p2_hp=100,
            current_turn_id=player1_id,
            staked_card_instance_id=staked_card_id,
            status="WAITING",
            referee_name=referee,
        )
        session.add(new_match)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return False, "⚠️ La mesa no pudo reservarse porque otro proceso ocupó ese recurso.", None
        return True, REFEREE_PROFILES[referee]["start"], new_match
    except Exception:
        session.rollback()
        raise


def accept_match_challenge(
    session: Session,
    match_id: str,
    player2_id: int
) -> Tuple[bool, str]:
    try:
        _begin_immediate(session)
        match = session.scalars(select(ActiveMatch).where(ActiveMatch.id == match_id).execution_options(populate_existing=True)).first()
        if not match or match.status != "WAITING":
            session.rollback()
            return False, "Esta mesa ya no está disponible o el duelo ya terminó."
        referee = match.referee_name
        if (datetime.utcnow() - match.created_at).total_seconds() > MATCH_TIMEOUT_SECONDS:
            release_staked_cards(session, match)
            expired = session.execute(
                update(ActiveMatch)
                .where(ActiveMatch.id == match_id, ActiveMatch.status == "WAITING", ActiveMatch.player2_id == 0)
                .values(status="EXPIRED", staked_card_instance_id=None)
            )
            if expired.rowcount != 1:
                session.rollback()
                return False, "Esta mesa ya no está disponible o el duelo ya terminó."
            session.commit()
            set_referee_on_break(referee)
            return False, REFEREE_PROFILES[referee]["timeout"]
        if match.player1_id == player2_id:
            session.rollback()
            return False, "No puedes aceptar tu propio reto."
        if match.player2_id != 0 and match.player2_id != player2_id:
            session.rollback()
            return False, "Esta mesa fue reservada para otro jugador."
        accepted = session.execute(
            update(ActiveMatch)
            .where(
                ActiveMatch.id == match_id,
                ActiveMatch.status == "WAITING",
                ActiveMatch.player2_id == 0,
                ActiveMatch.player1_id != player2_id,
            )
            .values(player2_id=player2_id, status="IN_PROGRESS")
        )
        if accepted.rowcount != 1:
            session.rollback()
            return False, "Esta mesa ya no está disponible o el duelo ya terminó."
        session.commit()
        return True, REFEREE_PROFILES[referee]["accept"]
    except Exception:
        session.rollback()
        raise


def validate_and_lock_staked_card(
    session: Session,
    match_id: str,
    user_id: int,
    card_instance_id: str
) -> Tuple[bool, str]:
    if user_id is None:
        return False, "Usuario no válido."
    try:
        _begin_immediate(session)
        match = session.scalars(select(ActiveMatch).where(ActiveMatch.id == match_id).execution_options(populate_existing=True)).first()
        if not match or match.status not in {"WAITING_FOR_STAKES", "IN_PROGRESS"}:
            session.rollback()
            return False, "El duelo no está en fase de apuestas o ya no existe."
        if user_id not in {match.player1_id, match.player2_id}:
            session.rollback()
            return False, "⚠️ **Operación Denegada:** no participas en este duelo."
        card = session.scalars(select(CardInstance).where(CardInstance.id == str(card_instance_id)).execution_options(populate_existing=True)).first()
        if not card:
            session.rollback()
            return False, "La carta seleccionada no existe."
        if getattr(card, "is_rental", False):
            session.rollback()
            return False, "⚠️ **Operación Denegada:** Las cartas prestadas por la mesera no se pueden apostar."
        if card.is_locked:
            session.rollback()
            return False, "⚠️ Esta carta ya está en uso en otro duelo o mercado."
        if card.owner_id != user_id:
            session.rollback()
            return False, "⚠️ **Violación de Seguridad:** Intentaste apostar una carta que no te pertenece."
        if match.p1_staked_card_id == card.id or match.p2_staked_card_id == card.id:
            session.rollback()
            return False, "⚠️ Esta misma carta ya fue seleccionada como apuesta en este duelo."
        card_definition = getattr(card, "card_template", None) or card.card
        if card_definition is None:
            session.rollback()
            return False, "⚠️ La instancia no tiene una carta base válida."
        rarity = card_definition.rarity
        if match.staked_rarity is None:
            match.staked_rarity = rarity
        elif rarity != match.staked_rarity:
            session.rollback()
            return False, f"⚠️ **Apuesta Inválida:** Tu oponente apostó una carta **{match.staked_rarity}**. Debes apostar una carta de la misma rareza."
        lock_result = session.execute(
            update(CardInstance)
            .where(CardInstance.id == str(card_instance_id), CardInstance.owner_id == user_id, CardInstance.is_locked.is_(False))
            .values(is_locked=True)
        )
        if lock_result.rowcount != 1:
            session.rollback()
            return False, "⚠️ Esta carta ya está en uso en otro duelo o mercado."
        if user_id == match.player1_id:
            match.p1_staked_card_id = card.id
        else:
            match.p2_staked_card_id = card.id
        session.commit()
        card_name = getattr(card_definition, "name", "Carta")
        return True, f"✅ Carta **{card_name}** ({rarity}) fijada y bloqueada correctamente para el duelo."
    except Exception:
        session.rollback()
        raise


def validate_and_set_stakes(
    session: Session,
    match_id: str,
    p1_card_instance_id: str,
    p2_card_instance_id: str
) -> Tuple[bool, str]:
    match = session.get(ActiveMatch, match_id)
    if not match or match.status not in {"WAITING_FOR_STAKES", "IN_PROGRESS"}:
        return False, "No hay un duelo activo para establecer las apuestas."

    ok, message = validate_and_lock_staked_card(
        session, match_id, match.player1_id, p1_card_instance_id
    )
    if not ok:
        return False, message

    ok, message = validate_and_lock_staked_card(
        session, match_id, match.player2_id, p2_card_instance_id
    )
    if not ok:
        return False, message

    return True, (
        f"✅ Apuestas validadas y bloqueadas correctamente: "
        f"ambos apostaron una carta **{match.staked_rarity}**."
    )


def _finish_match_in_transaction(
    session: Session,
    match: ActiveMatch,
    winner_id: int,
) -> Tuple[bool, str, str]:
    if match.status != "IN_PROGRESS":
        return False, "No se encontró un duelo en curso con esa identificación.", match.referee_name
    if winner_id not in {match.player1_id, match.player2_id}:
        return False, "El ganador indicado no participa en el duelo.", match.referee_name
    transition = session.execute(
        update(ActiveMatch)
        .where(ActiveMatch.id == match.id, ActiveMatch.status == "IN_PROGRESS")
        .values(status="FINISHED")
    )
    if transition.rowcount != 1:
        return False, "No se encontró un duelo en curso con esa identificación.", match.referee_name
    match.status = "FINISHED"
    referee = match.referee_name
    release_staked_cards(session, match)
    if match.staked_card_instance_id:
        card_inst = session.get(CardInstance, match.staked_card_instance_id)
        if card_inst:
            card_inst.owner_id = winner_id
            card_inst.is_locked = False
    if match.p1_staked_card_id and match.p2_staked_card_id:
        p1_card = session.get(CardInstance, str(match.p1_staked_card_id))
        p2_card = session.get(CardInstance, str(match.p2_staked_card_id))
        loser_card = p2_card if winner_id == match.player1_id else p1_card
        if loser_card:
            loser_card.owner_id = winner_id
            loser_card.is_locked = False
        for card_inst in (p1_card, p2_card):
            if card_inst:
                card_inst.is_locked = False
    match.staked_card_instance_id = None
    match.p1_staked_card_id = None
    match.p2_staked_card_id = None
    match.staked_rarity = None
    return True, f"🏁 Duelo concluido. {referee} se retira a la cocina por su receso reglamentario.", referee


def finish_match(
    session: Session,
    match_id: str,
    winner_id: int
) -> Tuple[bool, str]:
    try:
        _begin_immediate(session)
        match = session.scalars(select(ActiveMatch).where(ActiveMatch.id == match_id).execution_options(populate_existing=True)).first()
        if not match:
            session.rollback()
            return False, "No se encontró un duelo en curso con esa identificación."
        success, message, referee = _finish_match_in_transaction(session, match, winner_id)
        if not success:
            session.rollback()
            return False, message
        session.commit()
        set_referee_on_break(referee)
        return True, message
    except Exception:
        session.rollback()
        raise


def forfeit_match(
    session: Session,
    match_id: str,
    forfeiter_id: int,
    reason: str = "abandono"
) -> Tuple[bool, str]:
    match = session.get(ActiveMatch, match_id)

    if not match or match.status != "IN_PROGRESS":
        return False, "No hay un duelo activo para abandonar."

    if forfeiter_id == match.player1_id:
        winner_id = match.player2_id
    elif forfeiter_id == match.player2_id:
        winner_id = match.player1_id
    else:
        return False, "El usuario indicado no pertenece a este duelo."

    success, msg = finish_match(session, match_id, winner_id=winner_id)

    if not success:
        return False, msg

    referee = match.referee_name
    dialogue = (
        f"⏳ **¡Tiempo agotado / Abandono!**\n\n"
        f"🍺 *{referee} declara el final del combate*: "
        f"«Un participante se ha retirado de la mesa. Victoria por {reason} para el rival.»"
    )

    return True, dialogue
