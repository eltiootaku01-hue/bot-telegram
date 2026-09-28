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
