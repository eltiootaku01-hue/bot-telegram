# -*- coding: utf-8 -*-
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.dependencies import get_current_user, get_db
from api.security.telegram_auth import TelegramUserData
from src.db.models import CardInstance

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=List[Dict[str, Any]])
def get_user_inventory(
    current_user: TelegramUserData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna las cartas del usuario autenticado vía Telegram initData.
    Combina la copia única (CardInstance) con las estadísticas del catálogo (Card).
    """
    stmt = (
        select(CardInstance)
        .where(CardInstance.owner_id == current_user.id)
        .options(selectinload(CardInstance.card))
    )
    instances = db.scalars(stmt).all()

    inventory = []
    for inst in instances:
        inventory.append({
            "instance_id": inst.id,
            "copy_number": inst.copy_number,
            "level": inst.level,
            "card_id": inst.card.id,
            "name": inst.card.name,
            "rarity": inst.card.rarity,
            "attack": inst.card.attack,
            "defense": inst.card.defense,
            "element": inst.card.element,
            "image_url": inst.card.image_url,
            "acquired_at": inst.acquired_at.isoformat() if inst.acquired_at else None
        })

    return inventory
