from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.db.models import StoryProgress


STORY_ARC_KEY = "cafe-origenes-v1"


@dataclass(frozen=True, slots=True)
class StoryChapter:
    number: int
    key: str
    title: str
    scene: str
    characters: tuple[BotIdentity, ...]
    gameplay_hook: str


STORY_CHAPTERS: tuple[StoryChapter, ...] = (
    StoryChapter(
        1,
        "lights-on",
        "Las luces del Café",
        (
            "Chie termina de ordenar la recepción y enciende las luces del Café Otaku. "
            "Cari corre de un lado al otro preparando el salón, mientras Cami acomoda el archivo. "
            "Sunna observa desde la zona de juegos sin acercarse demasiado. "
            "Nadie le exige que hable. Cari simplemente deja una silla libre cerca de la mesa."
        ),
        (BotIdentity.CHIE, BotIdentity.CARI, BotIdentity.CAMI, BotIdentity.SUNNA),
        "El Café queda establecido como punto común: recepción, salón, archivo y zona de juegos.",
    ),
    StoryChapter(
        2,
        "half-finished-game",
        "Una partida a medias",
        (
            "Sunna deja una partida sin terminar cuando escucha movimiento en el salón. "
            "Vuelve pensando que tendrá que explicar por qué se fue, pero Cari solo le pregunta "
            "si quiere sentarse. Sunna responde poco. Esta vez, sin embargo, se queda. "
            "Cami nota el cambio y no intenta analizarlo en voz alta."
        ),
        (BotIdentity.SUNNA, BotIdentity.CARI, BotIdentity.CAMI),
        "WaifuMon y los juegos pueden ser una puerta de entrada a la pertenencia, no solo una competencia.",
    ),
    StoryChapter(
        3,
        "the-spoon-case",
        "El caso de la cuchara",
        (
            "Una cuchara desaparece del mostrador y termina dentro de la caja de servilletas. "
            "Cami reconstruye las pistas y propone el primer misterio del Café. "
            "Cari quiere resolverlo a toda velocidad; Sunna observa; Chie toma notas para que nadie "
            "olvide la pequeña escena. La respuesta es sencilla, pero el valor está en jugarlo juntas."
        ),
        (BotIdentity.CAMI, BotIdentity.CARI, BotIdentity.SUNNA, BotIdentity.CHIE),
        "El misterio de Cami recompensa observar las pistas y compartir la escena sin convertirla en canon.",
    ),
    StoryChapter(
        4,
        "stay-together",
        "No tenés que hacerlo sola",
        (
            "Una tarde tranquila hace que Cari vuelva a pensar que debería poder encargarse de todo. "
            "Sunna reconoce la misma idea desde el extremo contrario: desaparecer para no molestar. "
            "No encuentran una solución épica. Solo terminan sentadas en la misma mesa. "
            "Cami se queda cerca y Chie deja cuatro vasos juntos antes de volver a recepción."
        ),
        (BotIdentity.CARI, BotIdentity.SUNNA, BotIdentity.CAMI, BotIdentity.CHIE),
        "La historia refuerza el arco compartido: proteger y pertenecer también puede significar quedarse acompañado.",
    ),
    StoryChapter(
        5,
        "shared-reception",
        "La recepción no está sola",
        (
            "Chie recibe una lista demasiado larga de tareas y, por unos minutos, intenta hacerlas todas. "
            "Cari toma una parte del salón, Cami ordena la información y Sunna se ofrece a quedarse cerca. "
            "Chie descubre algo pequeño pero importante: coordinar no significa cargar con todo, sino conseguir "
            "que las personas correctas puedan ayudarse."
        ),
        (BotIdentity.CHIE, BotIdentity.CARI, BotIdentity.CAMI, BotIdentity.SUNNA),
        "La coordinación de Chie se convierte en un trabajo compartido con los demás roles del Café.",
    ),
    StoryChapter(
        6,
        "home",
        "El Café se vuelve hogar",
        (
            "Al final de la primera historia, las luces del Café siguen encendidas. "
            "Cari atiende una mesa, Cami cierra una ficha, Sunna termina una partida y Chie revisa la última lista. "
            "Tío Otaku puede aparecer y hablar cuando él lo decida, porque sigue siendo una persona y un personaje "
            "operado manualmente. Las chicas no necesitan una narración automática para existir: el sistema solo "
            "conserva este pequeño hilo de ficción para que la comunidad pueda recorrerlo."
        ),
        (BotIdentity.CARI, BotIdentity.CAMI, BotIdentity.SUNNA, BotIdentity.CHIE),
        "Este arco es una capa narrativa del runtime y no convierte sus escenas en canon de la obra principal.",
    ),
)


@dataclass(frozen=True, slots=True)
class StoryView:
    progress: StoryProgress
    chapter: StoryChapter


class StoryService:
    """Persisted, deterministic story progression for the Café runtime."""

    ARC_KEY = STORY_ARC_KEY
    CHAPTERS = STORY_CHAPTERS

    @classmethod
    def _chapter(cls, number: int) -> StoryChapter:
        if not 1 <= number <= len(cls.CHAPTERS):
            raise ValueError(f"invalid story chapter: {number}")
        return cls.CHAPTERS[number - 1]

    @classmethod
    async def current(
        cls,
        session: AsyncSession,
        *,
        chat_id: int,
    ) -> StoryView:
        row = await session.scalar(
            select(StoryProgress).where(
                StoryProgress.chat_id == chat_id,
                StoryProgress.arc_key == cls.ARC_KEY,
            )
        )
        if row is None:
            row = StoryProgress(
                chat_id=chat_id,
                arc_key=cls.ARC_KEY,
                chapter=1,
                completed=False,
            )
            try:
                async with session.begin_nested():
                    session.add(row)
                    await session.flush()
            except IntegrityError:
                row = await session.scalar(
                    select(StoryProgress).where(
                        StoryProgress.chat_id == chat_id,
                        StoryProgress.arc_key == cls.ARC_KEY,
                    )
                )
                if row is None:
                    raise
        return StoryView(progress=row, chapter=cls._chapter(row.chapter))

    @classmethod
    async def advance(
        cls,
        session: AsyncSession,
        *,
        chat_id: int,
    ) -> StoryView:
        view = await cls.current(session, chat_id=chat_id)
        if view.progress.completed:
            return view
        if view.progress.chapter >= len(cls.CHAPTERS):
            view.progress.completed = True
        else:
            view.progress.chapter += 1
        view.progress.updated_at = __import__("app.core.time", fromlist=["utc_now"]).utc_now()
        await session.flush()
        return StoryView(
            progress=view.progress,
            chapter=cls._chapter(view.progress.chapter),
        )
