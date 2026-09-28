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
