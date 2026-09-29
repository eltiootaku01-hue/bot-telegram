# Project Memory — Discoveries

## [TESTED] Task Contract

El contrato de tarea existe en `src/bot_ia/supervisor/task_contract.py` y contiene modelo, prioridades, estados, wait reasons, return policies, resultados y referencias contractuales.

## [TESTED] State Machine

Las transiciones válidas e inválidas son evaluables mediante `can_transition` y `transition`. Los estados terminales no tienen transiciones salientes.

## [TESTED] Wait reasons

WAITING requiere uno de: WAITING_USER, WAITING_EXTERNAL, WAITING_WEBCHAT o WAITING_TIMER.

## [TESTED] Parent/child

Se rechazan parent inexistente, self-parent, parent terminal y ciclos detectables en la cadena de parent_task_id.

## [TESTED] Late responses

Solo RUNNING y WAITING aceptan respuestas contractualmente. Unknown y terminal se descartan. Adjuntar resultado a una tarea terminal falla.

## [TESTED] Scope reference

Un scope_id no puede introducirse sin un ScopeLock válido. Si se proporciona ScopeLock, su task_id debe coincidir con el task_id de la tarea.

## [OBSERVED] Diferencia con runtime existente

El TaskEngine existente posee reglas operativas adicionales y no debe modificarse en esta fase. La reconciliación mediante adapter permanece pendiente.

## [UNKNOWN] Persistencia

El Task Contract es actualmente un registro en memoria. No existe persistencia independiente de Tasks implementada por esta fase.

## [UNKNOWN] Integración física

No existe todavía integración Supervisor → TaskEngine ni Supervisor → Scheduler.

## [TESTED] Write Authorization

`WriteAuthorization` representa authorization_id, task_id, scope_id, requester, authority, source, operation, target, status, created_at, expires_at, reason, evidence_ids y claim_ids. `check_authorization` no realiza ninguna mutación física.

## [TESTED] Fail-closed authority validation

Un estado AUTHORIZED sin un validador independiente de authority produce DENIED. Una autoridad que no valida independientemente produce DENIED.

## [TESTED] Scope containment

Authorization no puede exceder ScopeLock: target fuera del allowlist, target forbidden, operación no permitida o ScopeLock no activo producen DENIED.

## [TESTED] Immutability and revocation

Los campos críticos del registro son inmutables por dataclass frozen. La revocación devuelve un nuevo registro REVOKED y conserva el registro original intacto.

## [UNKNOWN] Physical write authority

No se estableció quién autentica finalmente a la autoridad física de escritura, cómo se integra AuthorityCore, ni cómo se persiste/audita la autorización entre reinicios.


## [TESTED] FASE 2F-5 — Hypothesis/Repair

- Hypothesis tiene estados PROPOSED, TESTING, SUPPORTED, REFUTED, INCONCLUSIVE, BLOCKED y CLOSED.
- [TESTED] Una hipótesis requiere evidencia para registrar un resultado de prueba y mantiene por separado evidencia de soporte y refutación.
- [TESTED] Confidence.VERIFIED está prohibido para Hypothesis; una hipótesis no se convierte en hecho.
- [TESTED] RepairProposal valida task_id, scope_id, operation y target contra Task/ScopeLock y queda BLOCKED si la propuesta excede el alcance.
- [TESTED] RepairBudget limita attempts, files, lines, changes, duration y conjunto explícito de operaciones.
- [TESTED] RepairAttempt no sobrescribe historial; RepairAttemptLedger exige numeración secuencial.
- [TESTED] VerificationResult exige evidencia.
- [TESTED] AuditEvent existente se reutiliza mediante repair_audit_event; no se crea un segundo AuditStore.

## [OBSERVED] FASE 2F-6 — Runtime ownership

- TaskEngine posee la máquina operativa real y todas las mutaciones de lifecycle.
- TaskScheduler posee la cola pending/active, selección de candidatos, prioridad, recursos y dispatch.
- TaskScheduler referencia una instancia concreta de TaskEngine y no constituye un lifecycle paralelo.
- Supervisor Task Contract contiene una máquina contractual separada, con solapamiento de estados pero diferencias de representación y reglas; no debe convertirse en autoridad operacional.
- El boundary contractual usa snapshots de TaskEngine y observación del Scheduler sin mutar ninguno.

## [TESTED] FASE 2F-6 — Boundary

- `TaskEngineBoundary` conserva task_id como identidad estable.
- ScopeLock con task_id incompatible produce BLOCKED.
- Solicitudes operacionales sobre tareas terminales producen BLOCKED.
- Authorization válida puede pasar el boundary solamente con binding de task/scope/operation/target y autoridad independiente, pero no ejecuta la tarea.
- Una solicitud con operación sin autorización produce DENIED.
- Observar TaskEngine/Scheduler no cambia estado ni despacha tareas.
- Scheduler perteneciente a otro TaskEngine es rechazado al construir el boundary.

## [UNKNOWN] FASE 2F-6

- Interfaz definitiva para entregar una solicitud `ALLOWED` al TaskEngine/Scheduler.
- Cómo se representará una aceptación/rechazo contractual dentro del lifecycle operacional sin duplicar estados.
- Autoridad física de ejecución y su enforcement.


## [OBSERVED] FASE 2F-7 — Runtime real

- TaskEngine expone snapshots copiados y concentra las mutaciones de lifecycle.
- TaskScheduler consulta el mismo TaskEngine, mantiene pending/active y despacha al executor registrado.
- WAITING utiliza las razones USER, EXTERNAL, WEBCHAT y TIMER en el runtime real.
- Cancellation desde Scheduler sincroniza el estado del TaskEngine y solicita cancelación al executor.
- Failure desde executor se sincroniza mediante `fail_from_executor` y libera el registro activo.
- Deadline checking puede llevar una tarea pendiente a TIMED_OUT sin que Supervisor la ejecute.

## [TESTED] FASE 2F-7 — Evidencia de runtime

- Scenario A: PENDING → RUNNING → COMPLETED.
- Scenario B: RUNNING → WAITING → RUNNING.
- Scenario C: RUNNING → CANCELLED.
- Scenario D: RUNNING → FAILED.
- Scenario E: task_id desconocido produce evidencia UNKNOWN y boundary BLOCKED.
- Scenario F: solicitud operacional sobre tarea terminal produce BLOCKED.
- Scenario G: observación no cambia snapshots de TaskEngine ni Scheduler.
- Scenario H: observación de Scheduler no selecciona ni despacha tareas.
- Scenario adicional: deadline expirada produce TIMED_OUT y parent/child conserva task_id estable.

## [UNKNOWN] FASE 2F-7

- No se implementa ni demuestra un handoff de solicitudes contractuales hacia ejecución física.
- No se define todavía la interfaz futura de integración Supervisor → TaskEngine/Scheduler para ejecución.


- [TESTED] En el runtime real, `TaskScheduler.wake()` rechaza una tarea WAITING que todavía figura como activa; la liberación del registro activo ocurre antes del wake.
- [TESTED] Tras modelar ese handoff con las interfaces existentes, WAITING → RUNNING queda observable sin modificar TaskEngine/TaskScheduler.


## [TESTED] FASE 2F-8R — F-001

RuntimeObservation.transition() no dispone de evidencia causal independiente. La reparación degrada el resultado de comparación de snapshots a OBSERVED y marca causal_transition_verified=false. El transition_source queda como metadata contextual.

## [TESTED] FASE 2F-8R — F-002

ScopeLock es inmutable después de construcción. Las operaciones de normalización inicial siguen siendo compatibles con frozen dataclass mediante object.__setattr__. No se creó un sistema de versionado paralelo.

## [UNKNOWN] FASE 2F-8R

La demostración causal de una transición futura requerirá evidencia producida por el runtime real; no se implementa en esta reparación.


## FASE 2F-8A — F-006

- [OBSERVED] `TaskOrchestrator` sólo se define en `src/gui/task_orchestrator.py` y se instancia operativamente desde `src/gui/app.py::_async_main`; sus tests directos están en `tests/test_task_orchestrator.py`.
- [OBSERVED] `TaskScheduler` se construye en `build_runtime()` y también puede ser creado por `WaitressSessionManager` cuando no recibe uno; en la GUI principal el manager de Taberna reutiliza el scheduler del runtime.
- [OBSERVED] `WaitressSessionManager` crea `tavern_chat` con `task_id=ticket_id`, lo registra en TaskScheduler y usa `WEB_MESA_UNICA` como recurso.
- [OBSERVED] La ruta GUI de `_send_web_persona` crea `gui_chat` con `task_id=ticket_id`, lo agenda en TaskScheduler y lo despacha.
- [OBSERVED] La ruta async de quick actions no crea Task ni task_id; encola `QueueItem(waitress_id, payload)` y entrega el payload a un `WebQueueManager` Playwright independiente.
- [OBSERVED] No existe en los componentes auditados un adapter Supervisor → TaskOrchestrator ni Supervisor → WebQueue.
- [OBSERVED] No existe reconciliación automática entre `TaskContractStore` y `TaskEngine`: el contrato genera su propio id si no se suministra uno, mientras TaskEngine también genera el suyo si no se suministra. El contrato permite recibir un `task_id` externo, pero no contiene un mecanismo de descubrimiento/reconciliación con TaskEngine.
- [OBSERVED] `AuthorityCore` representa identidad, administración y destinos autorizados de Telegram/Discord. La autorización contractual del Supervisor usa un `authority_validator` abstracto; no existe un adapter demostrado entre ambos.
- [OBSERVED] `AuthorityCore` no realiza la operación física autorizada; su API devuelve una decisión allow/deny.
- [CONFLICT] F-006 es duplicación operacional acotada de scheduling/orchestration para WebChat dentro de la aplicación GUI, con ownership local distinto y sin integración contractual común.


## FASE 2F-8B — Evidencia para la decisión WebChat

### Responsabilidades

[OBSERVED] TaskScheduler: lifecycle coordinado con TaskEngine, scheduling, prioridades heredadas del Task, resource arbitration, starvation bypass, dispatch, cancellation, response acceptance, failure synchronization y wake/resume.

[OBSERVED] TaskOrchestrator: PriorityQueue async propia, prioridades HIGH/MEDIUM/LOW, worker lifecycle, timeout 12 s, CircuitBreaker por waitress y fallback. No posee TaskEngine lifecycle, resource arbitration común, Task Contract, ScopeLock, Authorization ni Evidence.

[OBSERVED] WebChatQueueManager: cola FIFO en QThread, QTimer de timeout/circuit breaker, cancelación, protocol/DOM monitoring, operation_id, `_WEB_MESA_UNICA` y QWebEngineView.

[OBSERVED] WebQueueManager: pool Playwright async de seis páginas, un browser/contexto, contadores por waitress y soft reset; no posee lock equivalente a `_WEB_MESA_UNICA`.

### Recursos

[OBSERVED] `services.web_queue.WebChatQueueManager` usa el QWebEngineView/perfil persistente de la GUI.

[OBSERVED] `bot_ia.core.web_queue.WebQueueManager` lanza un Chromium propio con Playwright y un BrowserContext nuevo; no recibe `browser_profile`, storage_state ni cookies de la GUI en su constructor.

[UNKNOWN] No existe evidencia de que ambos compartan la misma cuenta autenticada, browser process, BrowserContext, cookies o sesión web.

[OBSERVED] Sí pueden coexistir en el mismo proceso/aplicación: `_async_main` crea WebQueueManager + TaskOrchestrator mientras CommandCenterWindow crea WebChatQueueManager.

### Concurrencia

[OBSERVED] Las quick actions pueden dirigirse a `cari` o `sunna`; el chat Web GUI puede seleccionar cualquier bot de `BOT_MAP`, incluidos esos IDs.

[INFERRED] Por tanto existe un escenario de solapamiento sobre la misma waitress lógica, sin un árbitro compartido entre ambos caminos.

[CONFLICT RESOLVED ARCHITECTURALLY] Esta evidencia impide considerar CANDIDATO B como frontera segura por defecto.

### Historial

[OBSERVED] `TaskOrchestrator` fue introducido por commit `3a571b2e154c` (2026-09-24).

[OBSERVED] `WebQueueManager` Playwright core fue introducido por `20774b4db5` (2026-09-24).

[OBSERVED] `TaskScheduler` fue introducido posteriormente por `9e0d4390ee` (2026-09-27) como routing/resource arbitration.

[OBSERVED] Posteriormente `services.web_queue.py` recibió commits `a71b227522` (scheduler cancellation), `14ad4bc973` (circuit state), `85c508ea5a` (capacity signal) y `3fe425105f` (capacity bridge).

[INFERRED] La secuencia histórica es consistente con una integración/migración progresiva del WebChat hacia TaskScheduler, aunque no demuestra que el TaskOrchestrator haya sido formalmente marcado como legacy.


## FASE 2F-8C — Migration evidence

### Quick Actions

- [OBSERVED] `_quick_action()` routes `chocolatada` and `trivia` to `_schedule_async_quick_action()` whenever TaskOrchestrator is available.
- [OBSERVED] `chocolatada`: caller `CommandCenterWindow._quick_action`; target `cari`; payload marks `is_local_action=true`; priority HIGH; callback is an async GUI callback; no WebChat timeout, fallback or WebQueue execution because TaskOrchestrator returns through the local-action branch.
- [OBSERVED] `trivia`: caller `CommandCenterWindow._quick_action`; target `sunna`; payload contains the prompt "Genera una pregunta rápida de trivia sobre anime."; priority MEDIUM; callback is an async GUI callback; Web timeout is 12 s; failure invokes the TaskOrchestrator fallback for `sunna`; CircuitBreaker is per waitress.
- [OBSERVED] Neither quick action currently creates a TaskEngine Task or task_id. Neither currently uses `WEB_MESA_UNICA`.
- [OBSERVED] TaskOrchestrator exposes no per-item cancellation API; its shutdown stops the worker. Therefore current quick-action cancellation is not equivalent to TaskEngine/Scheduler cancellation.

### Identity

- [OBSERVED] TaskEngine can generate a UUID task_id or accept an explicit one. The migration contract requires generation by TaskEngine for new quick actions.
- [OBSERVED] `ticket_id` is currently reused as task_id in `_send_web_persona` and `WaitressSessionManager`; this is an existing compatibility choice, not a rule that quick actions should use ticket_id.
- [OBSERVED] `session_id` is owned by WaitressSessionManager and persists in active_sessions; `waitress_id` is the logical waitress identity; `operation_id` belongs to WebChatQueueManager's browser/DOM anti-zombie protocol.
- [INFERRED] Future quick actions should not manufacture a ticket/session/operation identifier merely to replace task_id.

### Callback / Result

- [OBSERVED] TaskOrchestrator invokes the supplied callback with response text on local success, circuit-open fallback, worker failure and stop-state fallback; worker exceptions are converted to fallback rather than propagated to the callback.
- [OBSERVED] The quick-action callback reads `self._selected_bot_id` at callback time while the queued request carries a fixed waitress_id. If selection changes before completion, presentation identity can diverge from execution target.
- [PROPOSED] Future TaskEngine result handling should bind presentation to the task's immutable context/target, not to mutable GUI selection at callback time.
- [PROPOSED] Success should become TaskEngine completion/result acceptance followed by GUI notification. Failure should become executor failure → Scheduler synchronization → TaskEngine FAILED → GUI notification. Timeout should become the lifecycle timeout outcome plus physical cancellation/cleanup as required. Fallback should be explicit result policy, not a hidden second execution.

### Priority / Timeout

- [OBSERVED] TaskOrchestrator defines HIGH=1, MEDIUM=2, LOW=3. TaskEngine defines the same three constants with the same values and validates them.
- [OBSERVED] TaskScheduler consumes TaskEngine.priority and applies candidate ordering/starvation bypass; it does not define a second priority enum.
- [OBSERVED] TaskOrchestrator WEB_TIMEOUT_SECONDS=12.0 is an end-to-end worker wait around its web_worker callback. It is not a TaskEngine deadline and not a WebChatQueueManager timeout.
- [OBSERVED] Playwright WebQueueManager has response/navigation/page timeouts of 10 s/20 s/15 s respectively. WebChatQueueManager's ticket timeout defaults to 45 s. These are different responsibilities and cannot be collapsed by numeric equality.
- [PROPOSED] Future contract should assign deadline/lifecycle timeout to TaskEngine, resource waiting to Scheduler policy, and browser/protocol timeout to WebChatQueueManager; each physical timeout must have one owner.

### Circuit Breaker / Fallback

- [OBSERVED] TaskOrchestrator has a per-waitress CircuitBreaker: 3 failures opens, 30 s recovery; local actions bypass it because they return before circuit evaluation.
- [OBSERVED] WebChatQueueManager has its own physical CircuitBreaker: 3 failures, 10 s cooldown by default; it also exposes `capacity_restored` to TaskScheduler through WebChatTaskExecutor.
- [OBSERVED] WebQueueManager Playwright does not expose a circuit breaker in the inspected implementation.
- [PROPOSED] The target should retain the executor-specific circuit breaker as the physical WebChat availability gate. A separate per-waitress breaker is justified only if a future policy explicitly protects a logical waitress rather than the shared WebChat resource.
- [OBSERVED] TaskOrchestrator fallback text is a presentation response. It does not retry the WebChat operation.
- [PROPOSED] Any future retry that actually re-executes WebChat must remain under TaskEngine/Scheduler identity and lifecycle; no hidden retry path may call the old WebQueue directly.

### Cancellation / Failure

- [OBSERVED] TaskScheduler.cancel() mutates TaskEngine lifecycle and then calls the registered executor.cancel(task_id). WebChatTaskExecutor maps that call to WebChatQueueManager.cancel_ticket(task_id).
- [OBSERVED] WebChatQueueManager cancellation is ticket/task-id based and cancels both current browser operation and queued ticket state.
- [PROPOSED] This existing chain is the intended single cancellation authority for migrated quick actions.
- [OBSERVED] WebChatQueueManager emits ticket_failed and ticket_finished; GUI currently maps failure to Scheduler failure and completion to execution_finished for TaskEngine tasks.
- [PROPOSED] Error propagation should preserve task_id at every boundary and avoid translating an executor error into a new task.

### Resource / Session

- [OBSERVED] TaskScheduler defines `WEBCHAT_RESOURCE = "WEB_MESA_UNICA"` and arbitrates it through one active task per resource.
- [OBSERVED] Quick actions do not currently acquire that resource.
- [OBSERVED] Quick actions do not call WaitressSessionManager, do not create active_sessions and do not use session_id.
- [PROPOSED] A migrated quick action should only create/use a WaitressSessionManager session if its functional semantics actually require a tavern session. The generic WebChat trivia action currently has no demonstrated session dependency, so session_id should remain absent unless a future requirement introduces one.
- [PROPOSED] The future mapping is therefore conditional, not automatic: `Quick Action → waitress_id → optional session_id → TaskEngine task_id`. It must not fabricate a session merely to fit the model.

### WebQueue Migration

| Capability | Async WebQueueManager | WebChatQueueManager | Migration Action |
|---|---|---|---|
| waitress pages | Six Playwright pages, one per waitress | One QWebEngineView/page surface in the inspected GUI path | ADAPT |
| browser contexts | One Playwright BrowserContext | QWebEngineProfile/page lifecycle | REPLACE |
| cookies | Playwright context created without supplied storage_state | Persistent QWebEngineProfile | ADAPT |
| login state | Not demonstrated as shared with GUI | Persistent GUI profile is the current authenticated surface | KEEP/ADAPT |
| interaction counters | Per-waitress counters | No equivalent counter in inspected manager | ADAPT |
| soft reset | Reload/GOTO and counter reset every 20 interactions | No equivalent per-waitress soft-reset contract | ADAPT |
| timeout | 10 s response, 15 s page, 20 s navigation | 45 s ticket timeout by default plus protocol watchdogs | ADAPT |
| circuit breaker | None in inspected Playwright manager | 3 failures / 10 s cooldown by default | KEEP |
| cancellation | No public per-task cancellation API in inspected manager | ticket cancellation by identity | REPLACE |
| queue | Async WebQueue internals | QThread worker FIFO `msg_queue` | REPLACE |
| worker | asyncio/browser pool | QThread worker | REPLACE |
| GUI integration | None; Playwright core | QWebEngineView/QWebChannel/Qt signals | KEEP |
| persistent profile | No supplied profile/storage_state in constructor | QWebEngineProfile persistent storage | KEEP |
| Playwright | Required by old runtime | Not part of target physical path | REMOVE, only after capability parity |
| QWebEngineView | Not used | Core target surface | KEEP |

- [UNKNOWN] Whether six per-waitress Playwright pages provide user-visible behavior that must be preserved after convergence. The target resource is single-use, so parallel page ownership is not automatically a requirement.
- [UNKNOWN] Whether all Playwright selectors/wait conditions can be expressed by the current QWebChannel/DOM monitor protocol for every provider and response shape.
- [UNKNOWN] Whether the old runtime's Gemini-specific DOM semantics are fully represented by `services.web_queue.WebChatQueueManager`.

### Profile / Session

- [OBSERVED] WebChatQueueManager configures the existing QWebEngineProfile with persistent storage and ForcePersistentCookies.
- [OBSERVED] WebQueueManager creates a fresh Playwright BrowserContext and does not receive GUI browser profile/storage_state/cookies in its constructor.
- [UNKNOWN] Cross-runtime cookie/login continuity is not demonstrated and must not be inferred.
- [DECIDED] Migration must not copy credentials, cookies or storage_state. The target should preserve the already authenticated QWebEngineProfile rather than importing Playwright state.

### Double Execution

- [INFERRED] During a temporary migration, a naive dual wiring could send one quick action to both runtimes because both are independently operational.
- [DECIDED] The migration contract therefore requires one routing decision per request, one TaskEngine task_id for the target path, and no shadow execution.


### FASE 2F-8D — MIG-0 Capability Verification

- [OBSERVED] Playwright WebQueueManager crea seis páginas en un BrowserContext, una por waitress_id, y mantiene interaction_counters por waitress.
- [OBSERVED] Playwright define response/page/navigation timeouts de 10/15/20 segundos y soft reset cada 20 interacciones.
- [OBSERVED] WebChatQueueManager usa QWebEngineView/QWebChannel/MutationObserver, ticket timeout de 45 s por defecto, operation_id, cancellation y WEB_MESA_UNICA.
- [OBSERVED] WebChatQueueManager usa QWebEngineProfile persistente con storage/cache y ForcePersistentCookies; el Playwright core queue crea un BrowserContext nuevo y no recibe storage_state/perfil GUI.
- [UNKNOWN] Continuidad de login/cookies/storage entre ambos runtimes.
- [UNKNOWN] Equivalencia funcional de selectors, send protocol, response detection y provider-specific behavior.
- [UNKNOWN] Equivalencia de interaction counters y soft reset.
- [OBSERVED] TaskScheduler tiene WEB_MESA_UNICA y tests de exclusividad; las quick actions actuales lo evitan.
- [CONFIRMED RISK] _schedule_async_quick_action captura self como cierre pero consulta self._selected_bot_id durante completion, por lo que la presentación puede cruzarse si la selección GUI cambia.
- [BLOCKER] No existe evidencia runtime de una quick action migrada atravesando TaskEngine → TaskScheduler → WebChatTaskExecutor → WebChatQueueManager.
