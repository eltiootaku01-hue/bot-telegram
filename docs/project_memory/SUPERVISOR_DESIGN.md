# Project Memory — Supervisor Design

## Estado general

- [TESTED] Observation Core fue implementado y validado en PR #62.
- [TESTED] Claims y Scope Lock fueron implementados y validados en PR #63, HEAD `cf5a190ca7cdd872ba33554fea3b711f6007e0fb`.
- [DECIDED] Claims y Scope Lock son una capa contractual sobre Observation Core.
- [PROPOSED] Las capacidades posteriores del Supervisor siguen siendo diseño, no implementación.

## Claims

[DECIDED] Un Claim contiene claim_id, statement, status, confidence, evidence_ids, source, timestamps, scope y relaciones opcionales task/parent.

[DECIDED] Estados de claim: OBSERVED, TESTED, INFERRED, UNKNOWN y BLOCKED.

[DECIDED] Confidence reutiliza la semántica existente del Observation Core.

[DECIDED] VERIFIED requiere evidencia existente. La generación de un claim no concede VERIFIED automáticamente.

[DECIDED] La pérdida de evidencia no se ignora: validate/effective_confidence la hacen observable.

## Evidence

[DECIDED] ClaimStore utiliza el EvidenceStore existente mediante evidence_id.

[DECIDED] No se crea un segundo EvidenceStore, DB, vector DB, Redis ni embeddings.

## Scope Lock

[DECIDED] ScopeLock representa task_id, allowed_paths, forbidden_paths, allowed_operations, forbidden_operations, scope_owner, authorization, expires_at y status.

[DECIDED] Operaciones contractuales: READ, WRITE, CREATE, DELETE, EXECUTE.

[DECIDED] Default deny: aquello que no está explícitamente permitido queda denegado.

[DECIDED] Forbidden paths y operations tienen precedencia.

[DECIDED] Path containment resuelve contra repository_root y rechaza traversal, absolute paths externas y symlink escapes.

[DECIDED] ChangeBudget representa max_files_changed, max_lines_added, max_lines_deleted, max_commits y max_repair_attempts.

[UNKNOWN] El enforcement físico de ScopeLock sobre una escritura real.

## Autoridad

[DECIDED] ScopeLock representa owner y authorization como contrato.

[UNKNOWN] Quién posee la autoridad física definitiva de escritura.

[PROPOSED] FASE 2F-4 puede abordar la autoridad física, si el contrato futuro permanece vigente.

## Integración

[DECIDED] ObservationCore continúa siendo la capa de observación/evidencia.

[DECIDED] Claims y ScopeLock agregan semántica contractual sin invertir la autoridad.

[UNKNOWN] Adapter físico Supervisor → TaskEngine.

## Fuera de alcance

[DECIDED] No se implementaron planificación autónoma completa, repair loop operativo, TaskEngine, Scheduler, runtime integration, Character System, Café Otaku, personajes vivos, percepción diegética, economía ni fusión TCG/TMA.

## Fuentes

FASE 2E; FASE 2F-1V; FASE 2F-2; PR #62; PR #63; CI `36432587482`.
