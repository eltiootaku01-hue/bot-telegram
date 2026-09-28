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
