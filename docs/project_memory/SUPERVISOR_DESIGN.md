# Project Memory — Supervisor Design

## Cadena contractual

[DECIDED]

```
Observation
    ↓
Evidence
    ↓
Claims
    ↓
Scope Lock
    ↓
Task Contract
    ↓
State Machine
```

## Task Contract

[DECIDED] El contrato representa identidad, requester, tipo, contexto pequeño, prioridad, estado, timestamps, deadline, timeout policy, parent/child, interrupción, return policy, wait reason, resultado, error y metadata.

[DECIDED] Puede referenciar scope_id, claim_ids y evidence_ids. No copia objetos de EvidenceStore o ClaimStore.

[DECIDED] Prioridad: HIGH / MEDIUM / LOW.

[DECIDED] Wait reasons: WAITING_USER / WAITING_EXTERNAL / WAITING_WEBCHAT / WAITING_TIMER.

[DECIDED] Return policies: RETURN_IF_VALID / DISCARD_PARENT / NO_RETURN.

## State Machine

[DECIDED] Estados terminales: COMPLETED, FAILED, TIMED_OUT, CANCELLED, DISCARDED.

[DECIDED] WAITING exige wait_reason.

[DECIDED] No se permite transición desde estado terminal.

[DECIDED] CANCELLED no vuelve a RUNNING.

[DECIDED] CANCELLING solo continúa a CANCELLED o FAILED.

## Parent / Child

[DECIDED] parent_task_id permite relaciones padre/hijo sin introducir ejecución paralela.

[TESTED] Se rechazan self-parent, parent inexistente, parent terminal y ciclos.

## Late responses

[DECIDED] La respuesta debe identificarse por task_id.

[TESTED] Solo RUNNING y WAITING aceptan respuestas. Terminal/unknown se descartan.

## Scope

[DECIDED] Task referencia ScopeLock existente; no crea permisos paralelos.

## Compatibilidad

[OBSERVED] TaskEngine y TaskScheduler existentes fueron inspeccionados.

[UNKNOWN] El adapter futuro para reconciliar ambos contratos.

[DECIDED] FASE 2F-3 no modifica TaskEngine, TaskScheduler, WebQueue ni runtimes.

## Fuera de alcance

[DECIDED] Sin integración física Supervisor → TaskEngine/Scheduler, sin persistencia de Tasks, sin repair operativo, sin runtime observation, sin verifier independiente completo, sin Character System, Café Otaku ni TCG/TMA fusion.

## Write Authorization

[DECIDED] Authorization responde a la pregunta "¿quién/qué ha autorizado este write específico?" y no sustituye ScopeLock ni ejecuta la operación.

[DECIDED] Los campos críticos son authorization_id, task_id, scope_id, requester, authority, source, operation, target, status, created_at, expires_at, reason, evidence_ids y claim_ids.

[DECIDED] Operaciones reutilizadas de ScopeLock: READ, WRITE, CREATE, DELETE y EXECUTE. No se infieren permisos entre operaciones.

[DECIDED] Una autorización solo es válida dentro del ScopeLock asociado. ScopeLock conserva default deny, forbidden rules, containment y estado.

[DECIDED] AUTHORIZED requiere una validación independiente de authority. La implementación no declara a Supervisor, AuthorityCore, Admin o cualquier otro actor como autoridad física definitiva.

[DECIDED] Expiration se valida en el momento de check; no hay timers.

[DECIDED] Revocation es representable como un nuevo registro REVOKED; no existe servicio persistente de revocación en esta fase.

[DECIDED] Los registros son inmutables. Para cambiar campos críticos se crea otro registro; no se muta el AUTHORIZED existente.

## AuthorityCore

[OBSERVED] `src/bot_ia/security/authority.py` define `AuthorityCore` para identidad, administración, destinos Telegram/Discord y decisiones de acceso remoto.

[DECIDED] FASE 2F-4 no duplica AuthorityCore ni cambia su implementación.

[UNKNOWN] El adapter exacto entre AuthorityCore y la autoridad contractual de escritura.

## Fuera de alcance

[DECIDED] Sin file.write, file.delete, git commit, git push, git merge, subprocess write, database mutation, runtime configuration mutation o cualquier WriteExecutor.

[DECIDED] Sin integración física Supervisor → TaskEngine/Scheduler, WebQueue, Telegram, Discord, TCG, TMA, GUI o ProviderManager.

[DECIDED] Sin persistencia de Authorization ni servicio de revocación.


## Hypothesis / Repair Contract

[DECIDED] Hypothesis no es Claim y no puede elevarse automáticamente a VERIFIED/FACT.

[DECIDED] RepairProposal describe una posible reparación y permanece separada de Authorization. APPROVED no significa EXECUTING ni SUCCEEDED.

[DECIDED] RepairAttempt registra cada intento individual; FAILED no elimina evidencia ni intentos anteriores.

[DECIDED] RepairBudget es un techo contractual: attempts, files, lines, changes, duration y operaciones explícitamente permitidas. No puede ampliar ScopeLock.

[DECIDED] VerificationResult requiere evidencia y se enlaza a repair_id + attempt_id.

[DECIDED] repair_audit_event genera el AuditEvent ya existente para que la capa de persistencia existente pueda registrarlo; no introduce un sistema paralelo.

[DECIDED] No existe WriteExecutor/FileWriter/GitWriter en esta fase.

[UNKNOWN] Persistencia definitiva de Hypothesis/Repair, rollback físico y enforcement runtime permanecen abiertos.

## FASE 2F-6 — Supervisor ↔ TaskEngine / TaskScheduler

[OBSERVED] TaskEngine es la autoridad operacional única del lifecycle. Sus métodos públicos crean y mutan tareas; sus snapshots son copias y no permiten mutación externa del estado interno.

[OBSERVED] TaskScheduler es la autoridad operacional de scheduling: mantiene pending/active, registra rutas/executors, selecciona candidatos, aplica prioridades, recursos y starvation bypass, y despacha al executor.

[OBSERVED] TaskScheduler está ligado a una instancia concreta de TaskEngine; el boundary rechaza combinar instancias diferentes.

[OBSERVED] Supervisor `task_contract.py` contiene una state machine contractual separada. Aunque comparte estados con TaskEngine, existen diferencias de representación y reglas; no debe convertirse en una segunda autoridad operacional.

[DECIDED] `TaskEngineBoundary` es el contrato/adaptador mínimo: observa snapshots, valida identidad/scope/authorization y devuelve una decisión contractual sin ejecutar, despachar, cancelar ni mutar tareas.

[DECIDED] `ALLOWED` significa que la solicitud pasó la frontera contractual y puede ser considerada por una integración futura; no autoriza al Supervisor a ejecutar directamente.

[TESTED] Observation es read-only y no cambia TaskEngine ni Scheduler.

[TESTED] task_id mismatch, unknown task, terminal operational request, scope mismatch y authorization mismatch se bloquean/deniegan de forma fail-closed.

[DECIDED] No se duplica scheduler, lifecycle, WebChat queue, resource arbitration ni executor ownership.

[UNKNOWN] La interfaz futura de handoff desde una solicitud ALLOWED hacia el TaskEngine/Scheduler queda abierta para una fase posterior.

## Fuera de alcance FASE 2F-6

[DECIDED] Sin TaskEngine mutation desde Supervisor, sin Scheduler dispatch desde Supervisor, sin runtime observation residente, sin WebQueue integration, sin ejecución física y sin cambios en TaskEngine/TaskScheduler.


## FASE 2F-7 — Runtime Observation

[OBSERVED] `TaskEngineBoundary.observe_task()` obtiene snapshots desde la instancia real de TaskEngine; no devuelve referencias mutables al estado interno.

[OBSERVED] `TaskEngineBoundary.observe_scheduler()` obtiene únicamente pending/active IDs del Scheduler existente.

[DECIDED] `RuntimeObservation` transforma esos snapshots en `RUNTIME_EVIDENCE` usando el modelo `Evidence` existente. No mantiene cola, lifecycle ni scheduler propios.

[TESTED] La observación no cambia TaskEngine/Scheduler y no provoca dispatch. Las pruebas ejercitan el runtime real con un executor de prueba controlado, sin WebQueue ni ejecución física.

[TESTED] Las inconsistencias de identidad se conservan fail-closed: task desconocido → UNKNOWN como evidencia y BLOCKED en el boundary; mismatch entre snapshots → BLOCKED.

[DECIDED] Runtime Observation no habilita ejecución física ni constituye una segunda autoridad operacional.


[TESTED] La observación de WAITING/RESUME no introduce un comando de ejecución en Supervisor: el test conduce el runtime por las interfaces existentes y `RuntimeObservation` solamente captura snapshots antes/después.


## FASE 2F-8R — Evidence semantics

[DECIDED] Una diferencia before/after de RuntimeObservation es una observación de snapshots, no una prueba causal de una transición.

[TESTED] RuntimeObservation.transition() no puede elevar causalidad mediante transition_source; devuelve OBSERVED salvo UNKNOWN/BLOCKED por las validaciones existentes.

## FASE 2F-8R — ScopeLock immutability

[DECIDED] ScopeLock es immutable después de construcción.

[TESTED] La normalización inicial se realiza durante construcción y los intentos posteriores de modificar campos de alcance son rechazados.

[DECIDED] Authorization continúa siendo inmutable y ScopeLock ahora comparte esa propiedad contractual.

[UNKNOWN] Ninguna de estas garantías constituye enforcement físico de escritura.


## FASE 2F-8A — Ownership reconciliation

[OBSERVED] `TaskScheduler` es la autoridad de scheduling/routing/resource arbitration dentro del runtime TaskEngine, no una autoridad global del repositorio.

[OBSERVED] `GUI TaskOrchestrator` es un orquestador operativo separado del runtime TaskEngine. Mantiene su propia cola async y su propio control de timeout/fallback/circuit breaker.

[CONFLICT] Ambos caminos pueden ejecutar trabajo WebChat en la aplicación GUI: TaskScheduler entrega a `services.web_queue.WebChatQueueManager`; TaskOrchestrator entrega a `bot_ia.core.web_queue.WebQueueManager`. No comparten Task Contract ni identidad de tarea.

[DECIDED] F-006 se mantiene como conflicto de ownership arquitectónico pendiente. No se elimina ni se absorbe TaskOrchestrator en TaskScheduler en esta fase.

[UNKNOWN] El mecanismo definitivo de convergencia, si corresponde, y el recurso físico común entre ambas rutas quedan fuera de evidencia suficiente para decidirse aquí.

## FASE 2F-8A — Handoff

[OBSERVED] `TaskEngineBoundary` expone comandos contractuales `REQUEST`, `BLOCK`, `CANCEL_REQUEST` y decisiones `ALLOWED/BLOCKED/DENIED/UNKNOWN/INVALID`.

[UNKNOWN] No existe un handoff operacional que convierta `ALLOWED` en una llamada a TaskEngine/TaskScheduler. `ALLOWED` no equivale a ejecución.

## FASE 2F-8A — Task identity

[OBSERVED] TaskEngine y TaskContractStore pueden generar ids independientes. El Task Contract permite recibir un id externo, pero no reconcilia automáticamente ese id con TaskEngine.

[UNKNOWN] La interfaz futura para compartir/reconciliar identidad debe definirse antes de cualquier integración de ejecución.

## FASE 2F-8A — AuthorityCore

[OBSERVED] AuthorityCore sigue limitado a identidad, administración y destinos Telegram/Discord. No se modificó.

[UNKNOWN] No existe evidencia suficiente de un adapter AuthorityCore → WriteAuthorization ni de enforcement físico derivado de AuthorityCore.


## FASE 2F-8B — WebChat y Supervisor

[DECIDED] El runtime WebChat objetivo para futura integración operacional es `TaskEngine → TaskScheduler → WebChatQueueManager`.

[OBSERVED] Este camino es el que actualmente posee `task_id`, lifecycle TaskEngine, resource arbitration, dispatch, cancellation y observación mediante `TaskEngineBoundary`/RuntimeObservation.

[OBSERVED] GUI TaskOrchestrator no tiene integración contractual con Supervisor y mantiene una identidad basada en `waitress_id + payload`.

[PROPOSED] Una futura integración deberá entrar por el contrato/boundary de TaskEngine y conservar `task_id` como identidad operacional. No se debe crear una identidad paralela para WebChat.

[PROPOSED] Authorization, ScopeLock y Evidence deberán seguir siendo aplicados/observados por las capas contractuales existentes; esta fase no establece enforcement físico.

[UNKNOWN] El handoff físico futuro entre Supervisor y TaskEngine continúa fuera de alcance.


## FASE 2F-8C — Migration Compatibility Requirements

[DECIDED] La futura ruta WebChat de quick actions debe ser compatible con el modelo ya establecido:

```
GUI request
    ↓
TaskEngine Task (task_id único)
    ↓
TaskEngineBoundary / contractual checks
    ↓
TaskScheduler
    ↓
WebChatTaskExecutor
    ↓
WebChatQueueManager
```

### Task Contract

[PROPOSED] El TaskEngine Task deberá conservar, como mínimo, requester, task_type, target waitress_id en context/metadata, payload de acción, priority, deadline/timeout_policy y route/resource metadata.

[DECIDED] El Supervisor Task Contract no se convierte en segundo TaskEngine. Si se requiere reconciliación contractual, debe existir un adapter explícito que preserve el mismo task_id operacional.

### ScopeLock

[PROPOSED] ScopeLock deberá referirse al mismo task_id de la ejecución futura y limitar explícitamente cualquier operación física que llegue a estar autorizada.

[DECIDED] ScopeLock no debe usarse como sustituto de resource arbitration: `WEB_MESA_UNICA` pertenece al Scheduler/ejecutor.

### Authorization

[PROPOSED] Una autorización futura deberá estar vinculada al mismo task_id, scope_id, operation y target que la operación WebChat.

[DECIDED] Esta fase no implementa enforcement físico ni convierte AuthorityCore en executor.

### RuntimeObservation

[DECIDED] RuntimeObservation sólo observará snapshots/eventos del TaskEngine/Scheduler convergido.

[PROPOSED] La evidencia futura deberá demostrar, como mínimo, identidad task_id estable, ruta WEBCHAT, resource_key WEB_MESA_UNICA, transición de lifecycle y resultado físico correlacionado.

### Boundary / Handoff

[UNKNOWN] El handoff físico Supervisor → TaskEngine/Scheduler permanece abierto.

[DECIDED] Una decisión contractual ALLOWED no equivale a dispatch ni a ejecución.

[DECIDED] No se permite que Supervisor llame directamente a WebChatQueueManager, WebQueueManager o TaskOrchestrator.

### Single-owner requirements

[DECIDED] TaskEngine = lifecycle owner.

[DECIDED] TaskScheduler = scheduling/routing/resource arbitration owner.

[PROPOSED] WebChatTaskExecutor → WebChatQueueManager = physical WebChat execution owner.

[DECIDED] GUI = requester/presentation owner; no lifecycle paralelo.

[DECIDED] No se crea una segunda state machine, scheduler, TaskEngine, executor físico o WebChat resource lock.

