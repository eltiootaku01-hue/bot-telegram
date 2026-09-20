from __future__ import annotations

from dataclasses import dataclass

from app.core.identity import BotIdentity


@dataclass(frozen=True, slots=True)
class WorldCatalogDefinition:
    """Author-approved world element that may exist before anyone uses it."""

    bot_identity: BotIdentity
    entry_type: str
    entry_key: str
    label: str
    priority: int = 0


WORLD_CATALOG: tuple[WorldCatalogDefinition, ...] = (
    WorldCatalogDefinition(
        BotIdentity.CARI,
        "place",
        "cafe_otaku",
        "Café Otaku — punto de encuentro central de Ciudad Animals",
        100,
    ),
    WorldCatalogDefinition(
        BotIdentity.CARI,
        "role",
        "cari_hostess",
        "Cari — anfitriona y presencia comunitaria del Café Otaku",
        90,
    ),
    WorldCatalogDefinition(BotIdentity.CARI, "topic", "anime", "Anime", 60),
    WorldCatalogDefinition(BotIdentity.CARI, "topic", "manga", "Manga", 60),
    WorldCatalogDefinition(BotIdentity.CARI, "action", "community", "Charla y vida comunitaria", 50),
    WorldCatalogDefinition(BotIdentity.CARI, "action", "cafe_menu", "Menú del Café Otaku", 50),
    WorldCatalogDefinition(BotIdentity.CARI, "action", "daily_recommendation", "Recomendación diaria del Café", 50),
    WorldCatalogDefinition(BotIdentity.CARI, "action", "cafe_mystery", "Misterio diario del Café", 50),
    WorldCatalogDefinition(
        BotIdentity.SUNNA,
        "place",
        "game_zone",
        "Zona de juegos del Café Otaku",
        100,
    ),
    WorldCatalogDefinition(
        BotIdentity.SUNNA,
        "action",
        "waifumon",
        "WaifuMon — encuentros, colección y progresión",
        90,
    ),
    WorldCatalogDefinition(BotIdentity.SUNNA, "action", "gacha", "Gacha de personajes", 80),
    WorldCatalogDefinition(BotIdentity.SUNNA, "action", "trivia", "Trivia de anime", 80),
    WorldCatalogDefinition(BotIdentity.SUNNA, "action", "combat", "Combate", 70),
    WorldCatalogDefinition(BotIdentity.SUNNA, "action", "collection", "Colección y evolución", 70),
    WorldCatalogDefinition(
        BotIdentity.CAMI,
        "place",
        "archive",
        "Archivo y mostrador de publicaciones",
        100,
    ),
    WorldCatalogDefinition(
        BotIdentity.CAMI,
        "role",
        "cami_archivist",
        "Cami — archivista, observadora y encargada de publicaciones",
        90,
    ),
    WorldCatalogDefinition(BotIdentity.CAMI, "action", "media_catalog", "Catálogo de medios", 80),
    WorldCatalogDefinition(BotIdentity.CAMI, "action", "publication", "Publicaciones", 80),
    WorldCatalogDefinition(BotIdentity.CAMI, "action", "statistics", "Estadísticas", 70),
    WorldCatalogDefinition(BotIdentity.CAMI, "action", "catalog_search", "Búsqueda del catálogo", 65),
    WorldCatalogDefinition(
        BotIdentity.CHIE,
        "place",
        "reception",
        "Recepción y coordinación de Ciudad Animals",
        100,
    ),
    WorldCatalogDefinition(
        BotIdentity.CHIE,
        "role",
        "chie_coordinator",
        "Chie — coordinación, avisos, permisos y reglas",
        90,
    ),
    WorldCatalogDefinition(BotIdentity.CHIE, "action", "onboarding", "Bienvenida y configuración", 80),
    WorldCatalogDefinition(BotIdentity.CHIE, "action", "welcome", "Bienvenida de nuevos integrantes", 75),
    WorldCatalogDefinition(BotIdentity.CHIE, "action", "moderation", "Moderación y permisos", 80),
    WorldCatalogDefinition(BotIdentity.CHIE, "topic", "rules", "Reglas de la comunidad", 70),
    WorldCatalogDefinition(BotIdentity.CHIE, "topic", "welcome", "Tema de bienvenida", 65),
    WorldCatalogDefinition(
        BotIdentity.CARI,
        "relationship",
        "cari-cami",
        "Cari ↔ Cami — hermanas; corazón y razón del equipo",
        100,
    ),
    WorldCatalogDefinition(
        BotIdentity.CARI,
        "relationship",
        "cari-sunna",
        "Cari ↔ Sunna — aceptación, protección y pertenencia",
        100,
    ),
    WorldCatalogDefinition(
        BotIdentity.CAMI,
        "relationship",
        "cami-sunna",
        "Cami ↔ Sunna — comprensión, confianza y escucha",
        90,
    ),
    WorldCatalogDefinition(
        BotIdentity.CHIE,
        "relationship",
        "chie-sunna",
        "Chie ↔ Sunna — miedo, acompañamiento y pertenencia",
        90,
    ),
)


def catalog_for_identity(identity: BotIdentity) -> tuple[WorldCatalogDefinition, ...]:
    return tuple(item for item in WORLD_CATALOG if item.bot_identity is identity)
