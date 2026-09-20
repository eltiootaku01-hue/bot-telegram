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
- Misterios del Café Otaku: motor diario determinista con ganador único y 15+ casos cotidianos no violentos.
- Ciudad Animals: catálogo persistente y observación agregada; el catálogo base se siembra al arrancar ChatModule.
- Catálogo de waifus: 78 personajes jugables en esta etapa, con dos ejes separados de popularidad y poder, rareza D-SSS, carta R/SR/UR y elemento.
- Navegación del catálogo: comando /waifus y paginación desde el panel de Sunna.
- Compatibilidad histórica: IDs antiguos conocidos se resuelven en lectura sin migración destructiva.
- Contenido narrativo y expansión de personajes: sigue siendo el área de mayor trabajo pendiente.

## Trabajo técnico ya auditado
- TaskSupervisor: corregida carrera de callbacks entre tarea vieja y tarea nueva.
- EventBus y JobQueue: recuperación stale con fencing por identificadores de lease.
- MemberSync: touch y set_membership pueden unirse a transacciones del llamador.
- RequestService: eliminados commits y rollbacks internos incompatibles con la frontera transaccional externa.
- Puntos: referencias únicas para idempotencia y protección ante reintentos concurrentes.
- Gacha: ledger persistente, claim de recompensa único y referencias de tirada.
- Rare drops: transición pending -> approved/rejected de un solo uso.
- Wild encounters: expiración, limpieza stale y protección contra sobrescritura de estados terminales.
- Trivia: retiro de rondas vencidas, claim ganador condicional y servicio componible.
- Cami Publisher: claims atómicos para evitar doble envío.
- Clock: UTC centralizado y conversiones local/UTC explícitas.
- WorldService: observaciones agregadas sin depender de texto crudo.
- World Catalog: lugares, roles, acciones y relaciones documentadas como elementos catalogables.
- Seguridad de segundo plano: WildWaifu, Trivia y Cami Publisher validan la comunidad autorizada antes de enviar.

## Errores encontrados y resueltos en este ciclo
1. Un test de callback privado falló porque el middleware usaba el autor del Message y no el usuario que pulsó el callback. Se corrigió el orden de resolución del actor.
2. El test concurrente de Cami usando SQLite en memoria no representaba dos sesiones reales. Se cambió a un archivo temporal.
3. Ruff detectó un import sobrante de select en rare approval. Eliminado.
4. CI detectó un literal JSON mal escapado en el test de Trivia. Corregido.
5. CI detectó imports incompletos en el test de tiempo. Corregidos.
6. CI detectó que el fixture de Cami no autorizaba el chat después de endurecer el publisher. Corregido.
7. CI detectó sintaxis rota en la primera generación del navegador de waifus porque el escape de "\n" quedó partido. Se corrigió.
8. CI detectó que los tests históricos de gacha suponían que Taiga era la única carta B. Se actualizaron para aceptar el catálogo ampliado.
9. CI detectó que el ID de Anya debía conservar "anya" para compatibilidad con colecciones existentes. Se añadió normalización explícita y el objeto Character mantiene ahora el ID canónico.
10. CI detectó que el test de misterios no contemplaba "azúcar" entre los términos cotidianos. Se corrigió el test.
11. La actualización de CI y Windows canceló ejecuciones intermedias al llegar nuevos commits; solo la ejecución del SHA final debe considerarse evidencia de cierre.
12. Una edición de CIUDAD_ANIMALS_WORLD.md fue bloqueada por el control de la herramienta; no hubo escritura parcial. El estado correcto quedó registrado en esta bitácora.

## Evidencia histórica de pipelines
- CI #663: SUCCESS sobre 75ba43c2ca93d5c6836dd64d95ef7cf054dd2a3a.
- Windows #304: SUCCESS sobre el mismo SHA; verificó ejecutables, smoke test, instalador, portable y checksums.
- CI #673: SUCCESS sobre c13da70731d18bdd71533e0e03982d58d58e2e91.
- Windows #314: SUCCESS sobre el mismo SHA; publicó installer y portable.
- Los pipelines intermedios de este ciclo pueden aparecer como cancelled por la política de concurrencia de GitHub Actions y no deben contarse como fallo funcional.

## Catálogo de waifus
- Fuente principal de popularidad histórica del snapshot: Ranker, actualización 2026-07-15, posiciones 1-60 visibles.
- Fuente adicional: Anime Corner, ranking anual 2025 publicado 2026-03-05, entradas recientes no duplicadas y Anya Forger.
- Taiga se conserva como personaje inicial del proyecto y queda marcada como pendiente de ranking externo.
- Popularidad: escala normalizada 0-100 desde ranking de fuente.
- Poder: escala local 0-100 de balance; no es poder canónico.
- Rareza: D/C/B/A/S/SS/SSS derivada solo del poder.
- Carta: R/SR/UR derivada de popularidad + poder.
- Elemento: independiente de popularidad y poder.
- No usar popularity_score como porcentaje universal ni power_score como afirmación de canon.
- Los rankings pueden cambiar; los snapshots deben conservar fecha y fuente.

## Misterios
Casos iniciales: cuchara, libro, campanita, carta de juego, aviso.
Casos añadidos: porción de pastel, cargador cambiado, teléfono usado, batería consumida, auricular perdido, cable hecho nudo, control remoto en heladera, azúcar guardada, marcador de manga y notificación nocturna.
Regla: misterios de observación cotidiana, sin asesinatos ni muertes. Respuesta determinista, cuatro opciones, un ganador y recompensa idempotente.

## No rehacer
No volver a implementar desde cero:
- SQLite/WAL/transacciones;
- TaskSupervisor;
- durable workers/leases;
- RequestService idempotente;
- allowlist Telegram;
- claims de Cami;
- captura/gacha/trivia/mystery idempotentes;
- empaquetado Windows base.

Antes de tocar una de estas áreas, revisar sus pruebas y este archivo.

## Pendiente prioritario
1. Expandir escenas, eventos y relaciones de Ciudad Animals con estados explícitos de canon/no canon.
2. Completar el repertorio de las cuatro identidades sin reducir sus voces a frases repetitivas.
3. Añadir filtros del catálogo de waifus por elemento, carta, rareza y fuente, además de la paginación existente.
4. Añadir más fuentes de popularidad y un importador offline reproducible por snapshot.
5. Integrar más acciones reales de Cami y Chie al WorldService.
6. Mejorar arte por personaje y evolución.
7. Añadir ranking, colección y estadísticas del mundo con paneles dedicados.
8. Curador IA opcional con aprobación humana antes de modificar canon.

## Regla de cierre
Un bloque solo se considera terminado cuando:
- el cambio está en GitHub;
- los tests correspondientes existen;
- Ruff/Pytest pasan;
- Windows pasa cuando el cambio toca empaquetado/runtime Windows;
- el SHA final queda anotado aquí;
- los errores encontrados quedan documentados.
