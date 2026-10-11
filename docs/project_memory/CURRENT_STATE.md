# Project Memory — Current State

## Supervisor

- [TESTED] Observation Core: PR #62, validated in Ubuntu/Windows.
- [TESTED] Claims + Evidence linkage + Scope Lock: PR #63, HEAD `cf5a190ca7cdd872ba33554fea3b711f6007e0fb`.
- [TESTED] FASE 2F-3 añade Task Contract + State Machine sin conectar TaskEngine ni Scheduler.
- [DECIDED] El Task Contract es una capa contractual; no es un nuevo executor, scheduler ni TaskEngine.
- [TESTED] Branch de FASE 2F-3: `feature/supervisor-task-contract`.
- [OBSERVED] HEAD base: `2c94915ea51b39c5e514b809cab332a630cefbf0`.

## Task Contract

- [TESTED] Representa task_id, requester, task_type, context, priority, state, timestamps, deadline, timeout_policy, parent_task_id, interrupted_by, return_policy, wait_reason, result, error y metadata.
- [TESTED] También puede referenciar scope_id, claim_ids y evidence_ids sin copiar sus objetos.
- [DECIDED] Prioridades contractuales: HIGH, MEDIUM, LOW.
- [DECIDED] Estados: PENDING, RUNNING, WAITING, INTERRUPTED, CANCELLING, COMPLETED, FAILED, TIMED_OUT, CANCELLED, DISCARDED.
- [DECIDED] Estados terminales: COMPLETED, FAILED, TIMED_OUT, CANCELLED, DISCARDED.
- [TESTED] WAITING exige wait_reason.
- [TESTED] task_id duplicado, parent inexistente, self-parent, parent terminal y ciclos son rechazados.
- [TESTED] Respuestas solo son aceptables para tareas RUNNING/WAITING; tareas terminales y desconocidas se descartan.
- [DECIDED] El resultado de una tarea terminal no puede adjuntarse como resultado válido.

## Compatibilidad pendiente

- [OBSERVED] El TaskEngine existente contiene reglas operativas de ciclo de vida propias.
- [UNKNOWN] El adapter futuro que reconciliará exactamente ambos contratos todavía no está definido.
- [DECIDED] FASE 2F-3 no modifica TaskEngine ni TaskScheduler.

## Fuentes

FASE 2F-2; FASE 2F-3; `src/bot_ia/core/task_engine.py`; `src/bot_ia/core/task_scheduler.py`; PR #63.

## Write Authorization

- [TESTED] FASE 2F-4 añade un contrato separado para autorización de escritura; no ejecuta ninguna escritura.
- [DECIDED] Authorization requiere binding explícito a task_id, scope_id, operation y target.
- [DECIDED] Authorization no puede ampliar ScopeLock: la operación y el target deben pasar el ScopeLock existente.
- [DECIDED] Un registro AUTHORIZED requiere validación independiente de la autoridad; sin validador externo la comprobación es DENIED.
- [DECIDED] Supervisor no puede autoautorizarse cuando requester y authority representan la misma identidad del Supervisor.
- [DECIDED] Authorization es inmutable; una revocación produce un nuevo registro REVOKED.
- [TESTED] Expiración se valida contra current_time sin timers ni mutación.
- [UNKNOWN] La autoridad física definitiva, su autenticación y su integración futura con AuthorityCore continúan abiertas.


## FASE 2F-5

- [TESTED] Se añade un contrato separado de Hypothesis/Repair sin ejecución física.
- [DECIDED] Hypothesis conserva estado propio y no puede usar Confidence.VERIFIED.
- [DECIDED] Supporting evidence y refutation evidence son referencias separadas.
- [DECIDED] RepairProposal permanece separada de Authorization y Execution.
- [DECIDED] RepairAttempt es inmutable y el historial es append-only en memoria.
- [DECIDED] RepairBudget falla cerrado y no permite expansión automática de operaciones o ScopeLock.
- [TESTED] Proposal fuera de ScopeLock queda BLOCKED.
- [TESTED] Intento sin aprobación, sin authorization o fuera de presupuesto queda BLOCKED.
- [UNKNOWN] Persistencia definitiva de Hypothesis/Repair y auditoría entre reinicios siguen abiertas.

## FASE 2F-6

- [OBSERVED] TaskEngine es la autoridad operativa del lifecycle: crea tareas y aplica start, wait, resume, interrupt, cancellation, fail, complete, discard y deadline transitions.
- [OBSERVED] TaskScheduler es la autoridad operacional de scheduling/routing: mantiene pending/active registrations, selecciona candidatos, arbitra recursos y despacha hacia executors.
- [OBSERVED] TaskScheduler recibe un TaskEngine concreto y consulta/muta su lifecycle mediante esa instancia; el Scheduler no constituye un segundo TaskEngine.
- [OBSERVED] WebChat utiliza `WEB_MESA_UNICA` como resource key dentro del Scheduler; Supervisor no accede directamente a WebQueue.
- [OBSERVED] Supervisor `TaskContract` y runtime `TaskEngine.Task` representan información solapada, pero no son el mismo objeto ni tienen idénticas reglas operativas.
- [DECIDED] FASE 2F-6 trata TaskEngine como source of truth operacional y TaskScheduler como source of truth de scheduling; Supervisor conserva únicamente la frontera contractual.
- [TESTED] `TaskEngineBoundary` observa snapshots read-only y puede observar pending/active IDs del Scheduler sin seleccionar ni despachar tareas.
- [TESTED] `TaskEngineBoundary` rechaza task_id desconocido, ScopeLock incompatible, estados terminales para solicitudes operacionales y autorizaciones incompatibles.
- [TESTED] El boundary exige que un Scheduler asociado utilice exactamente la misma instancia de TaskEngine.
- [TESTED] Una solicitud contractual válida no cambia el estado del TaskEngine.
- [DECIDED] `ALLOWED` en el boundary significa "contrato aceptado para una futura frontera"; no significa ejecución física.
- [DECIDED] El adaptador `_AuthorizationTaskView` adapta únicamente identidad/requester/scope para reutilizar `check_authorization`; no duplica el lifecycle de TaskEngine.
- [UNKNOWN] La interfaz futura que entregará una solicitud aceptada al TaskEngine/Scheduler todavía no está definida y no se implementó en esta fase.


## FASE 2F-7 — Runtime Observation

- [OBSERVED] La implementación real de TaskEngine mantiene el lifecycle operacional: creación, start, wait/resume, interrupt, cancellation, failure, completion, discard y deadline checks.
- [OBSERVED] La implementación real de TaskScheduler mantiene pending/active registrations, candidate selection, prioridad, recursos y dispatch hacia executors.
- [TESTED] `TaskEngineBoundary` y `RuntimeObservation` consumen snapshots del runtime y no poseen métodos para mutar TaskEngine/Scheduler.
- [TESTED] Los escenarios de runtime cubren lifecycle normal, WAITING/RESUME, cancellation, failure, timeout, task desconocido, estado terminal, identidad parent/child y observación read-only.
- [TESTED] La evidencia de runtime se representa mediante el `Evidence` existente con `EvidenceType.RUNTIME_EVIDENCE`; no se crea otro EvidenceStore.
- [DECIDED] Runtime Observation queda como capa read-only: observar y registrar evidencia no equivale a ejecutar, despachar ni controlar el Scheduler.
- [UNKNOWN] Las transiciones no soportadas por el runtime actual no se inventan; cualquier futura integración de handoff operacional continúa fuera de alcance.


- [TESTED] CI del HEAD de implementación `5fea2df4a54eddeb8ff0949b5258767bce297712` pasa en Ubuntu y Windows después de corregir el escenario WAITING/RESUME conforme a la propiedad real de TaskScheduler de no despertar una tarea todavía activa.


## FASE 2F-8R — Repair & Re-verification

- [TESTED] F-001 was repaired: RuntimeObservation.transition() now classifies before/after snapshot comparison as OBSERVED, not TESTED, and explicitly records that transition_source is contextual metadata rather than causal proof.
- [TESTED] An adversarial runtime test confirms a caller-supplied transition_source cannot promote a snapshot difference to causal TESTED evidence.
- [TESTED] F-002 was repaired: ScopeLock is now frozen after construction, matching the immutability contract already used by WriteAuthorization.
- [TESTED] Mutation attempts against allowed_paths, allowed_operations and status are rejected.
- [UNKNOWN] Causal transition evidence remains unimplemented; no second state machine or runtime execution was introduced.


## FASE 2F-8A — F-006 Ownership reconciliation

- [OBSERVED] `TaskScheduler` es la autoridad de scheduling dentro del runtime gobernado por `TaskEngine`: pending/active, prioridad, recursos, rutas y dispatch.
- [OBSERVED] `GUI TaskOrchestrator` es un componente operativo propio del runtime asíncrono de GUI: mantiene `asyncio.PriorityQueue`, prioridades HIGH/MEDIUM/LOW, timeout de 12 s, fallback y CircuitBreaker por mesera.
- [OBSERVED] `TaskOrchestrator` recibe un callback de worker y en `_async_main` ese callback es `WebQueueManager.process_task`; no recibe `TaskEngine`, `TaskScheduler`, `Task Contract`, `ScopeLock` ni `Supervisor`.
- [OBSERVED] La GUI mantiene además una ruta independiente `TaskEngine -> TaskScheduler -> WebChatQueueManager` para `gui_chat` y para las sesiones de `WaitressSessionManager`.
- [TESTED] Las pruebas de ownership confirman que ambas rutas están explícitamente separadas en código y que Supervisor no importa ni alcanza directamente `TaskOrchestrator` o WebQueue.
- [CONFLICT] F-006 no es un caso de legacy/no-operativo: ambos componentes están activos. Tampoco es correcto declarar un scheduler global único, porque existen dos mecanismos de scheduling/orchestration operativos en la aplicación GUI.
- [CONFLICT] Ambos caminos pueden realizar trabajo WebChat, pero no comparten `task_id`, `session_id`, Task Contract ni la misma instancia de WebQueue: `TaskOrchestrator` usa el `WebQueueManager` async de `bot_ia.core.web_queue`; el runtime TaskEngine usa `WebChatQueueManager` de `services.web_queue`.
- [DECIDED] F-006 queda clasificado como `CONFLICT — ARCHITECTURAL OWNERSHIP`, no como legacy. La resolución de ownership definitivo entre ambos queda fuera de esta fase; no se fusionan ni se elimina ninguno.


## FASE 2F-8B — Decisión arquitectónica WebChat

### F-006

[DECIDED] El objetivo arquitectónico futuro es **CANDIDATO A — convergencia en TaskEngine/TaskScheduler** para el trabajo WebChat operacional.

La evidencia actual no justifica tratar GUI TaskOrchestrator como runtime WebChat independiente a largo plazo: ambos caminos aceptan la misma identidad lógica de waitress, pero sólo el camino TaskEngine/Scheduler posee identidad operacional `task_id`, lifecycle común, resource arbitration y boundary observable por Supervisor.

[OBSERVED] GUI TaskOrchestrator permanece operativo hoy para quick actions y no se elimina en esta fase.

[OBSERVED] TaskOrchestrator puede ejecutar `bot_ia.core.web_queue.WebQueueManager` sin pasar por `TaskScheduler` ni por `WEB_MESA_UNICA` de `services.web_queue`.

[OBSERVED] El camino TaskEngine/Scheduler utiliza `services.web_queue.WebChatQueueManager`, cuyo recurso `WEB_MESA_UNICA` sólo coordina instancias de ese módulo; no constituye un lock entre ambos runtimes.

[INFERRED] Existe riesgo real de concurrencia/ownership sobre la misma waitress lógica porque quick actions usan `cari`/ `sunna` y el chat Web GUI puede seleccionar esas mismas waitresses. No se demostró que compartan la misma cuenta, navegador o sesión web; por tanto esas dimensiones permanecen UNKNOWN.

[OBSERVED] El historial muestra que TaskOrchestrator fue creado el 2026-09-24, mientras TaskScheduler fue introducido posteriormente el 2026-09-27 y WebChatQueueManager recibió después adaptaciones explícitas para cancelación, estado de circuit breaker y recuperación de capacidad del Scheduler.

[DECIDED] F-006 deja de ser una decisión abierta de ownership: la arquitectura objetivo es una única ruta operacional WebChat basada en TaskEngine/TaskScheduler. La implementación de la convergencia queda para una fase posterior autorizada.

[PROPOSED] En una futura implementación, GUI TaskOrchestrator deberá convertirse en adapter/orquestación de presentación o retirarse gradualmente, pero no se decide aquí el mecanismo exacto de migración.


## FASE 2F-8C — Migration Contract WebChat

- [DECIDED] F-006 permanece resuelto arquitectónicamente como CANDIDATE A: `GUI → TaskEngine → TaskScheduler → WebChatTaskExecutor → services.web_queue.WebChatQueueManager`.
- [PROPOSED] La migración no debe crear otro TaskEngine, Scheduler, executor físico ni cola operacional paralela.
- [OBSERVED] Quick actions actuales: `chocolatada` es una acción local que responde directamente por callback y no llega a WebQueue; `trivia` es una acción WebChat que usa `sunna`, prioridad MEDIUM, timeout de 12 s, fallback del TaskOrchestrator y CircuitBreaker por waitress.
- [PROPOSED] Toda quick action WebChat futura debe recibir un `task_id` generado por TaskEngine y usar `WEB_MESA_UNICA` mediante TaskScheduler; `waitress_id` sólo identifica el destino lógico.
- [PROPOSED] El callback de quick action debe dejar de ser el mecanismo de lifecycle y representar la entrega de un resultado ya aceptado por TaskEngine; la GUI recibe después una notificación de presentación. No se crea un sistema paralelo de eventos.
- [OBSERVED] TaskScheduler no define timeout propio; TaskEngine soporta deadline/timeout_policy y WebChatQueueManager posee timeout físico de ticket. La política futura debe asignar un owner único a cada nivel, evitando que el timeout de 12 s del Orchestrator sea copiado sin justificación.
- [OBSERVED] WebQueueManager Playwright tiene RESPONSE_TIMEOUT_MS=10 s, PAGE_TIMEOUT_MS=15 s, NAVIGATION_TIMEOUT_MS=20 s y soft reset cada 20 interacciones; WebChatQueueManager tiene timeout de ticket configurable, por defecto 45 s, y CircuitBreaker 3 fallos/10 s de cooldown.
- [UNKNOWN] La equivalencia funcional exacta entre Playwright y QWebEngine para capacidades avanzadas del runtime antiguo requiere pruebas de migración; no se presume equivalencia.
- [PROPOSED] La continuidad de login/cookies debe conservar el QWebEngineProfile persistente existente; no se copiarán cookies, storage_state ni credenciales desde Playwright.
- [PROPOSED] La convivencia temporal debe tener un único routing por solicitud; una misma quick action nunca puede ser enviada simultáneamente a TaskOrchestrator y TaskEngine.
- [PROPOSED] La retirada de TaskOrchestrator sólo podrá ocurrir después de demostrar quick actions, cancelación, fallback, WebChat, Taberna, sesión y CI preservados.
- [DECIDED] TaskOrchestrator sigue ACTIVE / MIGRATION PENDING. No es legacy, no fue modificado y no fue eliminado.
- [DECIDED] Esta fase es diseño solamente: no inicia migración física ni FASE 2F-9.


## FASE 2F-8D — MIG-0 Capability Verification

- Estado: [PARTIAL]
- HEAD base: 54ea12ac70a0e9a9ebf461cb691584ee544231cd.
- [OBSERVED] Se verificaron los cuatro protected runtime hashes sin cambios.
- [OBSERVED] Se inventariaron 40 capacidades críticas Playwright/QWebEngine y 20 gates MIG-3.
- [UNKNOWN] La paridad funcional/runtime Playwright ↔ QWebEngine sigue abierta en detección de respuestas, selectors, send protocol, storage/login, counters/soft reset, timeouts, provider behavior y failure propagation.
- [OBSERVED] Quick actions actuales: chocolatada = LOCAL; trivia = WEBCHAT mediante TaskOrchestrator, sin TaskEngine/Scheduler.
- [OBSERVED] TaskOrchestrator sigue ACTIVE / MIGRATION PENDING; no fue modificado ni eliminado.
- [CONFIRMED RISK] El callback de quick action lee _selected_bot_id al completar, en vez de capturar la identidad encolada.
- [BLOCKER] Quick actions WebChat actuales no adquieren WEB_MESA_UNICA mediante TaskScheduler.
- No se añadieron tests de migración ni se ejecutó WebChat real.
- MIG-1..MIG-6: NO iniciados.

## FASE 2F-8E — MIG-3 Gate Closure / technical evidence

- Estado: [PARTIAL]
- Final implementation/test HEAD before memory update: 5fd323ec5026d7221309987a0a9a9a0a2920bfe6.
- [TESTED] Added deterministic MIG-3 evidence for task identity, late responses, cancellation, deadline timeout, executor failure, WEB_MESA_UNICA arbitration, ticket correlation, operation invalidation, breaker recovery and duplicate ticket protection.
- [TESTED] Ubuntu and Windows CI passed after the third and final repair attempt for this phase; 728 tests passed.
- [UNKNOWN] Real-provider response/DOM/selector/send/navigation parity remains unverified.
- [UNKNOWN] Real login/session/cookie/storage continuity, QWebEngine counter/soft-reset parity and provider behavior remain unverified.
- [OBSERVED] Timeout, breaker, duplicate-route and resource policies are heterogeneous between active runtimes.
- [TESTED] The quick-action callback presentation-identity bug is reproducible without external services.
- [DECIDED] The callback bug is recorded only; no runtime repair is made in MIG-3.
- [OBSERVED] F-007 shows multiple clock injection/observation policies; no common clock abstraction is introduced.
- [OBSERVED] F-008 confirms RuntimeObservation currently exposes only pending/active Scheduler snapshots.
- [DECIDED] MIG-1 is not started and migration remains physically uninitiated.

## FASE 2F-8 — Checkpoint histórico de continuidad observado en main (2026-09-30)

> **HISTORICAL — NOT CURRENT MAIN STATE.** Este bloque conserva el estado y la evidencia observados el 30 de septiembre de 2026. Todas las cifras de CI, recuentos de tests y estados 2F-8R/2F-8S que aparecen debajo pertenecen a ese checkpoint y no son resultados actuales.
>
> En ese checkpoint, `1763974f4dc27fb5ea5f66452c0f9b57297aaa76` era el HEAD de `main`; es un HEAD histórico, no el HEAD actual.
>
> `78d5fa6d0b539991aba1ee700121404678c21e59` conserva el significado de `LAST FUNCTIONAL BASELINE` para la línea funcional descrita aquí. No es el HEAD actual de `main`.
>
> **CURRENT MAIN REFERENCE — VERIFIED 2026-10-09 (before this documentation patch):** `main@9b191e578e86a65522cc374bdda24e53d386df37`. Esta referencia actual se registra separadamente y no altera la interpretación de los datos históricos siguientes.

### CONTINUATION POINT

- Branch canónica observada en el checkpoint: `main`.
- HEAD histórico observado en el checkpoint: `1763974f4dc27fb5ea5f66452c0f9b57297aaa76`.
- Parent inmediato histórico: `78d5fa6d0b539991aba1ee700121404678c21e59`.
- LAST FUNCTIONAL BASELINE (histórico): `78d5fa6d0b539991aba1ee700121404678c21e59`.
- Consolidación documental: `1763974f4dc27fb5ea5f66452c0f9b57297aaa76`.
- Base 2F-8R: `2902ac7d019aac4f9d0f35d7ee578d88b1fc334b`.
- HEAD válido previo de 2F-8S: `9feaf5b7d45da388d992df3565a45ee2fb9036d6`.
- `2902 → 9fe → 78d5` es la línea funcional válida; `1763974` es una consolidación documental descendiente de `78d5` y no cambia esa interpretación.

### 2F-8R / 2F-8S

- [TESTED] 2F-8R en `2902`: CI `36611033279` terminó Ubuntu PASS y Windows PASS, con `857 passed` y `violations=0` en ambos.
- [TESTED] `main@1763974` conserva `PhysicalWebChatResourceAuthority`, `PhysicalLifecycleReconciliation`, `WebPhysicalIdentity`, adapters QWeb/Playwright y wiring de runtime/GUI; `78d5` queda identificado como LAST FUNCTIONAL BASELINE.
- [TESTED] `tests/test_production_runtime_lifecycle_8s.py` contiene S01-S13.
- [TESTED] S03 actual implementa `RUNNING + BUSY → TaskEngine.complete() → COMPLETED + BUSY → record_termination() → COMPLETED + AVAILABLE → ALIGNED`.
- [PARTIAL] CI `36631685318` sobre `78d5`: Windows `872 passed`; Ubuntu `863 passed, 9 errors` por `QWebEngine local page did not load` en runtime controlado. Code policy fue PASS en ambos.
- [TESTED] R10 conserva `RUNNING + AVAILABLE → DIVERGED`: release físico no completa por sí solo el lifecycle lógico.

### Autoridad física y reconciliación

```text
TaskEngine → lifecycle lógico
TaskScheduler → scheduling/routing lógico
WebChatTaskExecutor → adaptación lógica → WebChat
PhysicalLifecycleReconciliation → puente y metadata de reconciliación
PhysicalWebChatResourceAuthority → única autoridad física
```

`RuntimeComponents` crea una autoridad física por instancia y la inyecta al reconciliador. GUI/QWeb/Playwright reutilizan esa autoridad. Supervisor continúa fuera de la ownership física.

Estados lógicos: `PENDING`, `RUNNING`, `WAITING`, `INTERRUPTED`, `CANCELLING`, `COMPLETED`, `FAILED`, `TIMED_OUT`, `CANCELLED`, `DISCARDED`.

Estados físicos: `AVAILABLE`, `CLAIMING`, `BUSY`, `CANCELLING`, `RELEASING`, `QUARANTINED`.

Reglas verificadas: `RUNNING + BUSY` puede estar ALIGNED; `RUNNING + AVAILABLE` es DIVERGED; `COMPLETED + BUSY` es DIVERGED; `COMPLETED + AVAILABLE` es ALIGNED. Timeout/cancelación solicitan cancelación física, no release implícito. La terminación requiere evidencia y binding/generation actuales.

### D3 / continuidad Git

`603266bad1cabcd23ab3ec49284e84917a6e1dca` = D3_TEST_ARTIFACT + ORPHANED_TEST_ARTIFACT; su padre real es `48545826ab7ccd6278b7a6dc714a5bf40caf461a` y su diff directo añade `tests/test_production_runtime_lifecycle_8s.py`.

`b6265c7d9c15f94014bb318065d0cf59d07111d5` = D3_TEST_VALIDATION_COMMIT sobre `9feaf5...`; modifica sólo `tests/test_production_runtime_lifecycle_8s.py`. Su contenido S03 coincide con el archivo actual de `main`, pero `b6265` no es ancestro de `78d5`.

Preservar sin modificar:
`archive/2f-8s-d3-orphaned-main` = REF ABSENT / NOT RESOLVABLE; OBJECT `603266bad1cabcd23ab3ec49284e84917a6e1dca` sigue accesible directamente por SHA.
`archive/2f-8s-d3-validation` = REF ABSENT / NOT RESOLVABLE; OBJECT `b6265c7d9c15f94014bb318065d0cf59d07111d5` sigue accesible directamente por SHA.

No hacer merge/cherry-pick/rebase histórico automáticamente.

### KNOWN UNKNOWN

- [UNKNOWN] Autenticación real del principal/provider.
- [UNKNOWN] Ejecución real contra Gemini/ChatGPT/Google.
- [UNKNOWN] Paridad completa de sesión/cookies/storage bajo provider autenticado.
- [UNKNOWN] Evidencia externa de producción.

La configuración productiva mantiene `authentication_state = "UNKNOWN"`; las identidades VERIFIED de tests controlados no constituyen autenticación real.

## HUESO-05 — Registro de cierre verificado en la referencia actual (2026-10-09)

- PR #96 (`HUESO-05: repair legacy service concurrency`) fue integrada en `94757b257e9df0be3886fbaf11d66dd421c2c4e3`.
- El registro arquitectónico posterior está presente en `main@9b191e578e86a65522cc374bdda24e53d386df37`.
- Estado registrado: `CLOSED / VERIFIED REPAIR + PASS` para las líneas H05-L02..L09 y los escenarios efectivamente validados.
- Este cierre no demuestra despliegue en producción, no cierra todas las superficies SQLite del ecosistema y no modifica el estado independiente de HUESO-10.
