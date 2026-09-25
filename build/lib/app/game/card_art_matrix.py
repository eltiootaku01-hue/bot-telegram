from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.art.prompt_policy import (
    FINAL_ASCENSION_DIRECTION,
    NO_EXPLICIT_VISUAL_POLICY,
    STYLE_POLICY,
    UR_ALT_HOLO_POLICY,
)


class CardArtTier(StrEnum):
    """Visual progression tier, independent from combat rarity."""

    CLOSE_UP = "D_C_B_R"
    S = "S"
    SR = "SR"
    UR = "UR"


class CardArtVariant(StrEnum):
    """Production/edition variant for a card illustration."""

    NORMAL = "normal"
    SHINY = "shiny"
    UR_ALT_HOLO = "ur-alt-holo"


@dataclass(frozen=True, slots=True)
class CardArtProfile:
    tier: CardArtTier
    visual_phase: str
    framing: str
    wardrobe: str
    composition: str
    function: str
    suggestive_level: str
    inspection_level: str
    prompt_direction: str


ART_MATRIX: dict[CardArtTier, CardArtProfile] = {
    CardArtTier.CLOSE_UP: CardArtProfile(
        tier=CardArtTier.CLOSE_UP,
        visual_phase="Fase 1 / base illustration",
        framing="primer plano / close-up",
        wardrobe="atuendo cotidiano, uniforme escolar o atuendo base completamente cubierto",
        composition="rostro y hombros; cabeza completa visible; expresión e identidad dominan la imagen",
        function="legibilidad limpia para avatares y mensajes rápidos",
        suggestive_level="ninguno",
        inspection_level="alto",
        prompt_direction=(
            "Retrato vertical de rostro y hombros; expresión clara; atuendo base; "
            "fondo sencillo; silueta muy legible; prioridad absoluta a identidad y anatomía."
        ),
    ),
    CardArtTier.S: CardArtProfile(
        tier=CardArtTier.S,
        visual_phase="Fase 2 / ascensión intermedia",
        framing="plano medio",
        wardrobe=(
            "atuendo de combate o vestuario dinámico mejorado; completamente cubierto "
            "salvo detalles no íntimos del diseño"
        ),
        composition="plano medio desde cabeza hasta cintura o muslos; pose activa y lectura clara del vestuario",
        function="transición visual hacia una carta de combate más expresiva",
        suggestive_level="glamour no explícito, sin enfoque sexual obligatorio",
        inspection_level="muy alto",
        prompt_direction=(
            "Plano medio vertical, pose de combate o acción controlada, vestuario mejorado, "
            "efectos moderados y composición con profundidad."
        ),
    ),
    CardArtTier.SR: CardArtProfile(
        tier=CardArtTier.SR,
        visual_phase="Fase 2 / ascensión intermedia avanzada",
        framing="plano tres cuartos",
        wardrobe=(
            "atuendo de combate mejorado o vestuario temático elegante; puede incluir "
            "gothic lolita, kemonomimi, bunny suit elegante, yukata/kimono festivo u otros conceptos no explícitos"
        ),
        composition="casi cuerpo completo; postura dinámica; manos, calzado y silueta deben leerse completos",
        function="alta fidelidad de vestuario, movimiento y presencia escénica",
        suggestive_level="glamour no explícito",
        inspection_level="muy alto",
        prompt_direction=(
            "Plano tres cuartos vertical, casi cuerpo completo, pose dinámica y temática; "
            "prioridad a anatomía coherente, manos correctas, ropa legible y perspectiva estable."
        ),
    ),
    CardArtTier.UR: CardArtProfile(
        tier=CardArtTier.UR,
        visual_phase="Final Ascension / Magnificent Art",
        framing="plano general",
        wardrobe=(
            "atuendo definitivo de combate, gala, fantasía o concepto premium; "
            "la versión canónica no requiere contenido sugerente"
        ),
        composition=(
            "cuerpo completo de pies a cabeza, fondo elaborado, múltiples planos de profundidad, "
            "efectos visuales de alta gama y jerarquía focal cinematográfica"
        ),
        function="ilustración definitiva y más impactante del personaje",
        suggestive_level="glamour premium; cualquier variante adulta sigue siendo estrictamente no explícita",
        inspection_level="máximo / doble revisión",
        prompt_direction=(
            f"{FINAL_ASCENSION_DIRECTION} Cuerpo completo visible, sin cortar pies, manos ni elementos clave."
        ),
    ),
}


def art_profile(tier: str | CardArtTier) -> CardArtProfile:
    try:
        resolved = tier if isinstance(tier, CardArtTier) else tier_from_label(tier)
        return ART_MATRIX[resolved]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Unsupported card art tier: {tier!r}") from exc


def tier_from_label(label: str) -> CardArtTier:
    normalized = label.strip().upper()
    if normalized in {"D", "C", "B", "R", "D_C_B_R"}:
        return CardArtTier.CLOSE_UP
    if normalized in {"S", "SR", "UR"}:
        return CardArtTier(normalized)
    raise ValueError(f"Unsupported card art label: {label!r}")


def variant_from_label(label: str) -> CardArtVariant:
    normalized = label.strip().casefold()
    aliases = {
        "normal": CardArtVariant.NORMAL,
        "canon": CardArtVariant.NORMAL,
        "canonical": CardArtVariant.NORMAL,
        "shiny": CardArtVariant.SHINY,
        "holo": CardArtVariant.UR_ALT_HOLO,
        "holo/shiny": CardArtVariant.UR_ALT_HOLO,
        "ur_alt": CardArtVariant.UR_ALT_HOLO,
        "ur-alt": CardArtVariant.UR_ALT_HOLO,
        "ur-alt-holo": CardArtVariant.UR_ALT_HOLO,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported card art variant: {label!r}") from exc


def validate_variant_for_tier(
    tier: str | CardArtTier,
    variant: str | CardArtVariant,
) -> CardArtVariant:
    resolved_tier = tier if isinstance(tier, CardArtTier) else tier_from_label(tier)
    resolved_variant = variant if isinstance(variant, CardArtVariant) else variant_from_label(variant)
    if resolved_variant is CardArtVariant.UR_ALT_HOLO and resolved_tier is not CardArtTier.UR:
        raise ValueError("UR_ALT_HOLO is available only for UR")
    return resolved_variant


def production_filename(
    character_id: str,
    variant: str | CardArtVariant = CardArtVariant.NORMAL,
    *,
    tier: str | CardArtTier | None = None,
) -> str:
    safe_id = character_id.strip()
    if not safe_id or "/" in safe_id or "\\" in safe_id:
        raise ValueError("character_id must be a safe asset identifier")
    resolved_variant = variant if isinstance(variant, CardArtVariant) else variant_from_label(variant)
    if tier is not None:
        resolved_variant = validate_variant_for_tier(tier, resolved_variant)
    suffix = resolved_variant.value
    return f"{safe_id}--{suffix}.jpg"


def build_card_art_prompt(
    *,
    character_name: str,
    anime: str,
    tier: str | CardArtTier,
    adult_eligible: bool = False,
    variant: str | CardArtVariant = CardArtVariant.NORMAL,
    outfit_note: str = "",
    background_note: str = "",
) -> str:
    """Build an auditable, fail-closed card-art prompt."""
    profile = art_profile(tier)
    resolved_variant = validate_variant_for_tier(profile.tier, variant)

    if resolved_variant is CardArtVariant.UR_ALT_HOLO:
        if not adult_eligible:
            raise ValueError("UR_ALT_HOLO requires adult_eligible=true")
        variant_direction = (
            "EDITION: UR ALTERNATE HOLO/SHINY. Add controlled holographic highlights, "
            "iridescent particles, polished foil-like light effects and a refined alternate pose. "
            "This is a premium non-explicit glamour edition."
        )
        safety = f"{UR_ALT_HOLO_POLICY} {NO_EXPLICIT_VISUAL_POLICY}"
    elif resolved_variant is CardArtVariant.SHINY:
        variant_direction = (
            "EDITION: SHINY. Use subtle foil-like highlights and clean luminous accents while "
            "preserving the canonical character design."
        )
        safety = f"NON-SUGGESTIVE SHINY MODE. {NO_EXPLICIT_VISUAL_POLICY}"
    else:
        variant_direction = "EDITION: NORMAL / CANONICAL."
        safety = f"NON-SUGGESTIVE PRODUCTION MODE. {NO_EXPLICIT_VISUAL_POLICY}"

    if profile.tier in {CardArtTier.CLOSE_UP, CardArtTier.S, CardArtTier.SR}:
        # The historical adult gate remains fail-closed for all non-UR variants.
        if profile.tier is CardArtTier.CLOSE_UP or not adult_eligible:
            wardrobe_direction = profile.wardrobe
        else:
            wardrobe_direction = (
                f"{profile.wardrobe}; any styling remains tasteful, covered and non-explicit."
            )
    else:
        wardrobe_direction = profile.wardrobe

    extras: list[str] = []
    if outfit_note.strip():
        extras.append(f"Outfit notes: {outfit_note.strip()}.")
    if background_note.strip():
        extras.append(f"Background notes: {background_note.strip()}.")

    strictness = (
        "ANATOMY QA: correct human proportions, two natural hands with five fingers each, "
        "no extra limbs, no fused fingers, no broken joints, no impossible perspective, "
        "no duplicated facial features, no cropped feet in UR."
    )
    return (
        f"WaifuMon card art for {character_name} from {anime}. "
        f"Production tier: {profile.tier.value}. Visual phase: {profile.visual_phase}. "
        f"Variant: {resolved_variant.value}. {profile.prompt_direction} "
        f"Wardrobe: {wardrobe_direction}. Function: {profile.function}. "
        f"{variant_direction} {safety} {STYLE_POLICY} "
        "No watermark, no logos, no text baked into the image. "
        f"{strictness} "
        + " ".join(extras)
        + " Output target: portrait JPG 1024x1536."
    )


def matrix_manifest() -> dict[str, dict[str, str]]:
    return {
        tier.value: {
            "visual_phase": profile.visual_phase,
            "framing": profile.framing,
            "wardrobe": profile.wardrobe,
            "composition": profile.composition,
            "function": profile.function,
            "suggestive_level": profile.suggestive_level,
            "inspection_level": profile.inspection_level,
        }
        for tier, profile in ART_MATRIX.items()
    }
