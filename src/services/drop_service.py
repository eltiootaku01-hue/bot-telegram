# -*- coding: utf-8 -*-
import uuid
import random
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from src.db.models import Card, CardInstance, GroupDrop, User

# Probabilidades por rareza
RARITY_WEIGHTS = {
    "Common": 60,
    "Rare": 25,
    "Epic": 12,
    "Legendary": 3,
}

def spawn_card_drop(session: Session, group_id: int, message_thread_id: Optional[int] = None) -> Tuple[GroupDrop, CardInstance, Card]:
    """
    Selecciona una carta aleatoria según sus probabilidades de rareza,
    genera una copia única (CardInstance) y registra el drop en el grupo.
    """
    # 1. Seleccionar rareza según pesos
    rarities = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

    # 2. Obtener cartas disponibles de esa rareza
    cards = session.scalars(select(Card).where(Card.rarity == chosen_rarity)).all()
    
    # Fallback por si no hay cartas de esa rareza en la BD
    if not cards:
        cards = session.scalars(select(Card).all())

    chosen_card = random.choice(cards)

    # 3. Incrementar el contador de copias impresas de esta carta
    chosen_card.total_copies_minted += 1
    copy_num = chosen_card.total_copies_minted

    # 4. Crear la instancia única de la carta
    instance_id = str(uuid.uuid4())
    card_instance = CardInstance(
        id=instance_id,
        card_id=chosen_card.id,
        owner_id=None,  # Todavía nadie la reclamó
        copy_number=copy_num,
        level=1
    )
    session.add(card_instance)

    # 5. Registrar el drop activo
    drop = GroupDrop(
        group_id=group_id,
        message_thread_id=message_thread_id,
        card_instance_id=instance_id,
        is_claimed=False
    )
    session.add(drop)
    session.commit()

    return drop, card_instance, chosen_card


def claim_card_drop(session: Session, drop_id: int, user_id: int, username: Optional[str] = None) -> Tuple[bool, str]:
    """
    Intenta asignar una carta reclamada a un usuario.
    Retorna (Éxito, Mensaje explicativo).
    """
    drop = session.get(GroupDrop, drop_id)

    if not drop:
        return False, "El drop ya no existe."

    if drop.is_claimed:
        return False, "¡Demasiado tarde! Alguien más ya reclamó esta carta."

    # Asegurar que el usuario existe en la base de datos
    user = session.get(User, user_id)
    if not user:
        user = User(id=user_id, username=username)
        session.add(user)

    # Asignar la propiedad de la carta
    card_instance = session.get(CardInstance, drop.card_instance_id)
    card_instance.owner_id = user_id

    # Marcar el drop como reclamado
    drop.is_claimed = True
    drop.claimed_by_id = user_id

    session.commit()

    card_name = card_instance.card.name
    copy_num = card_instance.copy_number
    return True, f"¡Felicidades! Reclamaste **{card_name}** (Copia #{copy_num})."
