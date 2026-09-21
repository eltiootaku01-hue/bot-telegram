from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import MysteryAttempt, MysteryRound
from app.db.repositories import MemberRepository


MYSTERY_POINTS = 15


@dataclass(frozen=True, slots=True)
class MysteryCase:
    key: str
    title: str
    question: str
    clues: tuple[str, ...]
    options: tuple[str, ...]
    answer_index: int


@dataclass(frozen=True, slots=True)
class MysteryStart:
    round: MysteryRound
    case: MysteryCase
    created: bool


MYSTERY_CASES: tuple[MysteryCase, ...] = (
    MysteryCase(
        "lost-spoon",
        "La cuchara desaparecida",
        "Una cuchara del Café Otaku apareció en la caja de servilletas. ¿Quién la dejó ahí?",
        (
            "Cari dice que estaba atendiendo la mesa de la ventana.",
            "Cami anotó que la cuchara estaba junto al mostrador antes de ordenar el archivo.",
            "Sunna estuvo jugando en la zona de juegos y pidió una cuchara para una bebida.",
            "Chie encontró la caja de servilletas mientras ordenaba la recepción.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),
    MysteryCase(
        "closed-book",
        "El libro cerrado",
        "Un libro que nadie estaba leyendo terminó cerrado en la estantería equivocada. ¿Quién lo movió?",
        (
            "Cami fue la única que estaba clasificando libros.",
            "Cari estuvo limpiando mesas, lejos del archivo.",
            "Sunna estaba en una partida y no salió de su zona.",
            "Chie estaba preparando avisos en recepción.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        1,
    ),
    MysteryCase(
        "bell-ring",
        "La campanita traviesa",
        "La campanita sonó dos veces sin que nadie hiciera un pedido. ¿Quién estaba practicando?",
        (
            "Cari suele tocar la campanita cuando quiere llamar la atención.",
            "Cami dijo que no necesitaba nada del mostrador.",
            "Sunna estaba mirando la campanita con curiosidad.",
            "Chie estaba revisando una lista y no quería interrumpir.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),
    MysteryCase(
        "missing-card",
        "La carta que faltaba",
        "Una carta de juego desapareció de la mesa y terminó dentro de un cuaderno. ¿Quién la guardó?",
        (
            "Cami estaba usando un cuaderno para registrar material.",
            "Cari se llevó una caja de cartas para limpiar la mesa.",
            "Sunna estaba organizando una partida y revisando las cartas.",
            "Chie no había entrado a la zona de juegos.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),

    MysteryCase(
        "cake-slice",
        "La porción de pastel perdida",
        "Quedaban cuatro porciones de pastel y de pronto solo quedan tres. ¿Quién tomó una?",
        (
            "Cari dice que dejó las cuatro porciones juntas antes de atender otra mesa.",
            "Cami registró cuatro porciones cuando cerró el archivo.",
            "Sunna volvió de la zona de juegos con un plato vacío y admitió que tenía hambre.",
            "Chie estuvo organizando avisos en recepción y no pasó por la mesa.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),
    MysteryCase(
        "charger-switch",
        "El cargador cambiado",
        "El teléfono de la mesa amaneció con un cargador distinto al suyo. ¿Quién lo cambió?",
        (
            "Cari usa el cargador que está junto a la caja cuando su teléfono se queda sin batería.",
            "Cami dejó escrito que necesitaba el cargador largo para revisar un dispositivo del archivo.",
            "Sunna dijo que su batería estaba completa y no necesitó cargar nada.",
            "Chie guardó los cables de repuesto en una caja marcada.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        1,
    ),
    MysteryCase(
        "phone-last-use",
        "El teléfono usado a escondidas",
        "El teléfono compartido del café muestra una última llamada que nadie recuerda. ¿Quién lo usó?",
        (
            "Cari estaba buscando una receta y dice que no hizo ninguna llamada.",
            "Cami anotó una llamada breve para confirmar un dato del archivo.",
            "Sunna no tenía permitido usar ese teléfono sin avisar.",
            "Chie estaba en una videollamada desde su propio teléfono.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        1,
    ),
    MysteryCase(
        "battery-missing",
        "La batería que bajó sola",
        "Un teléfono estaba al 100% y apareció al 63%. ¿Qué pasó?",
        (
            "Cari dejó una aplicación de música abierta.",
            "Cami comprobó que no había actualizaciones pendientes.",
            "Sunna estuvo jugando con el teléfono para aprender un juego nuevo.",
            "Chie mantuvo el teléfono apagado durante la mañana.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),
    MysteryCase(
        "earbud-left",
        "El auricular solitario",
        "Solo queda un auricular en la mesa; el otro desapareció. ¿Quién lo movió?",
        (
            "Cari estaba limpiando alrededor de la mesa.",
            "Cami guardó un pequeño dispositivo del archivo para que no se dañara.",
            "Sunna estuvo escuchando música y dejó un auricular junto a su juego.",
            "Chie no tocó la mesa porque estaba revisando avisos.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),
    MysteryCase(
        "cable-knot",
        "El nudo imposible",
        "Un cable que estaba enrollado terminó hecho un nudo imposible. ¿Quién lo dejó así?",
        (
            "Cari asegura que intentó ordenarlo rápidamente antes de salir.",
            "Cami explica que el cable se guardó en una caja y quedó recto.",
            "Sunna pidió un cable para cargar un mando y lo devolvió deprisa.",
            "Chie tenía una bolsa de repuestos y estaba etiquetando cada cable.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),
    MysteryCase(
        "remote-fridge",
        "El control remoto en la heladera",
        "El control remoto del café apareció junto a las bebidas frías. ¿Quién lo dejó ahí?",
        (
            "Cari llevó una bandeja a la heladera justo antes de limpiar el salón.",
            "Cami estaba en el archivo y no vio la televisión.",
            "Sunna estaba jugando y no necesitó el control.",
            "Chie estaba ordenando la recepción y fue quien notó el control.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        0,
    ),
    MysteryCase(
        "sugar-drawer",
        "El cajón de azúcar",
        "El azúcar desapareció del mostrador y apareció en un cajón de la recepción. ¿Quién lo guardó?",
        (
            "Cari preparó bebidas y dejó el azúcar junto a la cafetera.",
            "Cami registró que el recipiente estaba vacío.",
            "Sunna no entró en la recepción.",
            "Chie estaba ordenando el cajón y guardó lo que estaba fuera de lugar.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        3,
    ),
    MysteryCase(
        "manga-bookmark",
        "El marcador cambiado",
        "Un marcador apareció en otro manga distinto al que lo tenía. ¿Quién lo movió?",
        (
            "Cari dejó el manga abierto mientras ayudaba a una mesa.",
            "Cami estaba clasificando libros por tema.",
            "Sunna estaba jugando y no leyó esa tarde.",
            "Chie solo revisó los avisos de la recepción.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        1,
    ),
    MysteryCase(
        "late-notification",
        "La notificación nocturna",
        "Durante el turno tranquilo sonó una notificación en un teléfono que nadie decía estar usando. ¿De quién era?",
        (
            "Cari tenía su teléfono en el mostrador.",
            "Cami había silenciado el suyo antes de archivar documentos.",
            "Sunna estaba probando sonidos nuevos en su teléfono.",
            "Chie dejó el suyo en recepción y estaba ordenando papeles.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        2,
    ),
    MysteryCase(
        "wrong-sign",
        "El aviso cambiado",
        "Un cartel de 'cerrado' apareció en una mesa abierta. ¿Quién lo movió?",
        (
            "Chie estaba revisando los avisos de la recepción.",
            "Cari estaba sirviendo bebidas.",
            "Cami estaba en el archivo.",
            "Sunna estaba jugando y no necesitaba carteles.",
        ),
        ("Cari", "Cami", "Sunna", "Chie"),
        3,
    ),
)


class MysteryService:
    """Deterministic daily mystery game with a single rewarded winner."""

    CASES = MYSTERY_CASES

    def __init__(self) -> None:
        self.validate_cases()

    @classmethod
    def validate_cases(cls) -> None:
        for case in cls.CASES:
            if len(case.options) != 4:
                raise ValueError(f"Mystery case {case.key} must have exactly four options")
            if len(set(option.casefold().strip() for option in case.options)) != len(case.options):
                raise ValueError(f"Mystery case {case.key} has duplicate options")
            if not 0 <= case.answer_index < len(case.options):
                raise ValueError(f"Mystery case {case.key} has an invalid answer index")
            if len(case.clues) < 3:
                raise ValueError(f"Mystery case {case.key} needs at least three clues")
            answer = case.options[case.answer_index].casefold().strip()
            if not any(answer in clue.casefold() for clue in case.clues):
                raise ValueError(
                    f"Mystery case {case.key} has no clue that identifies its answer"
                )

    @classmethod
    def _case_for(cls, chat_id: int, day_key: str) -> MysteryCase:
        digest = hashlib.sha256(f"{chat_id}:{day_key}".encode("utf-8")).digest()
        return cls.CASES[int.from_bytes(digest[:8], "big") % len(cls.CASES)]

    @classmethod
    async def start_round(
        cls,
        session: AsyncSession,
        *,
        chat_id: int,
        day_key: str,
    ) -> MysteryStart:
        existing = await session.scalar(
            select(MysteryRound).where(
                MysteryRound.chat_id == chat_id,
                MysteryRound.day_key == day_key,
            )
        )
        if existing is not None:
            case = cls._case_for(chat_id, day_key)
            if existing.status == "failed":
                now = utc_now()
                existing.title = case.title
                existing.question = case.question
                existing.clues_json = json.dumps(case.clues, ensure_ascii=False)
                existing.options_json = json.dumps(case.options, ensure_ascii=False)
                existing.answer_index = case.answer_index
                existing.points = MYSTERY_POINTS
                existing.status = "active"
                existing.winner_user_id = None
                existing.message_id = None
                existing.expires_at = now + timedelta(hours=24)
                existing.updated_at = now
                await session.flush()
                return MysteryStart(existing, case, True)
            return MysteryStart(existing, case, False)

        case = cls._case_for(chat_id, day_key)
        now = utc_now()
        row = MysteryRound(
            chat_id=chat_id,
            day_key=day_key,
            title=case.title,
            question=case.question,
            clues_json=json.dumps(case.clues, ensure_ascii=False),
            options_json=json.dumps(case.options, ensure_ascii=False),
            answer_index=case.answer_index,
            points=MYSTERY_POINTS,
            status="active",
            expires_at=now + timedelta(hours=24),
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(MysteryRound).where(
                    MysteryRound.chat_id == chat_id,
                    MysteryRound.day_key == day_key,
                )
            )
            if existing is None:
                raise
            return MysteryStart(existing, case, False)
        return MysteryStart(row, case, True)

    @staticmethod
    def decode_round(row: MysteryRound) -> MysteryCase:
        return MysteryCase(
            key=f"db-{row.id}",
            title=row.title,
            question=row.question,
            clues=tuple(json.loads(row.clues_json)),
            options=tuple(json.loads(row.options_json)),
            answer_index=row.answer_index,
        )

    async def answer(
        self,
        session: AsyncSession,
        *,
        round_id: int,
        user_id: int,
        option_index: int,
        chat_id: int,
    ) -> tuple[str, int]:
        row = await session.get(MysteryRound, round_id)
        if row is None or row.chat_id != chat_id:
            return "invalid", 0
        now = utc_now()
        if row.status == "won":
            return "already_won", 0
        if row.status != "active" or now >= row.expires_at:
            if row.status == "active":
                row.status = "expired"
                row.updated_at = now
                await session.flush()
            return "expired", 0

        case = self.decode_round(row)
        if option_index < 0 or option_index >= len(case.options):
            return "invalid", 0

        try:
            async with session.begin_nested():
                session.add(
                    MysteryAttempt(
                        round_id=round_id,
                        user_id=user_id,
                        option_index=option_index,
                        correct=option_index == row.answer_index,
                    )
                )
                await session.flush()
        except IntegrityError:
            return "already_answered", 0

        if option_index != row.answer_index:
            return "wrong", 0

        claimed = await session.execute(
            update(MysteryRound)
            .where(
                MysteryRound.id == round_id,
                MysteryRound.status == "active",
                MysteryRound.expires_at > now,
            )
            .values(
                status="won",
                winner_user_id=user_id,
                updated_at=now,
            )
        )
        if claimed.rowcount != 1:
            return "already_won", 0

        balance = await MemberRepository().add_points(
            session,
            user_id=user_id,
            chat_id=chat_id,
            amount=row.points,
            reason="Misterio diario",
            reference_type="mystery",
            reference_id=str(round_id),
            commit=False,
        )
        await session.flush()
        return "correct", balance
