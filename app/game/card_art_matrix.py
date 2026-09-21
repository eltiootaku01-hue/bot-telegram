from __future__ import annotations

from dataclasses import dataclass

from app.art.prompt_policy import NO_EXPLICIT_VISUAL_POLICY, STYLE_POLICY
from enum import StrEnum


class CardArtTier(StrEnum):
    """Production framing tier. This is separate from the combat rarity ladder."""

    CLOSE_UP = "D_C_B_R"
    S = "S"
    SR = "SR"
    UR = "UR"


@dataclass(frozen=True, slots=True)
class CardArtProfile:
    tier: CardArtTier
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
        framing="primer plano / close-up",
        wardrobe="atuendo base, cotidiano o uniforme",
        composition="rostro y hombros, cabeza completa visible y hombros limpios",
        function="legibilidad limpia para avatares y mensajes rápidos",
        suggestive_level="ninguno",
        inspection_level="alto",
        prompt_direction=(
            "Retrato vertical de rostro y hombros; expresión clara; atuendo base; "
            "fondo sencillo y limpio; silueta muy legible."
        ),
    ),
    CardArtTier.S: CardArtProfile(
        tier=CardArtTier.S,
        framing="plano medio",
        wardrobe="vestimenta ajustada, traje de baño o lencería temática solo bajo compuerta adulta",
        composition="tórax con foco en busto, espalda o cadera sin desnudez",
        function="carta de glamour moderado con lectura inmediata del personaje",
        suggestive_level="ecchi moderado, no explícito",
        inspection_level="muy alto",
        prompt_direction=(
            "Plano medio vertical con pose sugerente pero no explícita; énfasis visual "
            "en silueta, torso, espalda o cadera; cobertura opaca; composición elegante."
        ),
    ),
    CardArtTier.SR: CardArtProfile(
        tier=CardArtTier.SR,
        framing="plano tres cuartos",
        wardrobe="atuendo temático de nicho; gothic lolita, kemonomimi, bunny suit elegante, yukata/kimono festivo o combate estilizado",
        composition="casi cuerpo completo y pose dinámica",
        function="variante de nicho con alta fidelidad de vestuario y movimiento",
        suggestive_level="ecchi avanzado, no explícito",
        inspection_level="muy alto",
        prompt_direction=(
            "Plano tres cuartos vertical, casi cuerpo completo, pose dinámica y "
            "temática; prioridad absoluta a anatomía coherente, manos correctas, "
            "ropa legible y perspectiva estable."
        ),
    ),
    CardArtTier.UR: CardArtProfile(
        tier=CardArtTier.UR,
        framing="plano general",
        wardrobe="cosplay o crossover conceptual premium; fanservice no explícito bajo compuerta adulta",
        composition="cuerpo completo con fondo elaborado y profundidad de escena",
        function="edición premium de colección con composición abierta",
        suggestive_level="ecchi premium, estrictamente no explícito",
        inspection_level="doble / máximo",
        prompt_direction=(
            "Plano general vertical con cuerpo completo de pies a cabeza, pose dinámica "
            "y fondo elaborado; composición cinematográfica; anatomía y perspectiva "
            "priorizadas sobre cualquier efecto decorativo."
        ),
    ),
}


def art_profile(tier: str | CardArtTier) -> CardArtProfile:
    try:
        return ART_MATRIX[CardArtTier(str(tier))]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Unsupported card art tier: {tier!r}") from exc


def tier_from_label(label: str) -> CardArtTier:
    normalized = label.strip().upper()
    if normalized in {"D", "C", "B", "R", "D_C_B_R"}:
        return CardArtTier.CLOSE_UP
    if normalized in {"S", "SR", "UR"}:
        return CardArtTier(normalized)
    raise ValueError(f"Unsupported card art label: {label!r}")


def production_filename(character_id: str, variant: str = "normal") -> str:
    safe_id = character_id.strip()
    safe_variant = variant.strip().casefold()
    if not safe_id or "/" in safe_id or "\\" in safe_id:
        raise ValueError("character_id must be a safe asset identifier")
    if safe_variant not in {"normal", "shiny"}:
        raise ValueError("variant must be normal or shiny")
    return f"{safe_id}--{safe_variant}.jpg"


def build_card_art_prompt(
    *,
    character_name: str,
    anime: str,
    tier: str | CardArtTier,
    adult_eligible: bool = False,
    outfit_note: str = "",
    background_note: str = "",
) -> str:
    """Build an auditable prompt; never grants adult fanservice implicitly."""
    profile = art_profile(tier)
    extras = []
    if outfit_note.strip():
        extras.append(f"Outfit notes: {outfit_note.strip()}.")
    if background_note.strip():
        extras.append(f"Background notes: {background_note.strip()}.")

    if profile.tier is CardArtTier.CLOSE_UP or not adult_eligible:
        safety = (
            "NON-SUGGESTIVE PRODUCTION MODE: no erotic emphasis, no lingerie, no swimwear, "
            f"no transparent clothing, no sexual pose. {NO_EXPLICIT_VISUAL_POLICY}"
        )
    else:
        safety = (
            "ADULT-ELIGIBLE NON-EXPLICIT MODE: tasteful glamour only; "
            f"{NO_EXPLICIT_VISUAL_POLICY}"
        )

    strictness = (
        "ANATOMY QA: correct human proportions, two natural hands with five fingers each, "
        "no extra limbs, no fused fingers, no broken joints, no impossible perspective, "
        "no duplicated facial features, no cropped feet in UR."
    )
    return (
        f"WaifuMon card art for {character_name} from {anime}. "
        f"Production tier: {profile.tier.value}. {profile.prompt_direction} "
        f"Wardrobe: {profile.wardrobe}. "
        f"Function: {profile.function}. "
        f"{safety} "
        f"{STYLE_POLICY} "
        "No watermark, no logos, no text baked into the image. "
        f"{strictness} "
        + " ".join(extras)
        + " Output target: portrait JPG 1024x1536."
    )


def matrix_manifest() -> dict[str, dict[str, str]]:
    return {
        tier.value: {
            "framing": profile.framing,
            "wardrobe": profile.wardrobe,
            "composition": profile.composition,
            "function": profile.function,
            "suggestive_level": profile.suggestive_level,
            "inspection_level": profile.inspection_level,
        }
        for tier, profile in ART_MATRIX.items()
    }
