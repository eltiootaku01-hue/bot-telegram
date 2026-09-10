from app.game.models import Character, Rarity


CHARACTERS: dict[str, Character] = {
    "taiga": Character(id="taiga", name="Taiga Aisaka", anime="Toradora!", rarity=Rarity.B, attack_name="Golpe de katana de madera", defense_name="¿No sabría hacerse bolita?", special_name="Golpe de tigre"),
    "anya": Character(id="anya", name="Anya Forger", anime="SPY x FAMILY", rarity=Rarity.D, attack_name="Golpe de maní", defense_name="Cara de no sé nada", special_name="¡Waku waku!"),
}

WILD_RARITIES = {Rarity.D, Rarity.C, Rarity.B}


def get_character(character_id: str) -> Character:
    return CHARACTERS[character_id]


def wild_characters() -> list[Character]:
    """Wild encounters are deliberately capped at B."""
    return [character for character in CHARACTERS.values() if character.rarity in WILD_RARITIES]
