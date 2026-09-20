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


def get_character(character_id: str) -> Character:
    return CHARACTERS[character_id]


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
