# -*- coding: utf-8 -*-
import uuid
import random
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from src.db.models import ActiveMatch, CardInstance, User

# Lista de meseras referí
REFEREES = ["Cami", "Cari", "Sunna"]
MATCH_TIMEOUT_SECONDS = 90  # 90 segundos para aceptar o jugar un turno


def get_available_referee(session: Session) -> Optional[str]:
    """
    Selecciona una mesera libre. Si todas están en duelos activos o descanso, retorna None.
    """
    # Meseras ocupadas en duelos en curso
    busy_stmt = select(ActiveMatch.referee_name).where(
        ActiveMatch.status.in_(["WAITING", "IN_PROGRESS"])
    )
    busy_referees = session.scalars(busy_stmt).all()

    available = [r for r in REFEREES if r not in busy_referees]
    
    if not available:
        return None
    
    # Seleccionar una mesera libre al azar
    return random.choice(available)


def create_match_challenge(
    session: Session,
    group_id: int,
    player1_id: int,
    player2_id: Optional[int] = None,
    staked_card_id: Optional[str] = None,
    message_thread_id: Optional[int] = None
) -> Tuple[bool, str, Optional[ActiveMatch]]:
    """
    Crea una solicitud de duelo asignando una mesera libre y un tiempo de expiración.
    """
    # 1. Verificar disponibilidad de Mesera
    referee = get_available_referee(session)
    if not referee:
        return False, "☕ Todas las meseras están ocupadas o en su descanso. ¡Inténtalo en un momento!", None

    # 2. Verificar que el retador no tenga otro duelo activo
    active_stmt = select(ActiveMatch).where(
        or_(ActiveMatch.player1_id == player1_id, ActiveMatch.player2_id == player1_id),
        ActiveMatch.status.in_(["WAITING", "IN_PROGRESS"])
    )
    if session.scalars(active_stmt).first():
        return False, "⚠️ Ya tienes un duelo en curso. Termina tu partida antes de retar de nuevo.", None

    # 3. Registrar el duelo con tiempo límite (TTL)
    match_id = str(uuid.uuid4())
    new_match = ActiveMatch(
        id=match_id,
        group_id=group_id,
        message_thread_id=message_thread_id,
        player1_id=player1_id,
        player2_id=player2_id or 0,  # 0 indica reto abierto para el grupo
        p1_hp=100,
        p2_hp=100,
        current_turn_id=player1_id,
        staked_card_instance_id=staked_card_id,
        status="WAITING",
        referee_name=referee
    )

    session.add(new_match)
    session.commit()

    return True, f"✨ La mesera **{referee}** ha tomado la mesa para coordinar el duelo.", new_match


def accept_match_challenge(
    session: Session,
    match_id: str,
    player2_id: int
) -> Tuple[bool, str]:
    """
    Procesa la aceptación del reto validando tiempos y permisos.
    """
    match = session.get(ActiveMatch, match_id)

    if not match or match.status != "WAITING":
        return False, "El duelo ya no está disponible o ya finalizó."

    # Validar expiración por tiempo (90 segundos)
    now = datetime.utcnow()
    if (now - match.created_at).total_seconds() > MATCH_TIMEOUT_SECONDS:
        match.status = "EXPIRED"
        session.commit()
        return False, f"⏰ El reto ha expirado. La mesera **{match.referee_name}** tuvo que atender otras mesas."

    # Validar que el creador no acepte su propio reto
    if match.player1_id == player2_id:
        return False, "No puedes aceptar tu propio reto."

    # Validar que si el reto era para alguien específico, coincida el ID
    if match.player2_id != 0 and match.player2_id != player2_id:
        return False, "Este reto no es para ti."

    # Iniciar la partida
    match.player2_id = player2_id
    match.status = "IN_PROGRESS"
    session.commit()

    return True, f"⚔️ ¡El duelo ha comenzado bajo la supervisión de **{match.referee_name}**!"
