# -*- coding: utf-8 -*-
import datetime
import enum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Database Base Class
class Base(DeclarativeBase):
    pass


# -------------------------------------------------------------------
# ENUMS DE CARTAS
# -------------------------------------------------------------------
class CardType(str, enum.Enum):
    WAIFU = "WAIFU"
    EQUIPMENT = "EQUIPMENT"
    MAGIC = "MAGIC"


class CardRarity(str, enum.Enum):
    R = "R"
    SR = "SR"
    SSR = "SSR"


# -------------------------------------------------------------------
# 1. USUARIOS Y PERFILES (Soporta Telegram ID y Discord ID)
# -------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # Telegram User ID
    discord_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True, index=True)  # Discord ID opcional
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coins: Mapped[int] = mapped_column(Integer, default=100)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    # Relaciones
    inventory: Mapped[list["CardInstance"]] = relationship(
        "CardInstance", back_populates="owner", foreign_keys="CardInstance.owner_id"
    )


# -------------------------------------------------------------------
# 2. CATÁLOGO BASE DE CARTAS (Plantillas)
# -------------------------------------------------------------------
class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rarity: Mapped[str] = mapped_column(String(20), default="Common")  # Common, Rare, Epic, Legendary
    attack: Mapped[int] = mapped_column(Integer, default=10)
    defense: Mapped[int] = mapped_column(Integer, default=5)
    element: Mapped[str | None] = mapped_column(String(30), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_copies_minted: Mapped[int] = mapped_column(Integer, default=0)

    # Instancias derivadas
    instances: Mapped[list["CardInstance"]] = relationship("CardInstance", back_populates="card")


# -------------------------------------------------------------------
# 3. INSTANCIAS ÚNICAS DE CARTAS (Álbum / Inventario Real)
# -------------------------------------------------------------------
class CardInstance(Base):
    __tablename__ = "card_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID de la copia única
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # None si está libre en un drop
    copy_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Ej: Copia #15
    level: Mapped[int] = mapped_column(Integer, default=1)
    acquired_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    # Relaciones
    card: Mapped["Card"] = relationship("Card", back_populates="instances")
    owner: Mapped["User | None"] = relationship("User", back_populates="inventory")


# -------------------------------------------------------------------
# 4. DROPS EN GRUPOS Y CANALES
# -------------------------------------------------------------------
class GroupDrop(Base):
    __tablename__ = "group_drops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Tema/Topic ID de Telegram o Canal Discord
    card_instance_id: Mapped[str] = mapped_column(ForeignKey("card_instances.id"), nullable=False)
    is_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    claimed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


# -------------------------------------------------------------------
# 5. DUELOS Y BATALLAS ACTIVAS (Motor del Referí / Mesera)
# -------------------------------------------------------------------
class ActiveMatch(Base):
    __tablename__ = "active_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # Match ID
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    player1_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    player2_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    p1_hp: Mapped[int] = mapped_column(Integer, default=100)
    p2_hp: Mapped[int] = mapped_column(Integer, default=100)

    # Compatibilidad con el campo original del motor de duelos.
    current_turn_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Estado del mazo/carga de combate de cada jugador.
    p1_waifu_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p1_equip_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p1_magic_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p2_waifu_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p2_equip_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p2_magic_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Apuestas y moneda inicial del combate.
    staked_rarity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    p1_staked_card_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p2_staked_card_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    coin_picker_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    coin_choice: Mapped[str | None] = mapped_column(String(10), nullable=True)  # HEADS / TAILS
    first_turn_player_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_turn_player_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    staked_card_instance_id: Mapped[str | None] = mapped_column(
        ForeignKey("card_instances.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), default="IN_PROGRESS")  # WAITING, IN_PROGRESS, FINISHED
    referee_name: Mapped[str] = mapped_column(String(50), default="Mesera")  # Cami, Cari, Sunna
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


# -------------------------------------------------------------------
# 6. HISTORIAL DE DUELOS
# -------------------------------------------------------------------
class MatchHistory(Base):
    __tablename__ = "match_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(36), nullable=False)
    winner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    loser_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    staked_card_instance_id: Mapped[str | None] = mapped_column(ForeignKey("card_instances.id"), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # Resumen JSON de la pelea
    finished_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


# -------------------------------------------------------------------
# INICIALIZADOR AUTOMÁTICO DE TABLAS
# -------------------------------------------------------------------
def init_db(db_url: str = "sqlite:///bot_database.db"):
    """Crea todas las tablas en la base de datos SQLite si no existen."""
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    print("✓ Base de datos e hiper-tablas inicializadas correctamente.")


if __name__ == "__main__":
    init_db()
