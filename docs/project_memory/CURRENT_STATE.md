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
