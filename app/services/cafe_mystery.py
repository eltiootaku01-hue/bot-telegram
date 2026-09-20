from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CafeMystery:
    key: str
    title: str
    question: str
    options: tuple[str, ...]
    answer_index: int
    reveal: str

    def __post_init__(self) -> None:
        if len(self.options) < 2:
            raise ValueError("A Café mystery needs at least two options")
        if not 0 <= self.answer_index < len(self.options):
            raise ValueError("Café mystery answer_index is out of range")


CAFE_MYSTERIES: tuple[CafeMystery, ...] = (
    CafeMystery(
        key="campanita",
        title="La campanita perdida",
        question="Cari dejó la campanita del mostrador en algún sitio. ¿Dónde tiene más sentido buscar primero?",
        options=(
            "Debajo del mostrador",
            "En la zona de juegos",
            "Dentro del archivo de Cami",
        ),
        answer_index=0,
        reveal="Primero debajo del mostrador. Cari suele dejar cosas cerca de donde las estaba usando.",
    ),
    CafeMystery(
        key="pedido",
        title="El pedido confundido",
        question="Aparecieron dos pedidos con el mismo anime pero distinto detalle. ¿Qué debería comprobar Cami primero?",
        options=(
            "El color del recipiente",
            "Las etiquetas y la descripción original",
            "Quién llegó más tarde",
        ),
        answer_index=1,
        reveal="Las etiquetas y la descripción original. Cami debe comprobar la fuente antes de asumir qué pedido es cuál.",
    ),
    CafeMystery(
        key="aviso",
        title="El aviso misterioso",
        question="Chie encuentra un aviso sin autor. ¿Qué acción encaja mejor con su forma de trabajar?",
        options=(
            "Publicarlo inmediatamente",
            "Borrarlo sin revisar",
            "Comprobar el origen antes de publicarlo",
        ),
        answer_index=2,
        reveal="Comprobar el origen antes de publicarlo. La coordinación de Chie prioriza verificar antes de difundir.",
    ),
    CafeMystery(
        key="sunna-regalo",
        title="Un pequeño regalo",
        question="Sunna recibe un pequeño regalo durante una tarde tranquila. ¿Qué respuesta encaja mejor con su comportamiento cotidiano?",
        options=(
            "Ignorarlo completamente",
            "Agradecerlo de forma discreta",
            "Convertirlo en un anuncio público",
        ),
        answer_index=1,
        reveal="Agradecerlo de forma discreta. El afecto de Sunna puede ser breve sin ser indiferente.",
    ),
    CafeMystery(
        key="cafe-tranquilo",
        title="El Café demasiado tranquilo",
        question="El Café está extrañamente silencioso. ¿Qué haría Cari primero?",
        options=(
            "Revisar si alguien necesita ayuda",
            "Cerrar el Café sin avisar",
            "Apagar las luces y desaparecer",
        ),
        answer_index=0,
        reveal="Revisar si alguien necesita ayuda. El impulso protector de Cari funciona incluso en momentos tranquilos.",
    ),
)


def mystery_for(day_key: str, chat_id: int) -> CafeMystery:
    if not day_key.strip():
        raise ValueError("day_key must not be empty")
    seed = f"{day_key}:{chat_id}".encode("utf-8")
    digest = __import__("hashlib").sha256(seed).digest()
    index = int.from_bytes(digest[:8], "big") % len(CAFE_MYSTERIES)
    return CAFE_MYSTERIES[index]
