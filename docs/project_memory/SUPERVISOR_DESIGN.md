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
