from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def game_hub_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎲 Gacha", callback_data="game:gacha:open"),
        InlineKeyboardButton(text="🎒 Inventario", callback_data="game:inventory:open"),
    )
    builder.row(InlineKeyboardButton(text="📚 Catálogo de waifus", callback_data="game:waifus:page:1"))
    builder.row(
        InlineKeyboardButton(text="⚔️ Combate", callback_data="game:combat:open"),
        InlineKeyboardButton(text="📡 Waifu Detector", callback_data="game:detector:open"),
    )
    builder.row(
        InlineKeyboardButton(text="🎯 Misiones", callback_data="game:missions:open"),
    )
    return builder.as_markup()


def combat_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Ataque", callback_data="game:combat:attack"),
        InlineKeyboardButton(text="🛡️ Defensa", callback_data="game:combat:defend"),
    )
    builder.row(InlineKeyboardButton(text="✨ Especial", callback_data="game:combat:special"))
    return builder.as_markup()


def gacha_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎲 Tirar gacha", callback_data="game:gacha:roll"))
    builder.row(
        InlineKeyboardButton(text="📚 Ver waifus", callback_data="game:waifus:page:1"),
        InlineKeyboardButton(text="🎒 Inventario", callback_data="game:inventory:open"),
    )
    return builder.as_markup()


def encounter_keyboard(encounter_id: str, options: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        builder.add(InlineKeyboardButton(
            text=option,
            callback_data=f"game:encounter:{encounter_id}:answer:{index}",
        ))
    builder.adjust(2)
    return builder.as_markup()


def trivia_keyboard(round_id: int, options: tuple[str, ...]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        builder.add(InlineKeyboardButton(
            text=option,
            callback_data=f"game:trivia:{round_id}:{index}",
        ))
    builder.adjust(2)
    return builder.as_markup()


def fusion_keyboard(character_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✨ Evolucionar", callback_data=f"game:fusion:{character_id}"))
    return builder.as_markup()

def waifu_catalog_keyboard(
    page: int,
    total_pages: int,
    active_filter=None,
    characters=(),
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for character in characters:
        if active_filter is None:
            detail_data = f"game:waifu:d:{character.id}:{page}"
        else:
            detail_data = (
                f"game:waifu:d:{character.id}:{page}:"
                f"{active_filter.field.value}:{active_filter.value}"
            )
        builder.add(
            InlineKeyboardButton(
                text=character.name[:28],
                callback_data=detail_data,
            )
        )
    if characters:
        builder.adjust(2)

    navigation = []
    if page > 1:
        if active_filter is None:
            callback_data = f"game:waifus:page:{page - 1}"
        else:
            callback_data = (
                f"game:waifus:page:{page - 1}:"
                f"{active_filter.field.value}:{active_filter.value}"
            )
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=callback_data))

    if page < total_pages:
        if active_filter is None:
            callback_data = f"game:waifus:page:{page + 1}"
        else:
            callback_data = (
                f"game:waifus:page:{page + 1}:"
                f"{active_filter.field.value}:{active_filter.value}"
            )
        navigation.append(InlineKeyboardButton(text="➡️", callback_data=callback_data))

    if navigation:
        builder.row(*navigation)

    builder.row(
        InlineKeyboardButton(
            text="🔎 Filtros",
            callback_data="game:waifus:filters",
        )
    )
    if active_filter is not None:
        builder.row(
            InlineKeyboardButton(
                text="🧹 Quitar filtro",
                callback_data="game:waifus:clear",
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="🎲 Volver al gacha",
            callback_data="game:gacha:open",
        )
    )
    return builder.as_markup()


def waifu_catalog_detail_keyboard(
    page: int,
    active_filter=None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if active_filter is None:
        callback_data = f"game:waifus:page:{page}"
    else:
        callback_data = (
            f"game:waifus:page:{page}:"
            f"{active_filter.field.value}:{active_filter.value}"
        )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Volver al catálogo",
            callback_data=callback_data,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎲 Gacha",
            callback_data="game:gacha:open",
        )
    )
    return builder.as_markup()



def waifu_filter_categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔥 Elemento", callback_data="game:waifus:filter:e"),
        InlineKeyboardButton(text="🎴 Carta", callback_data="game:waifus:filter:c"),
    )
    builder.row(
        InlineKeyboardButton(text="🏷️ Clase", callback_data="game:waifus:filter:r"),
        InlineKeyboardButton(text="📚 Fuente", callback_data="game:waifus:filter:s"),
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Volver al catálogo",
            callback_data="game:waifus:page:1",
        )
    )
    return builder.as_markup()


def waifu_filter_options_keyboard(field: str) -> InlineKeyboardMarkup:
    options = {
        "e": (
            ("🔥 Fuego", "fuego"),
            ("💧 Agua", "agua"),
            ("🌱 Tierra", "tierra"),
            ("🌪️ Aire", "aire"),
            ("❄️ Hielo", "hielo"),
            ("✨ Luz", "luz"),
            ("🌑 Oscuridad", "oscuridad"),
            ("⚡ Rayo", "rayo"),
            ("🧠 Mente", "mente"),
            ("🔮 Arcano", "arcano"),
            ("⚪ Neutro", "neutro"),
        ),
        "c": (
            ("R", "r"),
            ("SR", "sr"),
            ("UR", "ur"),
        ),
        "r": (
            ("D", "d"),
            ("C", "c"),
            ("B", "b"),
            ("A", "a"),
            ("S", "s"),
            ("SS", "ss"),
            ("SSS", "sss"),
        ),
        "s": (
            ("🏆 Ranker 2026", "ranker"),
            ("🆕 Anime Corner 2025", "recent"),
            ("📦 Catálogo inicial", "local"),
        ),
    }
    builder = InlineKeyboardBuilder()
    for label, value in options.get(field, ()):
        builder.add(
            InlineKeyboardButton(
                text=label,
                callback_data=f"game:waifus:set:{field}:{value}",
            )
        )
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Categorías",
            callback_data="game:waifus:filters",
        )
    )
    return builder.as_markup()

def mystery_keyboard(round_id: int, options: tuple[str, ...]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        builder.add(
            InlineKeyboardButton(
                text=option,
                callback_data=f"game:mystery:{round_id}:{index}",
            )
        )
    builder.adjust(2)
    return builder.as_markup()




def detector_keyboard(round_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⚔️ Enfrentar mob",
            callback_data=f"game:detector:fight:{round_id}",
        )
    )
    return builder.as_markup()



def gift_keyboard(drop_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎁 Reclamar regalo",
            callback_data=f"game:gift:claim:{drop_id}",
        )
    )
    return builder.as_markup()


def item_inventory_keyboard(items, character_ids) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.row(
            InlineKeyboardButton(
                text=f"🍰 {item.item_key} ×{item.quantity}",
                callback_data=f"game:item:choose:{item.item_key}",
            )
        )
    for character_id in character_ids:
        builder.row(
            InlineKeyboardButton(
                text=f"🎀 {character_id}",
                callback_data=f"game:item:waifu:{character_id}",
            )
        )
    return builder.as_markup()


def item_consume_keyboard(item_key: str, characters) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for character in characters:
        builder.add(
            InlineKeyboardButton(
                text=character.name[:28],
                callback_data=f"game:item:absorb:{item_key}:{character.id}",
            )
        )
    builder.adjust(2)
    return builder.as_markup()
