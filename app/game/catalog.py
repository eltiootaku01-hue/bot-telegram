from app.game.models import Character, Rarity


CHARACTERS: dict[str, Character] = {
    "taiga": Character(
        id="taiga",
        name="Taiga Aisaka",
        anime="Toradora!",
        rarity=Rarity.B,
        attack_name="Golpe de katana de madera",
        defense_name="¿No sabría hacerse bolita?",
        special_name="Golpe de tigre",
    ),
    "anya": Character(
        id="anya",
        name="Anya Forger",
        anime="SPY x FAMILY",
        rarity=Rarity.D,
        attack_name="Golpe de maní",
        defense_name="Cara de no sé nada",
        special_name="¡Waku waku!",
    ),
}

# Public wild encounters stop at C. B/A/S/SS/SSS are exceptional drops
# and can only enter a player's collection after private owner approval.
WILD_RARITIES = frozenset({Rarity.D, Rarity.C})


def get_character(character_id: str) -> Character:
    return CHARACTERS[character_id]


def wild_characters() -> tuple[Character, ...]:
    """Return only characters eligible for normal public encounters."""
    return tuple(character for character in CHARACTERS.values() if character.rarity in WILD_RARITIES)
