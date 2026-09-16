# Auditoría viva del proyecto

Fecha de referencia: 2026-09-16

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
| Canon y perfiles de personajes | 72% |
| Director determinista | 60% |
| Repertorio escrito | 47% |
| Router determinista de intenciones | 50% |
| Rutinas y horarios | 52% |
| Interacciones entre personajes | 29% |
| Café Otaku | 23% |
| Ciudad Animals | 35% |
| Estadísticas del mundo | 40% |
| Registro automático de uso de escenas | 50% |
| IA como curadora periódica | 20% |
| Juegos nuevos (misterios, cartas, etc.) | 10% |
| GUI completa de edición | 20% |
| Base documental anime/maid | 18% |
| Operador humano Tío Otaku | 15% |

## Riesgos activos detectados por auditoría

1. Cari y Cami ya están ancladas a lore del autor, pero Sunna y Chie todavía necesitan biblias equivalentes antes de recibir rasgos psicológicos profundos en el modelo.
2. El repertorio sigue creciendo, pero todavía está lejos del volumen necesario para que los cuatro personajes tengan una vida de NPC amplia y sostenible.
3. La conversación debe seguir siendo determinista y explícitamente activada. El router usa coincidencias de palabras/frases completas y contempla variantes habituales con acentos.
4. El runtime social usa director, repertorio y rutinas horarias, pero todavía necesita más categorías y escenas específicas para producir intervenciones espontáneas variadas.
5. Ciudad Animals registra escenas usadas, intención y ámbitos de usuario/chat. Las escenas de seguimiento quedan atribuidas al personaje que realmente habla.
6. Las rutinas usan `Settings.bot_world_timezone` y convierten UTC a zona IANA. `tzdata` queda declarado para portabilidad de la base horaria en Windows.
7. El cierre de sesión de `Database.session()` establece explícitamente el límite transaccional: commit al completar el bloque y rollback ante excepciones. Esto corrige el hueco detectado por CI.
8. Café Otaku y las rutinas del mundo siguen siendo funcionalidad parcial: faltan objetos, servicios, economía, personajes secundarios y eventos conectados a esas rutinas.
9. La base de comportamiento de maids/tiendas y la base de metadatos de anime son actualmente documentación de referencia; todavía no están convertidas en un catálogo de datos consultable por Cami/Cari.
10. Tío Otaku debe mantenerse como operador humano: el sistema transporta, muestra y registra; la decisión y redacción final pertenecen al operador y la IA no es obligatoria.
11. La bibliotecaria y las capas de conocimiento deben distinguir entre canon del autor, datos externos normalizados, planificación y propuestas.
12. Las pruebas deben seguir protegiendo la voz específica de Sunna, Cami y Chie frente a expansiones futuras del repertorio.
13. CI no se considera verde solo por una corrección local: cada cambio debe tener una ejecución posterior concluida con éxito.
14. La trivia tenía llamadas directas a `datetime.utcnow()` y defaults de modelo basados en ese reloj, fuera de la abstracción temporal central. Esto se corrigió para usar `app.core.time.utc_now()`, manteniendo el almacenamiento UTC-naive coherente con el resto de la plataforma.
15. La auditoría de solicitudes detectó una segunda frontera transaccional que debe vigilarse: `RequestService.create_paid()` hace `commit()` y `rollback()` internos aunque el llamador usa `Database.session()` como frontera transaccional. Esto funciona en el flujo actual, pero reduce la composabilidad del servicio y puede confirmar o deshacer trabajo ajeno si el mismo `AsyncSession` se reutiliza. SQLAlchemy recomienda una `AsyncSession` por tarea y una transacción claramente delimitada; la siguiente corrección debe preservar la atomicidad del cobro y de la solicitud sin romper la frontera superior.
16. `FanRequest` y `PointTransaction` tienen restricciones únicas y el servicio ya intenta resolver carreras de mensajes duplicados mediante `source_message_id` y referencias de puntos. Falta una prueba de integración que ejerza explícitamente dos intentos concurrentes y compruebe que solo uno cobra y crea la solicitud.

## Canon de personajes incorporado

### Cari

`docs/characters/CARI_CANON_PERSONALITY.md` resume material del autor y separa identidad narrativa, motivación, miedo, virtudes, defectos, Berserker, relaciones y evolución. Su rol de anfitriona del Café Otaku es una función operativa y no sustituye su papel de protagonista.

### Cami

`docs/characters/CAMI_CANON_PERSONALITY.md` resume material del autor y define a Cami como coprotagonista y hermana de Cari, estratega introvertida y observadora cuya filosofía es comprender para proteger. Se incorporaron al perfil estructurado su motivación, miedo central y tema de arco, preservando su diferencia respecto de Cari.

No se completaron artificialmente estos campos para Sunna o Chie porque todavía no existe material canónico equivalente en el repositorio.

## Base documental de referencia

`docs/reference/MAID_BEHAVIOR_BASE.md` contiene una taxonomía inicial de actuación para maids, personal de café y tiendas japonesas, incluyendo protocolos, microacciones y reglas contra la invención de productos.

`docs/reference/ANIME_METADATA_BASE.md` define el esquema local para obras, personajes, procedencia y resúmenes originales breves. Los textos de wikis no se copian como contenido propio.

`docs/reference/TIO_OTAKU_OPERATOR.md` fija el concepto de Tío Otaku como operador humano.

## Evidencia externa utilizada

### Telegram / aiogram

La documentación oficial de aiogram mantiene el enfoque de `Router`, middlewares, filtros y contexto, compatible con la composición modular existente. La API oficial de Telegram expone diferentes tipos de updates y requisitos de permisos que deben comprobarse antes de ampliar moderación o coordinación.

### Persistencia / concurrencia

La documentación actual de SQLAlchemy 2.1 confirma que `AsyncSession` es mutable y no debe compartirse entre tareas concurrentes; el patrón recomendado es una sesión por tarea y una transacción por unidad de trabajo. Esta regla se usa ahora como criterio explícito de auditoría para servicios que reciben una sesión desde `Database.session()`.

### Tiempo del mundo

Python `zoneinfo` implementa zonas IANA y puede usar datos del sistema o `tzdata`. El proyecto valida la zona configurada y declara `tzdata` para reproducibilidad en Windows. La auditoría del 16-09-2026 extendió esta regla a Trivia, eliminando el uso directo de `datetime.utcnow()` en el servicio y sus modelos.

### GitHub Actions / CI

GitHub documenta que las ejecuciones de Actions pueden ejecutarse concurrentemente por defecto y que `concurrency` permite limitar o cancelar ejecuciones obsoletas. Por ahora no se añade esa configuración por estética: primero se debe comprobar si el patrón real del repositorio genera ejecuciones redundantes o conflictos. El objetivo es que CI siga verificando cada cambio útil sin ocultar fallos ni desperdiciar recursos.

### IA opcional

Ollama soporta actualmente chat y salidas estructuradas, lo que deja abierta una futura IA curadora que entregue propuestas validables. No cambia el principio de que la IA sea opcional y no el cerebro permanente.

### Fuentes de metadatos de anime

Wikidata ofrece datos estructurados reutilizables bajo CC0. Jikan ofrece una API comunitaria no oficial que obtiene datos públicos de MyAnimeList y expone recursos para obras, personajes, episodios y estadísticas. El plan del proyecto es importar y normalizar esos datos localmente, no depender de consultas web durante cada conversación.

### Comparación de proyectos

La comparación de proyectos públicos de aiogram y bots modulares confirma como patrones útiles la separación entre handlers, servicios, persistencia, configuración y middleware. Bot-IA añade una capa de dominio que esas plantillas normalmente no contienen: personajes, repertorio authored-only, mundo y operador humano.

## Verificación técnica reciente

- CI `35008731690`: `172 passed, 2 failed`. Ruff pasó; las dos fallas estaban en `test_chat_world_attribution.py`. El análisis identificó que el contexto `Database.session()` no hacía commit al completar el bloque.
- Se corrigió `Database.session()` para commit/rollback y se añadió una prueba de persistencia entre sesiones.
- La comparación incorrecta con `BotIdentity.CARI` también quedó corregida para usar su valor en el campo persistido.
- Los builds de Windows `35010256095` y `35010289685` terminaron correctamente, incluyendo media, ejecutables, smoke test, instalador, portable, checksums y artefactos.
- CI `35063030974` detectó un contrato incorrecto en una prueba de `ChatModule`: el stub de `message.answer` era síncrono mientras la producción lo espera como coroutine. Se corrigió el test para respetar el contrato real.
- El commit `95e9f2a45feec848a2493dc714e7acb6b5bc7516` disparó un nuevo Windows build (`35103114020`).
- El commit `248255158ea8adb981594e58c8c01db6ee6bf5d2` es actualmente `main`. Para ese commit, Windows build `35103365937` terminó con conclusión `success` el 16-09-2026.
- La última ejecución Linux conocida asociada al commit anterior `44ee28a6e28e9082d6c665dd9b525893d204ca2c` también terminó con éxito. La auditoría no marcará todo el pipeline como verde para el commit `248255...` hasta observar una ejecución Linux posterior específica de ese SHA.

## Trabajo actual

La capa de personajes ya distingue entre canon del autor y comportamiento operativo del Café Otaku. Cari y Cami tienen una base canónica que permite ampliar el repertorio sin reducirlas a caricaturas.

El runtime social usa director, repertorio y rutinas con hora mundial configurable y texto authored-only.

La persistencia de observaciones de mundo tiene una frontera transaccional explícita, operaciones de observación resistentes a carreras y cobertura dedicada. `ChatModule` ya conecta una respuesta authored-only con una observación de mundo persistida.

La auditoría de módulos muestra que WaifuMon/progresión y solicitudes tienen límites transaccionales explícitos en sus flujos actuales, pero solicitudes necesita una corrección posterior para que el servicio no se apropie de la transacción del llamador. La trivia también queda alineada con el reloj central después de la corrección del 16-09-2026. Todavía falta extender de forma deliberada la observación del mundo a eventos de dominio relevantes de juegos, trivia, media y solicitudes; no se añadirá telemetría indiscriminada solo para aumentar estadísticas.

La siguiente fase inmediata es: (1) comprobar el pipeline Linux para el SHA actual, (2) añadir una prueba de concurrencia/idempotencia para solicitudes y puntos, (3) corregir la propiedad de la transacción en `RequestService` sin perder atomicidad, (4) repetir CI Linux + Windows, y (5) continuar con WaifuMon, Trivia y Media bajo el mismo recorrido `Telegram → módulo → servicio de dominio → persistencia → evento/mundo`.

La siguiente fase de producto, después de cerrar esas fronteras, es convertir las bases documentales en datos de dominio consultables, ampliar el repertorio, modelar relaciones/acontecimientos/objetos/estado del Café Otaku y Ciudad Animals, y diseñar la futura interfaz de Tío Otaku como herramienta de operación humana. La IA seguirá siendo opcional.

## Criterio de finalización

No marcar 100% hasta comprobar: personajes completos, repertorio amplio, rutinas, interacciones, Café Otaku, mundo, estadísticas, funcionalidades previstas, base documental, GUI, modo operador humano, pruebas de integración, builds y auditorías repetidas.
