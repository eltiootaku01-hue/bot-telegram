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
