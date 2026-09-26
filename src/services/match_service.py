# -*- coding: utf-8 -*-
import random
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.db.models import ActiveMatch, CardInstance, User

MATCH_TIMEOUT_SECONDS = 90  # 90 segundos para aceptar o expira el reto

# Perfiles de personalidad y diálogos de las Meseras Referí
REFEREE_PROFILES: Dict[str, Dict[str, str]] = {
    "Cari": {
        "start": "☕ *Cari limpia la mesa con un trapo cansada*: «Bueno, coordinemos esto rápido que mi café se enfría. Tienen 90 segundos para aceptar o me voy a la cocina.»",
        "accept": "⚔️ *Cari se apoya en la mesa y sonríe con sarcasmo*: «¡Al fin! Serví las cartas. Tienen la mesa lista, veamos quién paga la cuenta hoy.»",
        "timeout": "⏳ *Cari suspira y guarda las sillas*: «Pasó minuto y medio y nadie apareció. Me voy a la cocina a tomar un descanso. Avisen cuando de verdad vayan a pelear.»",
        "busy": "☕ *Cari desde la barra*: «Estoy ocupada atendiendo otra mesa y las chicas están en lo suyo. Esperen un momento.»"
    },
    "Cami": {
        "start": "🔥 *Cami llega corriendo casi tirando la bandeja*: «¡Llegó la hora del duelo! La mesa está servida. Tienen 90 segundos antes de que me aburra y me vaya a desafiar a otro.»",
        "accept": "⚔️ *Cami da un golpe entusiasta a la mesa*: «¡ESO ES! ¡Desafío aceptado! ¡Abran paso, limpio la zona para la batalla!»",
        "timeout": "⏰ *Cami hace sonar su silbato*: «¡Se acabó el tiempo! No me hagan perder el tiempo montando una mesa si van a quedarse mirando.»",
        "busy": "🔥 *Cami agitada*: «¡Tengo todas las mesas ardiendo en duelos ahora mismo! Denme un minuto para terminar estos pedidos.»"
    },
    "Sunna": {
        "start": "✨ *Sunna acomoda los manteles con elegancia impecable*: «Buenas noches. Supervisaré este encuentro con total neutralidad. Tienen 90 segundos para formalizar la aceptación.»",
        "accept": "⚔️ *Sunna ajusta sus guantes y se inclina cortesmente*: «Desafío aceptado. Que la mejor estrategia y compostura prevalezcan en el campo.»",
        "timeout": "⌛ *Sunna retira las cartas con total serenidad*: «El tiempo reglamentario de espera ha concluido. Retiro la propuesta por inactividad y paso a mi receso programado.»",
        "busy": "✨ *Sunna con voz pausada*: «Todas las meseras nos encontramos supervisando partidas en este instante. Les ruego un momento de paciencia.»"
    }
}


def get_available_referee(session: Session) -> Optional[str]:
    """
    Selecciona una mesera libre. Si todas están en duelos activos, retorna None.
    """
    busy_stmt = select(ActiveMatch.referee_name).where(
        ActiveMatch.status.in_(["WAITING", "IN_PROGRESS"])
    )
    busy_referees = session.scalars(busy_stmt).all()
    available = [r for r in REFEREE_PROFILES.keys() if r not in busy_referees]

    return random.choice(available) if available else None


def create_match_challenge(
    session: Session,
    group_id: int,
    player1_id: int,
    player2_id: Optional[int] = None,
    staked_card_id: Optional[str] = None,
    message_thread_id: Optional[int] = None
) -> Tuple[bool, str, Optional[ActiveMatch]]:
    """
    Crea una solicitud de duelo asignando una mesera libre y un tiempo de expiración (90s).
    """
    referee = get_available_referee(session)
    if not referee:
        # Mensaje genérico de ocupadas si ninguna está libre
        return False, "☕ *Todas las meseras están en duelos o en su descanso de cocina.* ¡Inténtalo en un par de minutos!", None

    # Verificar que el retador no tenga otro duelo activo
    active_stmt = select(ActiveMatch).where(
        or_(ActiveMatch.player1_id == player1_id, ActiveMatch.player2_id == player1_id),
        ActiveMatch.status.in_(["WAITING", "IN_PROGRESS"])
    )
    if session.scalars(active_stmt).first():
        return False, "⚠️ Ya tienes una mesa o duelo en curso. Termina tu partida antes de pedir otra.", None

    match_id = str(uuid.uuid4())
    new_match = ActiveMatch(
        id=match_id,
        group_id=group_id,
        message_thread_id=message_thread_id,
        player1_id=player1_id,
        player2_id=player2_id or 0,
        p1_hp=100,
        p2_hp=100,
        current_turn_id=player1_id,
        staked_card_instance_id=staked_card_id,
        status="WAITING",
        referee_name=referee
    )

    session.add(new_match)
    session.commit()

    intro_msg = REFEREE_PROFILES[referee]["start"]
    return True, intro_msg, new_match


def accept_match_challenge(
    session: Session,
    match_id: str,
    player2_id: int
) -> Tuple[bool, str]:
    """
    Procesa la aceptación del reto validando tiempos (90s) y permisos de participantes.
    """
    match = session.get(ActiveMatch, match_id)

    if not match or match.status != "WAITING":
        return False, "Esta mesa ya no está disponible o el duelo ya terminó."

    referee = match.referee_name
    now = datetime.utcnow()

    # Validar expiración por tiempo (90 segundos)
    if (now - match.created_at).total_seconds() > MATCH_TIMEOUT_SECONDS:
        match.status = "EXPIRED"
        session.commit()
        timeout_msg = REFEREE_PROFILES[referee]["timeout"]
        return False, timeout_msg

    if match.player1_id == player2_id:
        return False, "No puedes aceptar tu propio reto."

    if match.player2_id != 0 and match.player2_id != player2_id:
        return False, "Esta mesa fue reservada para otro jugador."

    match.player2_id = player2_id
    match.status = "IN_PROGRESS"
    session.commit()

    accept_msg = REFEREE_PROFILES[referee]["accept"]
    return True, accept_msg
