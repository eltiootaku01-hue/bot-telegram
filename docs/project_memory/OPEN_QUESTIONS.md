# Project Memory — Open Questions

## Compatibilidad Task Contract / TaskEngine

- Estado: [UNKNOWN]
- Pregunta: ¿Cuál será el adapter exacto entre el contrato Supervisor y las reglas operativas del TaskEngine existente?
- Evidencia disponible: ambos modelos fueron inspeccionados.
- Restricción: no modificar TaskEngine durante FASE 2F-3.

## Persistencia de Tasks

- Estado: [UNKNOWN]
- Pregunta: ¿Debe el contrato de tarea adquirir persistencia propia posteriormente?
- Conocido: FASE 2F-3 usa memoria en proceso.

## Enforcement físico de Scope Lock

- Estado: [UNKNOWN]
- La referencia contractual existe; el enforcement físico sigue abierto.

## Autoridad física de escritura

- Estado: [UNKNOWN]
- Continúa abierta y fuera de FASE 2F-3.

## Integración Supervisor → TaskEngine

- Estado: [TESTED]
- FASE 2F-6 implementa únicamente una frontera read-only/contractual `TaskEngineBoundary`.
- [UNKNOWN] No se definió todavía la interfaz futura que entregará solicitudes ALLOWED al lifecycle operacional.

## Integración Supervisor → Scheduler

- Estado: [TESTED]
- FASE 2F-6 puede observar pending/active IDs del Scheduler existente y verifica que comparte la misma instancia de TaskEngine.
- [UNKNOWN] No se implementó entrega de comandos ni selección desde Supervisor.

## Conflictos entre Claims

- Estado: [UNKNOWN]
- No existe estado CONFLICT formal en Claims.

## Integración con AuthorityCore

- Estado: [UNKNOWN]
- Pregunta: ¿Cómo debe adaptarse `AuthorityCore` existente a la autoridad contractual del Supervisor?
- Conocido: `src/bot_ia/security/authority.py` sigue intacto y su alcance actual es identidad/destino/permiso de interfaces remotas.

## Persistencia y auditoría

- Estado: [UNKNOWN]
- Pregunta: ¿Cómo se persistirá y auditará Authorization a través de reinicios o procesos?
- Conocido: FASE 2F-4 no implementa almacenamiento ni revocación persistente.


## Persistencia de Hypothesis/Repair

- Estado: [UNKNOWN]
- Pregunta: ¿Debe Hypothesis/Repair persistirse en el mismo almacenamiento JSONL existente o mediante otra capa futura?
- Conocido: FASE 2F-5 solo mantiene historial contractual de intentos en memoria y no añade una base de datos.
- [UNKNOWN] Auditoría y reconciliación de Hypothesis/Repair entre reinicios/procesos.

## FASE 2F-6 — Boundary operativo

- [UNKNOWN] El mecanismo definitivo para convertir una solicitud contractual aceptada en una llamada operacional al TaskEngine no se implementa todavía.
- [UNKNOWN] La semántica final de BLOCK/REQUEST/CANCEL_REQUEST entre Supervisor y TaskEngine queda pendiente de una futura fase controlada.
- [DECIDED] Esta incertidumbre no justifica modificar TaskEngine ni TaskScheduler en FASE 2F-6.


## FASE 2F-7 — Runtime Observation

- [TESTED] El Supervisor puede observar snapshots del TaskEngine y pending/active IDs del Scheduler sin mutarlos.
- [TESTED] task_id permanece estable en los snapshots observados, incluyendo parent/child.
- [UNKNOWN] No existe todavía una interfaz de handoff operacional desde una decisión contractual ALLOWED hacia TaskEngine/Scheduler.
- [UNKNOWN] No existe todavía autoridad física definida para ejecución desde Supervisor.
- [UNKNOWN] Las transiciones que no están expuestas por el runtime actual no deben inferirse ni fabricarse.


- [TESTED] El escenario WAITING/RESUME requiere respetar la propiedad operacional existente de active registration; no implica una nueva autoridad para Supervisor.


## FASE 2F-8R — Runtime transition causality

- Estado: [UNKNOWN]
- La diferencia entre snapshots puede observarse, pero no existe todavía un mecanismo independiente que pruebe causalidad de una transición.
- Restricción: no convertir RuntimeObservation en executor ni crear una segunda state machine.

## FASE 2F-8R — ScopeLock immutability

- Estado: [TESTED]
- ScopeLock quedó frozen después de creación.
- [UNKNOWN] El enforcement físico del ScopeLock continúa sin implementarse.


## FASE 2F-8A — F-006 Ownership

- Estado: [CONFLICT]
- `TaskScheduler` no es scheduler global; su ownership queda limitado al runtime `TaskEngine` al que está asociado.
- `GUI TaskOrchestrator` no es legacy/no-activo: tiene instanciación y uso operativo comprobables.
- Ambos caminos realizan trabajo WebChat, pero no comparten Task Contract, `task_id`, `session_id` ni instancia de WebQueue.
- Pregunta pendiente: ¿debe existir una futura convergencia arquitectónica entre el quick-action async de GUI y el runtime TaskEngine/Scheduler? Esta fase no toma esa decisión.

## FASE 2F-8A — Task Contract reconciliation

- Estado: [UNKNOWN]
- No existe reconciliación automática demostrada entre `TaskContractStore` y `TaskEngine`.
- El contrato puede aceptar un `task_id` suministrado, pero no verifica contra el registro interno del TaskEngine ni mantiene un vínculo automático con él.

## FASE 2F-8A — Supervisor handoff

- Estado: [UNKNOWN]
- Existe `REQUEST`, `CANCEL_REQUEST`, `ALLOWED` y `BLOCKED` como contrato de `TaskEngineBoundary`.
- No existe handoff operativo Supervisor → TaskEngine/TaskScheduler demostrado: `ALLOWED` termina en una decisión contractual y declara explícitamente que la ejecución permanece externa.

## FASE 2F-8A — AuthorityCore adapter

- Estado: [UNKNOWN]
- No se encontró adapter/validator integrado entre `AuthorityCore` y `WriteAuthorization`; el contrato del Supervisor sólo acepta un validador independiente abstracto.


## FASE 2F-8B — Estado posterior a la decisión

- F-006: [DECIDED — CANDIDATO A]
- Arquitectura objetivo WebChat: `GUI → TaskEngine → TaskScheduler → WebChatQueueManager`.
- TaskOrchestrator actual: [ACTIVE / MIGRATION PENDING], no legacy.
- Adapter futuro o retirada gradual de TaskOrchestrator: [PROPOSED]
- Migración de quick actions a TaskEngine/Scheduler: [PROPOSED]
- Identidad futura de quick actions: [PROPOSED] reutilizar `TaskEngine.task_id`, sin inventar una segunda identidad.
- Recurso futuro común: [PROPOSED] `WEB_MESA_UNICA` bajo el único WebChat executor; requiere diseño/implementación posterior.
- Misma cuenta/browser/session entre los dos caminos actuales: [UNKNOWN]
- Enforcement físico de Authorization/ScopeLock: [UNKNOWN]
- Supervisor → execution handoff: [UNKNOWN]

La decisión arquitectónica no autoriza implementación ni inicia FASE 2F-9.


## FASE 2F-8C — Migration blockers / open questions

### Capability parity

- [BLOCKER / UNKNOWN] ¿Qué capacidades concretas del Playwright WebQueueManager son required para quick actions y no están demostradas en QWebEngine/QWebChannel/MutationObserver?
- [UNKNOWN] ¿Debe conservarse la semántica de seis páginas por waitress o basta la arbitraje de una única superficie WebChat?
- [UNKNOWN] ¿Cómo se preservarán interaction counters y el soft reset cada 20 interacciones si la arquitectura objetivo mantiene una sola superficie?
- [UNKNOWN] ¿Los timeouts de respuesta, navegación y page operation del runtime Playwright tienen equivalentes funcionales en el protocolo Qt actual?
- [UNKNOWN] ¿Existe alguna dependencia de storage_state/IndexedDB del Playwright que no esté cubierta por el QWebEngineProfile persistente?

### Identity / lifecycle

- [DECIDED] El futuro quick-action WebChat debe tener un task_id generado por TaskEngine.
- [UNKNOWN] ¿Qué metadata mínima debe convertirse en Task.context para conservar target waitress, payload, acción y datos de presentación sin introducir una identidad nueva?
- [UNKNOWN] ¿Debe una quick action que no usa WaitressSessionManager continuar sin session_id? La evidencia actual indica que sí; no se debe fabricar una sesión.
- [UNKNOWN] ¿Qué política de deadline debe usar TaskEngine para sustituir el timeout global de 12 s del TaskOrchestrator sin duplicar el timeout físico de WebChatQueueManager?

### Cancellation / failure / fallback

- [UNKNOWN] ¿La GUI necesitará un control explícito de cancelación para quick actions o sólo cancelación por shutdown/parent task?
- [UNKNOWN] ¿Qué fallos deben terminar en FAILED y cuáles deben producir una respuesta fallback sin marcar la operación física como fallida?
- [UNKNOWN] Si una política futura agrega retry real, ¿debe representarse como el mismo task lifecycle o como child task? No se permite decidirlo implícitamente dentro de un executor.
- [UNKNOWN] ¿Qué parte del CircuitBreaker por waitress del TaskOrchestrator, si alguna, expresa una política diferente del breaker físico de WebChatQueueManager?

### Temporal compatibility

- [UNKNOWN] ¿El routing switch de migración será una feature flag, adapter explícito o configuración de modo? La decisión queda para MIG-1.
- [DECIDED] No se permite que el modo de compatibilidad ejecute ambas rutas para una misma solicitud.
- [UNKNOWN] ¿Cuándo puede declararse el antiguo Playwright runtime sin consumidores operativos y por tanto elegible para archival/removal?

### Supervisor compatibility

- [UNKNOWN] ¿Cuál será el handoff físico exacto desde una decisión contractual ALLOWED hacia TaskEngine/Scheduler?
- [UNKNOWN] ¿Dónde se materializará el binding físico de Authorization y ScopeLock antes de ejecutar una quick action?
- [DECIDED] RuntimeObservation seguirá siendo read-only; no se convertirá en dispatcher.
- [UNKNOWN] ¿Qué evidencia runtime deberá demostrar que el nuevo quick-action path realmente pasó por TaskEngine/Scheduler y por `WEB_MESA_UNICA`?

### Migration safety

- [DECIDED] No se copian cookies, perfiles, credenciales ni storage_state durante la migración.
- [DECIDED] No se crean un segundo Scheduler, TaskEngine, WebChat executor ni cola operacional paralela.
- [UNKNOWN] ¿Qué prueba de idempotencia demostrará que un routing switch no puede reenviar una solicitud ya aceptada?
- [UNKNOWN] ¿Qué rollback preservará una sesión QWebEngine autenticada sin reactivar simultáneamente el Playwright runtime?


## FASE 2F-8D — MIG-0 Gates

### New UNKNOWNs

- [UNKNOWN] ¿Qué matriz de providers y respuestas reales es necesaria para cerrar MIG-3-G01..G05?
- [UNKNOWN] ¿Qué mecanismo futuro reemplazará interaction_counters y soft_reset_page sin perder el comportamiento requerido?
- [UNKNOWN] ¿Cuál será la precedencia exacta entre TaskEngine deadline y timeout físico de WebChatQueueManager?
- [UNKNOWN] ¿Qué parte del fallback de trivia es presentación y qué parte, si alguna, debería convertirse en política de lifecycle?
- [UNKNOWN] ¿Cómo se demostrará una sola ruta por solicitud durante la transición sin shadow execution?

### Confirmed blockers

- [BLOCKER] Quick actions WebChat actuales no usan TaskScheduler ni WEB_MESA_UNICA.
- [BLOCKER] Login/storage continuity entre Playwright y QWebEngine no está demostrada.
- [BLOCKER] MIG-3 requiere runtime/provider evidence; MIG-0 no la ejecuta.
- [CONFIRMED RISK] callback de quick action depende de _selected_bot_id mutable.
