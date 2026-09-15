# Auditoría viva del proyecto

Fecha de referencia: 2026-09-15

Este documento separa el estado técnico comprobable del avance hacia la visión completa de Ciudad Animals. Los porcentajes son estimaciones de alcance, no métricas automáticas de cobertura.

## Estado de la plataforma

| Área | Estado |
| --- | ---: |
| Arquitectura Core | 87% |
| Cuatro identidades independientes | 92% |
| Persistencia / SQLite / transacciones | 91% |
| Módulos y composición | 88% |
| Eventos, jobs, turnos y presencia | 84% |
| WaifuMon / progresión | 82% |
| Trivia | 80% |
| Media / archivo / publicaciones | 80% |
| Solicitudes / puntos | 82% |
| BotManager / empaquetado Windows | 90% |

## Estado de personajes y mundo

| Área | Estado |
| --- | ---: |
| Perfiles de Cari, Sunna, Cami y Chie | 60% |
| Director determinista | 60% |
| Repertorio escrito | 47% |
| Router determinista de intenciones | 50% |
| Rutinas y horarios | 52% |
| Interacciones entre personajes | 27% |
| Café Otaku | 23% |
| Ciudad Animals | 35% |
| Estadísticas del mundo | 40% |
| Registro automático de uso de escenas | 50% |
| IA como curadora periódica | 20% |
| Juegos nuevos (misterios, cartas, etc.) | 10% |
| GUI completa de edición | 20% |
| Operador humano Tío Otaku | 15% |

## Riesgos activos detectados por auditoría

1. La personalidad está definida pero no toda está conectada al runtime de conversación.
2. El repertorio sigue creciendo, pero todavía está lejos del volumen necesario para que los cuatro personajes tengan una vida de NPC amplia y sostenible.
3. La conversación debe seguir siendo determinista y explícitamente activada. El router usa coincidencias de palabras/frases completas y contempla variantes habituales con acentos.
4. El runtime social ya usa el director, el repertorio y las rutinas horarias, pero todavía necesita más categorías y escenas específicas para que las intervenciones espontáneas tengan mayor variedad.
5. Ciudad Animals registra escenas usadas, intención y ámbitos de usuario/chat. La atribución de escenas de seguimiento se hace sobre el personaje que realmente habla y existe una prueba dedicada para protegerla.
6. Las rutinas usan `Settings.bot_world_timezone` y convierten UTC a una zona IANA explícita (`America/Argentina/Buenos_Aires` por defecto). `tzdata` queda declarado para portabilidad de la base horaria en Windows.
7. El cierre de sesión de `Database.session()` ahora establece explícitamente el límite transaccional: commit al completar el bloque y rollback ante excepciones. Esto es necesario para que observaciones del mundo y otros cambios sean visibles en sesiones posteriores.
8. Café Otaku y las rutinas del mundo siguen siendo funcionalidad parcial: faltan objetos, servicios, economía, personajes secundarios y eventos conectados a esas rutinas.
9. La base de comportamiento de maids/tiendas y la base de metadatos de anime son actualmente documentación de referencia; todavía no están convertidas en un catálogo de datos consultable por Cami/Cari.
10. La futura interfaz de Tío Otaku debe tratarlo como operador humano: el sistema recibe/muestra/envía mensajes, pero no debe sustituir su redacción manual por IA por defecto.
11. Se requieren auditorías posteriores para verificar que nuevos juegos o sistemas no desplacen el objetivo principal: personajes y mundo vivos sin dependencia continua de IA.
12. Las pruebas deben seguir protegiendo la voz específica de Sunna, Cami y Chie frente a expansiones futuras del repertorio.

## Evidencia externa utilizada

### Telegram / aiogram

La documentación actual de aiogram mantiene el enfoque de `Router`, middlewares, filtros y dependencia de contexto, que encaja con la composición modular existente del proyecto. La API oficial de Telegram expone diferentes tipos de updates y requisitos de permisos que deben comprobarse antes de ampliar moderación o coordinación.

### Persistencia / concurrencia

La documentación actual de SQLAlchemy 2.0 confirma que `AsyncSession` es mutable y no debe compartirse entre tareas concurrentes; el modelo correcto es una sesión por tarea concurrente. El proyecto usa sesiones creadas por operación y ahora define un límite transaccional explícito en `Database.session()`.

### Tiempo del mundo

Python `zoneinfo` implementa zonas IANA y puede usar datos del sistema o `tzdata`. El proyecto declara `tzdata` para que la planificación de Ciudad Animals no dependa de que Windows tenga instalada una base horaria del sistema.

### IA opcional

Ollama soporta chat y salidas estructuradas, lo que permite una futura IA curadora que entregue propuestas validables. Esto no cambia la decisión arquitectónica: para Bot-IA la IA sigue siendo opcional y no el cerebro permanente.

### Fuentes de metadatos de anime

Wikidata ofrece datos estructurados reutilizables bajo CC0 y relaciones entre entidades. Jikan ofrece una API comunitaria no oficial que obtiene datos públicos de MyAnimeList y expone recursos para obras, búsqueda, personajes, episodios y estadísticas. El proyecto debe importar/normalizar estos datos a un catálogo local en vez de consultar la web en cada conversación. 

## Comparación de proyectos

Se revisaron proyectos públicos relacionados con aiogram y bots modulares para contrastar separación de handlers, servicios, persistencia, configuración y middleware. El hallazgo útil no es copiar una plantilla: es confirmar que esa separación reduce acoplamiento y facilita pruebas. Bot-IA añade una capa de dominio particular: personalidad, repertorio, mundo y comportamiento authored-only.

## Nuevas bases documentales

`docs/reference/MAID_BEHAVIOR_BASE.md` contiene una taxonomía inicial de actuación para maids, personal de café y tiendas japonesas, incluyendo protocolos, microacciones y reglas contra la invención de productos.

`docs/reference/ANIME_METADATA_BASE.md` define el esquema local para obras, personajes, procedencia y resúmenes originales breves. Los textos de wikis no se copian como contenido propio; se usan datos estructurados y fuentes de referencia para construir fichas locales.

`docs/reference/TIO_OTAKU_OPERATOR.md` fija el concepto de Tío Otaku como operador humano: Telegram es el transporte, el sistema proporciona la interfaz y herramientas, y la decisión/redacción pertenecen al operador.

## Verificación técnica reciente

La ejecución `35007258984` falló inicialmente en dos pruebas de atribución: la comparación de `BotIdentity.CARI` estaba corregida, pero las filas no eran visibles porque el contexto de `Database.session()` no hacía commit al salir. El análisis de logs mostró `172 passed, 2 failed` y localizó ambas fallas en `test_chat_world_attribution.py`.

El cambio de sesión transaccional y la prueba de persistencia entre sesiones quedaron implementados en `f0d9ae2ccf85998490bf8108ec598a5a6422642a` y `543c2c933c81de3d7b7397ccc5a71f0bc7413275`, respectivamente. No se marca CI verde hasta observar una ejecución posterior que pase realmente.

Los builds de Windows `35010256095` y `35010289685` terminaron correctamente, incluyendo pruebas nativas de media, compilación de ejecutables, smoke test de BotManager, instalador, portable, checksums y artefactos.

## Trabajo actual

La capa de personajes está conectada al runtime mediante intenciones explícitas, director determinista, repertorio y rutinas. Las escenas de seguimiento quedan registradas bajo el personaje que realmente emitió el texto.

El runtime social usa hora mundial configurable y texto authored-only para sus intervenciones locales.

La persistencia de observaciones de mundo ahora tiene un límite transaccional explícito en el gateway de base de datos. Esto corrige un hueco real descubierto por CI y queda protegido por una prueba que verifica visibilidad de la observación desde una sesión posterior.

La siguiente fase prioritaria sigue siendo convertir las bases documentales en datos de dominio consultables, ampliar el repertorio y construir el comportamiento del Café Otaku/ Ciudad Animals alrededor de horarios, acontecimientos, objetos, relaciones y estados, manteniendo Tío Otaku como operador humano y la IA como componente opcional.
