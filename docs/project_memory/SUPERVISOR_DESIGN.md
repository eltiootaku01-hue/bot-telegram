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

## Fuera de alcance FASE 2F-5

[DECIDED] Sin escritura de archivos, git commit/push/merge, DB mutation, runtime config mutation, TaskEngine, TaskScheduler, WebQueue, Telegram, Discord, TCG, TMA, GUI o AuthorityCore.
