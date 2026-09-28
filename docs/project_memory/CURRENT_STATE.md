# Project Memory — Current State

## Epistemic policy

Esta memoria externa conserva únicamente estados con etiqueta epistemológica. Las etiquetas usadas son: [OBSERVED], [TESTED], [DECIDED], [INFERRED], [PROPOSED], [UNKNOWN], [BLOCKED], [USER_PROVIDED].

## Repository

- [OBSERVED] Branch de implementación: `feature/supervisor-claims-scope-lock`.
- [OBSERVED] HEAD base de FASE 2F-2: `2488dbef2037cdc70678ff414a817b48d376bce7`.
- [TESTED] HEAD final de implementación: `cf5a190ca7cdd872ba33554fea3b711f6007e0fb`.
- [OBSERVED] Base/main: `48545826ab7ccd6278b7a6dc714a5bf40caf461a`.

## Supervisor

- [TESTED] FASE 2E definió el contrato del Supervisor por encima de los runtimes existentes.
- [DECIDED] Claims, Evidence y Scope Lock forman una segunda capa contractual sobre Observation Core; no sustituyen Observation Core.
- [DECIDED] Esta fase no implementa planificación autónoma, reparación automática, TaskEngine, Scheduler ni integración runtime.
- [UNKNOWN] La autoridad física definitiva para una escritura real continúa abierta.

## Observation Core

- [TESTED] PR #62 implementó y validó Observation Core.
- [TESTED] CI de FASE 2F-1V: `36392137591` y `36392275545`.
- [TESTED] FASE 2F-2 CI `36432587482`: Ubuntu y Windows completaron compilación, política, imports y suite con éxito.
- [DECIDED] Claims reutiliza `EvidenceStore`; no existe un segundo EvidenceStore.
- [DECIDED] Scope Lock es contractual y no constituye todavía la autoridad física final de escritura.

## Claims

- [TESTED] Existe `Claim`, `ClaimStatus`, `ClaimStore` y `ClaimValidation`.
- [TESTED] Un claim puede enlazarse a evidence IDs existentes y puede detectar referencias ausentes.
- [DECIDED] Un claim no puede recibir confianza `VERIFIED` sin referencias de evidencia existentes.
- [DECIDED] La pérdida posterior de evidencia se hace observable mediante validación y degrada la confianza efectiva a `UNKNOWN`; no modifica silenciosamente el registro histórico.

## Scope Lock

- [TESTED] Existe `ScopeLock` con operaciones READ, WRITE, CREATE, DELETE y EXECUTE.
- [TESTED] Default deny, forbidden paths/operations, containment de rutas, expiración y change budget están representados.
- [DECIDED] Una operación solo queda autorizada si está explícitamente permitida y no está prohibida.
- [TESTED] El containment resuelve rutas contra la raíz del repositorio y rechaza traversal, rutas absolutas externas y escapes mediante symlink.
- [DECIDED] El change budget de esta fase cubre archivos, líneas añadidas/eliminadas, commits y repair attempts; Resource Budget permanece fuera de alcance.

## Arquitectura y runtimes protegidos

- [DECIDED] TaskEngine, TaskScheduler, WebQueue, Telegram, Discord, TCG, TMA y GUI no fueron modificados por FASE 2F-2.
- [DECIDED] No se realizó fusión TCG/TMA.
- [OBSERVED] La separación histórica permanente TCG/TMA continúa sin evidencia suficiente para elevarse a decisión histórica.

## Documentación

- [TESTED] La memoria externa ya existía en `docs/project_memory/` antes de FASE 2F-2.
- [TESTED] FASE 2F-2 actualizó únicamente memoria documental directamente relacionada con el Supervisor: CURRENT_STATE, DECISIONS, DISCOVERIES, OPEN_QUESTIONS, SUPERVISOR_DESIGN y CHANGELOG_MEMORY.

## Fuentes

FASE 2E; FASE 2F-1; FASE 2F-1V; FASE 2F-MEM-W2; FASE 2F-2; PR #62; PR #63; CI `36432587482`; documentación existente del repositorio.
