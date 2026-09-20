# Bitácora maestra de desarrollo

Última actualización: 2026-09-20.

## Objetivo
Evitar repetir auditorías y cambios ya realizados. Actualizar este archivo al cerrar cada bloque importante.

## Estado actual
- Arquitectura Core y separación determinista/Brain: endurecida.
- Persistencia SQLite, WAL, transacciones y leases: endurecida.
- Seguridad Telegram y allowlist fail-closed: endurecida.
- BotManager y distribución Windows: empaquetado reproducible.
- WaifuMon: captura, colección, progresión, fusión, gacha y trivia con idempotencia.
- Misterios del Café Otaku: motor diario determinista con ganador único y casos cotidianos no violentos.
- Ciudad Animals: catálogo persistente y observación agregada; el catálogo base se siembra al arrancar ChatModule.
- Catálogo de waifus: 78 personajes jugables con popularidad, poder, rareza, carta R/SR/UR y elemento.
- Contenido narrativo y expansión de personajes: sigue siendo el área de mayor trabajo pendiente.

## Trabajo técnico ya auditado
- TaskSupervisor: corregida carrera de callbacks entre tarea vieja y tarea nueva.
- EventBus y JobQueue: recuperación stale con fencing por identificadores de lease.
- MemberSync: touch y set_membership pueden unirse a transacciones del llamador.
- RequestService: eliminados commits y rollbacks internos incompatibles con la frontera transaccional externa.
- Puntos: referencias únicas para idempotencia.
- Gacha: ledger persistente y claim de recompensa de un solo uso.
- Rare drops: transición pending a approved/rejected de un solo uso.
- Wild encounters: expiración y limpieza de stale rows con updates condicionados.
- Trivia: retiro de rondas expiradas y claim ganador condicional.
- Cami Publisher: claims atómicos para evitar doble envío.
- Clock: UTC centralizado y conversiones local/UTC explícitas.

## Seguridad
- ChatAccessMiddleware corta updates no autorizados antes de MemberSync.
- Los callbacks privados usan callback.from_user como actor real.
- WildWaifu, Trivia y Cami Publisher comprueban la allowlist antes de envíos de fondo.
- Los chats privados administrativos exigen ADMIN_USER_ID.
- Los tokens por identidad permanecen separados.

## Errores encontrados y resueltos
1. Un test de callback privado falló porque el middleware usaba el autor del Message y no el usuario que pulsó el callback. Se corrigió el orden de resolución del actor.
2. El test concurrente de Cami usando SQLite en memoria no representaba dos sesiones reales. Se cambió a un archivo temporal.
3. Ruff detectó un import sobrante de select en rare approval. Eliminado.
4. CI detectó un literal JSON mal escapado en el test de Trivia. Corregido.
5. CI detectó imports incompletos en el test de tiempo. Corregidos.
6. CI detectó que el fixture de Cami no autorizaba el chat después de endurecer el publisher. Corregido.
7. El test de seguridad inicialmente no coincidía con el objeto CallbackQuery usado por el middleware. Corregido y validado.

## Evidencia de pipelines
- CI #663: SUCCESS sobre 75ba43c2ca93d5c6836dd64d95ef7cf054dd2a3a.
- Windows #304: SUCCESS sobre el mismo SHA; verificó ejecutables, smoke test, instalador, portable y checksums.
- CI #673: SUCCESS sobre c13da70731d18bdd71533e0e03982d58d58e2e91.
- Windows #314: SUCCESS sobre c13da70731d18bdd71533e0e03982d58d58e2e91; publicó los artefactos de installer y portable.
- Los cambios posteriores a c13da707 pertenecen a este ciclo y deben quedar validados por sus pipelines antes de una etiqueta de release.

## Catálogo de waifus
- Ranker, snapshot 2026-07-15: posiciones 1-60 del listado de anime girls.
- Anime Corner, ranking anual 2025 publicado 2026-03-05: entradas recientes añadidas cuando no estaban duplicadas y Anya Forger.
- Taiga se conserva como personaje original inicial y está marcada como pendiente de ranking externo.
- Popularidad: 0-100 normalizada desde la posición de la fuente.
- Poder: 0-100 como balance local.
- Rareza: D-SSS derivada del poder.
- Carta: R/SR/UR derivada de popularidad + poder.
- Elemento: independiente del ranking.
- No tratar power_score como poder canónico ni popularity_score como porcentaje universal.

## Misterios
Casos previos: cuchara, libro, campanita, carta de juego, aviso.
Casos añadidos: porción de pastel, cargador cambiado, teléfono usado, batería consumida, auricular perdido, cable hecho nudo, control remoto en heladera, azúcar guardada, marcador de manga y notificación nocturna.
Todos tienen cuatro opciones y respuesta determinista. Las pruebas verifican que no se introduzca lenguaje de asesinato/muerte.

## No rehacer
No volver a implementar desde cero SQLite/WAL/transacciones, leases de workers, RequestService idempotente, allowlist Telegram, claims de Cami, captura/gacha/trivia/mystery idempotentes ni el empaquetado Windows base. Revisar primero sus pruebas y este archivo.

## Pendiente prioritario
1. Expandir escenas, eventos y relaciones de Ciudad Animals.
2. Completar repertorio de las cuatro identidades sin reducirlas a frases repetitivas.
3. Añadir buscador y paginación del catálogo de waifus con filtros por elemento/carta/rareza.
4. Añadir más fuentes de popularidad e importador offline reproducible.
5. Integrar más acciones reales de Cami y Chie al WorldService.
6. Mejorar arte por personaje y evolución.
7. Añadir paneles de ranking, colección y estadísticas.
8. Curador IA opcional con aprobación humana antes de modificar canon.

## Regla de cierre
Un bloque solo se considera terminado cuando el cambio está en GitHub, tiene pruebas, Ruff/Pytest pasan, Windows pasa cuando corresponde, el SHA queda anotado y los errores encontrados quedan documentados.
