from __future__ import annotations

from app.core.identity import BotIdentity
from app.knowledge.models import KnowledgeArticle, KnowledgeSourceKind


ARTICLES: tuple[KnowledgeArticle, ...] = (
    KnowledgeArticle(
        key="cari_capabilities",
        identity=BotIdentity.CARI,
        title="Qué puede hacer Cari",
        keywords=(
            "que podes hacer", "qué podés hacer", "que puede hacer cari",
            "para que sirve cari", "en que me podes ayudar", "en qué me podés ayudar",
            "ayuda", "podés ayudar", "podes ayudar",
        ),
        answer=(
            "Puedo atender el Café Otaku, charlar sobre anime y manga, orientarte dentro de "
            "la comunidad y llamar a Cami, Sunna o Chie cuando una tarea corresponde mejor a ellas."
        ),
        source="Canon operativo del proyecto: Cari como anfitriona del Café Otaku.",
        source_kind=KnowledgeSourceKind.AUTHOR,
        priority=100,
    ),
    KnowledgeArticle(
        key="cari_how_answering_works",
        identity=BotIdentity.CARI,
        title="Cómo responde Cari sin IA",
        keywords=(
            "sin ia", "sin ai", "como respondes", "cómo respondes",
            "como sabes", "cómo sabes", "de donde sacas", "de dónde sacás",
        ),
        answer=(
            "Cuando no uso IA, no invento respuestas: busco coincidencias en mi conocimiento "
            "local y en las reglas del café. Si no encuentro una fuente suficiente, te digo "
            "que no lo sé o llamo a una persona que pueda revisar el tema."
        ),
        source="Arquitectura local-first del proyecto.",
        source_kind=KnowledgeSourceKind.AUTHOR,
        priority=95,
    ),
    KnowledgeArticle(
        key="cari_support_basics",
        identity=BotIdentity.CARI,
        title="Acompañamiento básico ante malestar",
        keywords=(
            "estoy mal", "me siento mal", "estoy triste", "estoy nervioso",
            "estoy nerviosa", "ansiedad", "me angustia", "necesito hablar",
            "necesito ayuda", "me pasó algo", "me paso algo",
        ),
        answer=(
            "Te escucho. No hace falta que cuentes todo de golpe. Podemos empezar por lo más "
            "urgente: qué pasó, qué necesitás ahora y si estás a salvo. Puedo acompañarte y "
            "ayudarte a buscar apoyo de alguien de confianza, pero no hago diagnósticos ni "
            "reemplazo a un profesional."
        ),
        source="WHO, Psychological First Aid: Guide for Field Workers (2011).",
        source_kind=KnowledgeSourceKind.EXTERNAL_GUIDELINE,
        priority=90,
        follow_up="¿Querés contarme qué pasó primero?",
    ),
    KnowledgeArticle(
        key="cari_distress_safety",
        identity=BotIdentity.CARI,
        title="Situación de posible riesgo",
        keywords=(
            "no quiero seguir", "quiero desaparecer", "me quiero morir",
            "quiero hacerme daño", "me voy a lastimar", "suicidio",
            "me lastime", "me lastimé", "me hice daño",
        ),
        answer=(
            "Primero importa tu seguridad. Si existe peligro inmediato, buscá ayuda humana "
            "ahora mismo y contactá los servicios de emergencia de tu zona. No tenés que "
            "manejar una situación así en soledad. Puedo quedarme acompañándote mientras "
            "buscás a una persona de confianza."
        ),
        source="WHO, Psychological First Aid; seguridad, escucha y conexión con apoyo.",
        source_kind=KnowledgeSourceKind.EXTERNAL_GUIDELINE,
        priority=120,
        follow_up="¿Hay alguien cerca que pueda quedarse con vos ahora?",
    ),
    KnowledgeArticle(
        key="cari_cafe",
        identity=BotIdentity.CARI,
        title="Café Otaku",
        keywords=(
            "cafe otaku", "café otaku", "que hay en el cafe", "qué hay en el café",
            "como funciona el cafe", "cómo funciona el café",
        ),
        answer=(
            "El Café Otaku es el punto de encuentro de Ciudad Animals. Yo llevo la parte "
            "social; Sunna se ocupa de juegos y WaifuMon, Cami del archivo y publicaciones, "
            "y Chie de recepción, reglas y coordinación."
        ),
        source="Catálogo de Ciudad Animals y perfiles operativos del proyecto.",
        source_kind=KnowledgeSourceKind.AUTHOR,
        priority=85,
    ),
    KnowledgeArticle(
        key="cami_archive",
        identity=BotIdentity.CAMI,
        title="Archivo de Cami",
        keywords=(
            "archivo", "buscar imagen", "buscar material", "catalogo", "catálogo",
            "publicar imagen", "etiquetas", "pedido de imagen",
        ),
        answer=(
            "Puedo revisar el archivo, clasificar material, comprobar etiquetas, asociar "
            "imágenes a pedidos y preparar publicaciones. Cuando un dato no está registrado, "
            "prefiero marcarlo como pendiente antes que inventarlo."
        ),
        source="Rol operativo de Cami y módulo de medios del proyecto.",
        source_kind=KnowledgeSourceKind.AUTHOR,
        priority=100,
    ),
    KnowledgeArticle(
        key="sunna_waifumon",
        identity=BotIdentity.SUNNA,
        title="WaifuMon",
        keywords=(
            "waifumon", "como capturo", "cómo capturo", "capturar waifu",
            "encuentro", "encuentro salvaje", "coleccion", "colección",
            "fusion", "evolucion", "evolución",
        ),
        answer=(
            "WaifuMon usa encuentros locales, respuestas por botones, colección, copias, "
            "experiencia y evolución. Las reglas se resuelven localmente y la misma captura "
            "no debería pagarse dos veces aunque lleguen acciones duplicadas."
        ),
        source="Reglas locales de WaifuMon, progresión e idempotencia del proyecto.",
        source_kind=KnowledgeSourceKind.AUTHOR,
        priority=100,
    ),
    KnowledgeArticle(
        key="chie_setup",
        identity=BotIdentity.CHIE,
        title="Configuración de Chie",
        keywords=(
            "configurar grupo", "como configuro el grupo", "configurar", "permisos", "administradora",
            "como preparo el grupo", "cómo preparo el grupo",
            "foro", "temas", "reglas",
        ),
        answer=(
            "Primero compruebo que soy administradora del grupo y que tengo los permisos "
            "necesarios. Después preparo los temas del foro y guardo la configuración. "
            "No considero suficiente que alguien diga que los permisos están puestos: los compruebo."
        ),
        source="Flujo de configuración de Chie y permisos de Telegram.",
        source_kind=KnowledgeSourceKind.AUTHOR,
        priority=100,
    ),
)


def articles_for(identity: BotIdentity) -> tuple[KnowledgeArticle, ...]:
    return tuple(article for article in ARTICLES if article.identity is identity)
