from app.game.models import Character, Element, Rarity
from app.game.waifu_catalog import ALL_WAIFUS


CHARACTERS: dict[str, Character] = {
    definition.id: Character(
        id=definition.id,
        name=definition.name,
        anime=definition.anime,
        rarity=definition.rarity,
        attack_name=f"Técnica de {definition.element.value}",
        defense_name="Defensa",
        special_name=f"Especial de {definition.name}",
        popularity_score=definition.popularity_score,
        power_score=definition.power_score,
        element=definition.element,
        popularity_rank=definition.ranker_rank or definition.recent_rank,
        popularity_source=definition.popularity_source,
    )
    for definition in ALL_WAIFUS
}

# Preserve the original project ID used by existing collections and tests.
if "anya-forger" in CHARACTERS:
    legacy_anya = CHARACTERS.pop("anya-forger")
    CHARACTERS["anya"] = Character(
        id="anya",
        name=legacy_anya.name,
        anime=legacy_anya.anime,
        rarity=legacy_anya.rarity,
        level=legacy_anya.level,
        attack_name=legacy_anya.attack_name,
        defense_name=legacy_anya.defense_name,
        special_name=legacy_anya.special_name,
        popularity_score=legacy_anya.popularity_score,
        power_score=legacy_anya.power_score,
        element=legacy_anya.element,
        card_tier=legacy_anya.card_tier,
        popularity_rank=legacy_anya.popularity_rank,
        popularity_source=legacy_anya.popularity_source,
    )

CHARACTERS["taiga"] = Character(
    id="taiga",
    name="Taiga Aisaka",
    anime="Toradora!",
    rarity=Rarity.B,
    attack_name="Golpe de katana de madera",
    defense_name="¿No sabría hacerse bolita?",
    special_name="Golpe de tigre",
    popularity_score=45,
    power_score=50,
    element=Element.FIRE,
    popularity_source="Catálogo inicial del proyecto; pendiente de ranking externo.",
)

WILD_RARITIES = frozenset({Rarity.D, Rarity.C})
LEGACY_CHARACTER_IDS = {"anya-forger": "anya"}


def canonical_character_id(character_id: str) -> str:
    return LEGACY_CHARACTER_IDS.get(character_id, character_id)


def get_character(character_id: str) -> Character:
    return CHARACTERS[canonical_character_id(character_id)]


def wild_characters() -> tuple[Character, ...]:
    """Return characters eligible for normal public encounters."""
    return tuple(
        character
        for character in CHARACTERS.values()
        if character.rarity in WILD_RARITIES
    )


def catalog_size() -> int:
    """Return the number of playable characters currently registered."""
    return len(CHARACTERS)
