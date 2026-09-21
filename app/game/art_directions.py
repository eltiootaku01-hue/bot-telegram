from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharacterArtDirection:
    """Per-avatar visual direction used to keep the card library non-uniform."""

    palette: str
    expression: str
    pose: str
    environment: str
    motif: str


ART_DIRECTIONS: dict[str, CharacterArtDirection] = {
    "yor-forger": CharacterArtDirection(
        "negro, vino y dorado",
        "serena y ligeramente amenazante",
        "perfil de tres cuartos con una mano preparada para atacar",
        "salón nocturno elegante con luces cálidas",
        "rosa de cristal y detalles de asesina",
    ),
    "erza-scarlet": CharacterArtDirection(
        "rojo escarlata, plata y azul profundo",
        "segura y decidida",
        "postura de caballero con hombros abiertos y espada visible",
        "arena mágica con partículas y arquitectura fantástica",
        "armadura, emblema de gremio y destellos mágicos",
    ),
    "asuna-yuuki": CharacterArtDirection(
        "blanco, rojo y dorado",
        "amable pero concentrada",
        "avance diagonal con espada ligera en guardia",
        "paisaje luminoso inspirado en un mundo virtual fantástico",
        "brillo de datos y líneas de energía",
    ),
    "rias-gremory": CharacterArtDirection(
        "rojo oscuro, negro y carmesí",
        "confiada y elegante",
        "pose frontal relajada con una mano extendida",
        "salón gótico con iluminación teatral",
        "aura demoníaca estilizada y rosas",
    ),
    "esdeath": CharacterArtDirection(
        "azul hielo, blanco y azul marino",
        "fría y dominante",
        "espada baja y capa flotando por el viento",
        "campo nevado con cristales helados",
        "copos geométricos y hielo fracturado",
    ),
    "nami": CharacterArtDirection(
        "naranja, blanco y azul marino",
        "sonrisa astuta y segura",
        "pose dinámica con el brazo levantado como si guiara el clima",
        "cubierta de barco bajo un cielo de tormenta",
        "relámpagos estilizados y mapa náutico",
    ),
    "lucy-heartfilia": CharacterArtDirection(
        "azul celeste, blanco y dorado",
        "entusiasta y luminosa",
        "gesto de invocación con una llave mágica en primer plano",
        "cielo de fantasía con estrellas y constelaciones",
        "llaves zodiacales y círculos mágicos",
    ),
    "mirajane-strauss": CharacterArtDirection(
        "blanco, turquesa y negro",
        "dulce con una energía peligrosa contenida",
        "pose lateral suave con alas/aura transformada insinuada",
        "cielo crepuscular con nubes luminosas",
        "motivos de transformación y pétalos",
    ),
    "albedo": CharacterArtDirection(
        "negro, blanco y dorado",
        "majestuosa y tranquila",
        "pose ceremonial con alas abiertas parcialmente",
        "trono oscuro con luz celestial detrás",
        "plumas negras y ornamentos dorados",
    ),
    "makima": CharacterArtDirection(
        "rojo, crema y marrón oscuro",
        "calma, observadora y controlada",
        "pose frontal mínima con composición simétrica",
        "oficina sobria con perspectiva profunda",
        "líneas circulares sutiles y contraste cinematográfico",
    ),
    "power": CharacterArtDirection(
        "rojo, marfil y negro",
        "sonrisa exageradamente orgullosa",
        "pose asimétrica y expansiva como si acabara de ganar",
        "calle urbana caótica al atardecer",
        "formas de sangre estilizadas y energía angular",
    ),
    "violet-evergarden": CharacterArtDirection(
        "azul petróleo, lila y crema",
        "melancólica y serena",
        "postura elegante con manos juntas y vestido movido por el viento",
        "campo floral con cartas suspendidas",
        "sobres, flores y luz suave",
    ),
    "hinata-hyuga": CharacterArtDirection(
        "lavanda, azul noche y blanco",
        "tímida pero firme",
        "postura defensiva suave con manos preparadas",
        "bosque nocturno con luna difusa",
        "ondas de chakra y hojas flotantes",
    ),
    "tsunade": CharacterArtDirection(
        "verde, blanco y dorado",
        "segura y protectora",
        "pose de combate con un puño adelantado",
        "ruinas de entrenamiento con polvo suspendido",
        "símbolo médico y fracturas de energía",
    ),
    "rin-tohsaka": CharacterArtDirection(
        "azul profundo, rojo y negro",
        "orgullosa y concentrada",
        "pose de hechizo con joyas mágicas entre los dedos",
        "torre urbana nocturna con círculos arcanos",
        "gemas rojas y geometría mágica",
    ),
    "mikasa-ackerman": CharacterArtDirection(
        "negro, gris acero y rojo oscuro",
        "seria y enfocada",
        "movimiento diagonal con equipo de movilidad desplegado",
        "tejados en perspectiva y cielo tormentoso",
        "cintas rojas y líneas de movimiento",
    ),
    "cha-hae-in": CharacterArtDirection(
        "blanco, dorado y azul hielo",
        "determinada y elegante",
        "espada vertical y torso girado hacia la cámara",
        "mazmorra luminosa con partículas",
        "brillos de maná y acero pulido",
    ),
    "kurumi-tokisaki": CharacterArtDirection(
        "negro, rojo y carmesí",
        "sonrisa juguetona e inquietante",
        "pose de reloj con un brazo elevado",
        "calle nocturna con reloj gigante desenfocado",
        "relojería, sombras y pétalos oscuros",
    ),
    "jibril": CharacterArtDirection(
        "rosa, blanco y dorado",
        "curiosidad orgullosa",
        "pose flotante con libro y alas extendidas",
        "biblioteca celestial llena de luz",
        "plumas, páginas y runas",
    ),
    "emilia": CharacterArtDirection(
        "blanco, lila y turquesa",
        "tierna y resoluta",
        "pose de conjuro defensivo con mano al frente",
        "bosque mágico iluminado por nieve",
        "cristales de hielo y flores",
    ),
    "ai-hoshino": CharacterArtDirection(
        "negro, rosa y violeta brillante",
        "sonrisa de escenario con calidez",
        "pose de idol con una mano cerca del rostro",
        "escenario de concierto con luces circulares",
        "estrellas, micrófono y destellos",
    ),
    "anya": CharacterArtDirection(
        "rosa, crema y verde menta",
        "expresión traviesa y curiosa",
        "pose pequeña y juguetona con manos escondidas detrás",
        "interior acogedor de estilo familiar",
        "estrellas pequeñas y elementos cómicos",
    ),
    "maomao": CharacterArtDirection(
        "verde jade, crema y marrón",
        "curiosidad analítica",
        "pose de observación con frasco medicinal",
        "laboratorio tradicional con plantas y estantes",
        "hierbas, frascos y notas manuscritas",
    ),
}


def direction_for(character_id: str) -> CharacterArtDirection:
    """Return explicit direction or a safe deterministic fallback."""
    return ART_DIRECTIONS.get(
        character_id,
        CharacterArtDirection(
            "paleta propia del personaje",
            "expresión coherente con su personalidad",
            "pose individual relacionada con su identidad",
            "entorno temático de su obra",
            "motivos visuales propios sin copiar diseños ajenos",
        ),
    )
