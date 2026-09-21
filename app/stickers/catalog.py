from __future__ import annotations

from dataclasses import dataclass

from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity


@dataclass(frozen=True, slots=True)
class StickerSpec:
    """Stable, author-approved sticker contract independent from Telegram file IDs."""

    key: str
    identity: BotIdentity
    intent: CharacterIntent
    pose: str
    face: str
    prop: str
    text: str = ""

    @property
    def telegram_lookup_key(self) -> str:
        return self.key


_STICKER_TEMPLATES: dict[BotIdentity, dict[CharacterIntent, tuple[str, str, str, str]]] = {
    BotIdentity.CARI: {
        CharacterIntent.GREETING: ("saluda con una mano", "sonrisa abierta", "tacita de café", "¡Hola!"),
        CharacterIntent.CALLED: ("se gira rápidamente", "sorpresa alegre", "campanita del café", "¿Sí?"),
        CharacterIntent.AFFECTION: ("se inclina con cariño", "sonrisa cálida", "juguito", "Awww…"),
        CharacterIntent.REASSURANCE: ("pulgar arriba", "calma segura", "delantal", "Todo bien."),
        CharacterIntent.BELONGING: ("abre los brazos", "sonrisa protectora", "mesa del café", "Hay lugar."),
        CharacterIntent.FAREWELL: ("se despide agitando la mano", "sonrisa tranquila", "tacita", "¡Nos vemos!"),
        CharacterIntent.THANKS: ("junta las manos", "agradecimiento alegre", "juguito", "¡Gracias!"),
        CharacterIntent.CELEBRATION: ("salta de alegría", "ojos brillantes", "confeti", "¡Yay!"),
        CharacterIntent.CONFUSION: ("inclina la cabeza", "confusión simpática", "libretito", "¿Eh?"),
        CharacterIntent.BUSY: ("corre con prisa", "concentración divertida", "dos tazas", "¡Ya voy!"),
        CharacterIntent.GAME_SUCCESS: ("levanta el puño", "orgullo alegre", "ficha de juego", "¡Victoria!"),
        CharacterIntent.GAME_MISS: ("se tapa la cara", "sorpresa teatral", "dado", "¡Oh no!"),
    },
    BotIdentity.SUNNA: {
        CharacterIntent.GREETING: ("hace un pequeño saludo", "sonrisa tímida", "control de juego", "Hola."),
        CharacterIntent.CALLED: ("mira de reojo", "atención contenida", "audífonos", "Hm?"),
        CharacterIntent.AFFECTION: ("se acerca un poco", "sonrisa suave", "pequeña bufanda", "Gracias…"),
        CharacterIntent.REASSURANCE: ("asiente despacio", "calma serena", "control", "Estoy bien."),
        CharacterIntent.BELONGING: ("se sienta junto al grupo", "sonrisa discreta", "cojín", "Hay lugar."),
        CharacterIntent.FAREWELL: ("levanta dos dedos", "despedida tranquila", "control", "Nos vemos."),
        CharacterIntent.THANKS: ("inclina la cabeza", "gratitud sincera", "pequeña bolsa de regalo", "Gracias."),
        CharacterIntent.CELEBRATION: ("levanta el puño", "alegría contenida", "trofeo pequeño", "Bien."),
        CharacterIntent.CONFUSION: ("mira una pantalla", "duda curiosa", "manual de juego", "No entiendo."),
        CharacterIntent.BUSY: ("juega concentrada", "concentración", "dos controles", "Espera."),
        CharacterIntent.GAME_SUCCESS: ("muestra una ficha ganadora", "sorpresa satisfecha", "trofeo", "Ganamos."),
        CharacterIntent.GAME_MISS: ("parpadea sorprendida", "decepción leve", "dado", "Hm…"),
    },
    BotIdentity.CAMI: {
        CharacterIntent.GREETING: ("saluda con una carpeta", "sonrisa discreta", "ficha de archivo", "Hola."),
        CharacterIntent.CALLED: ("levanta la vista", "atención serena", "lápiz", "¿Sí?"),
        CharacterIntent.AFFECTION: ("ofrece una pequeña nota", "ternura contenida", "papelito", "Lo valoro."),
        CharacterIntent.REASSURANCE: ("hace una señal de calma", "serenidad", "checklist", "Está bien."),
        CharacterIntent.BELONGING: ("señala una silla", "amabilidad discreta", "silla del archivo", "Puedes quedarte."),
        CharacterIntent.FAREWELL: ("cierra una carpeta", "despedida tranquila", "archivo", "Hasta luego."),
        CharacterIntent.THANKS: ("anota algo", "gratitud tranquila", "lápiz", "Gracias."),
        CharacterIntent.CELEBRATION: ("muestra una ficha aprobada", "satisfacción discreta", "sello", "Completado."),
        CharacterIntent.CONFUSION: ("compara dos fichas", "duda analítica", "dos documentos", "No coincide."),
        CharacterIntent.BUSY: ("revisa documentos", "concentración", "pila de carpetas", "Un momento."),
        CharacterIntent.GAME_SUCCESS: ("muestra una ficha ganadora", "orgullo sereno", "marcador", "Buen resultado."),
        CharacterIntent.GAME_MISS: ("marca un error en rojo", "sorpresa leve", "lápiz", "Reviso."),
    },
    BotIdentity.CHIE: {
        CharacterIntent.GREETING: ("saluda nerviosamente", "sonrisa tímida", "carpeta de recepción", "B-buenas…"),
        CharacterIntent.CALLED: ("se sobresalta", "sorpresa nerviosa", "campanita", "¿S-sí?"),
        CharacterIntent.AFFECTION: ("junta las manos", "felicidad tímida", "corazón de papel", "G-gracias…"),
        CharacterIntent.REASSURANCE: ("respira y asiente", "calma tímida", "lista revisada", "Todo en orden."),
        CharacterIntent.BELONGING: ("ofrece una silla", "sonrisa nerviosa", "silla de recepción", "H-hay lugar."),
        CharacterIntent.FAREWELL: ("se despide con ambas manos", "sonrisa tímida", "agenda", "H-hasta pronto."),
        CharacterIntent.THANKS: ("hace una reverencia pequeña", "gratitud nerviosa", "nota", "G-gracias."),
        CharacterIntent.CELEBRATION: ("levanta una lista aprobada", "alegría nerviosa", "confeti mínimo", "¡S-salió bien!"),
        CharacterIntent.CONFUSION: ("mira una lista al revés", "confusión nerviosa", "papeles", "¿E-eh?"),
        CharacterIntent.BUSY: ("ordena varias listas", "concentración nerviosa", "tres carpetas", "U-un momento…"),
        CharacterIntent.GAME_SUCCESS: ("levanta un sello", "sorpresa feliz", "sello de aprobado", "¡S-sí!"),
        CharacterIntent.GAME_MISS: ("se lleva las manos a la cabeza", "susto cómico", "papel arrugado", "¡A-ay!"),
    },
}


def _build_catalog() -> tuple[StickerSpec, ...]:
    specs: list[StickerSpec] = []
    for identity, by_intent in _STICKER_TEMPLATES.items():
        for intent, (pose, face, prop, text) in by_intent.items():
            specs.append(
                StickerSpec(
                    key=f"{identity.value}-{intent.value}-01",
                    identity=identity,
                    intent=intent,
                    pose=pose,
                    face=face,
                    prop=prop,
                    text=text,
                )
            )
    return tuple(specs)


STICKER_CATALOG: tuple[StickerSpec, ...] = _build_catalog()


_BY_INTENT: dict[
    tuple[BotIdentity, CharacterIntent],
    tuple[StickerSpec, ...],
] = {}
for _spec in STICKER_CATALOG:
    key = (_spec.identity, _spec.intent)
    _BY_INTENT[key] = (*_BY_INTENT.get(key, ()), _spec)


def sticker_for(
    identity: BotIdentity,
    intent: CharacterIntent,
    *,
    roll: int = 0,
) -> StickerSpec | None:
    """Choose an authored sticker deterministically; never invent a sticker key."""
    options = _BY_INTENT.get((identity, intent), ())
    if not options:
        return None
    return options[abs(roll) % len(options)]


def sticker_prompt(spec: StickerSpec) -> str:
    """Generate a safe visual prompt for an artist or image generator."""
    return (
        f"Telegram sticker of {spec.identity.value.title()}, "
        f"cute clean anime/chibi style, expressive but non-explicit, "
        f"{spec.pose}, {spec.face}, holding or using {spec.prop}. "
        "Simple readable silhouette, fondo transparente, contorno limpio marcado, "
        "no nudity, no sexualized pose, no gore, no watermark."
        + (f' Include the short Spanish text "{spec.text}".' if spec.text else "")
    )


def validate_catalog() -> None:
    identities = set(BotIdentity)
    if {spec.identity for spec in STICKER_CATALOG} != identities:
        raise ValueError("Sticker catalog must cover every bot identity")
    keys = [spec.key for spec in STICKER_CATALOG]
    if len(keys) != len(set(keys)):
        raise ValueError("Sticker keys must be unique")
    if any(not spec.key.strip() for spec in STICKER_CATALOG):
        raise ValueError("Sticker key cannot be empty")


validate_catalog()
