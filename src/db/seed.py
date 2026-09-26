# -*- coding: utf-8 -*-
import sys
import os

# Permitir importaciones del módulo src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.db.models import Base, Card


def seed_cards(db_url: str = "sqlite:///bot_database.db"):
    """Pobla la tabla de cartas con personajes iniciales de prueba."""
    engine = create_engine(db_url, echo=False)

    # Asegura que las tablas existan antes de insertar
    Base.metadata.create_all(engine)

    sample_cards = [
        # Comunes
        Card(
            name="Capibara Bebé",
            rarity="Common",
            attack=15,
            defense=20,
            element="Agua",
            image_url="https://placehold.co/400x600/png?text=Capibara+Bebe",
        ),
        Card(
            name="Capibara Explorador",
            rarity="Common",
            attack=25,
            defense=18,
            element="Planta",
            image_url="https://placehold.co/400x600/png?text=Capibara+Explorador",
        ),
        # Raras
        Card(
            name="Capibara Caballero",
            rarity="Rare",
            attack=50,
            defense=55,
            element="Tierra",
            image_url="https://placehold.co/400x600/png?text=Capibara+Caballero",
        ),
        Card(
            name="Capibara Mago",
            rarity="Rare",
            attack=65,
            defense=30,
            element="Fuego",
            image_url="https://placehold.co/400x600/png?text=Capibara+Mago",
        ),
        # Épicas
        Card(
            name="Cari, Gemela Táctica",
            rarity="Epic",
            attack=85,
            defense=75,
            element="Rayo",
            image_url="https://placehold.co/400x600/png?text=Cari+Tactica",
        ),
        Card(
            name="Cami, Gemela Impulsiva",
            rarity="Epic",
            attack=95,
            defense=60,
            element="Fuego",
            image_url="https://placehold.co/400x600/png?text=Cami+Impulsiva",
        ),
        # Legendaria
        Card(
            name="Rey Capibara Soberano",
            rarity="Legendary",
            attack=130,
            defense=115,
            element="Luz",
            image_url="https://placehold.co/400x600/png?text=Rey+Capibara",
        ),
    ]

    with Session(engine) as session:
        # Verificar si ya hay cartas para evitar duplicados al reejecutar
        existing_count = session.query(Card).count()
        if existing_count > 0:
            print(f"ℹ️ La base de datos ya contiene {existing_count} cartas. Omitiendo la carga.")
            return

        session.add_all(sample_cards)
        session.commit()
        print(f"✓ ¡Éxito! Se añadieron {len(sample_cards)} cartas al catálogo inicial.")


if __name__ == "__main__":
    seed_cards()
