# Project Memory — Discoveries

## [TESTED] Observation Core

PR #62 implementa el Observation Core mínimo con modelos de observación/evidencia, observers, verificación, persistencia local y auditoría. FASE 2F-1V confirmó su CI en Ubuntu y Windows.

## [TESTED] Claims sobre EvidenceStore

FASE 2F-2 añadió un ClaimStore que consulta el EvidenceStore existente. Las referencias de evidencia se validan por evidence_id.

Limitación: ClaimStore no constituye una base de datos ni un segundo EvidenceStore.

## [TESTED] Integridad claim → evidence

Un claim con referencias inexistentes no puede obtener confianza VERIFIED. Si la evidencia deja de estar disponible, la validación lo hace observable y la confianza efectiva se presenta como UNKNOWN.

## [TESTED] Scope Lock

ScopeLock representa operaciones READ, WRITE, CREATE, DELETE y EXECUTE, paths permitidos/prohibidos, owner, authorization, expiración y change budget.

## [TESTED] Path containment

La implementación resuelve la ruta contra repository_root y rechaza traversal, rutas absolutas externas y escapes mediante symlink. Las pruebas de FASE 2F-2 cubren estos casos.

## [TESTED] Default deny

Una operación solo se autoriza cuando la operación está explícitamente permitida y la ruta pertenece a un patrón permitido; una operación o ruta prohibida prevalece.

## [OBSERVED] Límite contractual

Scope Lock representa autorización contractual, pero la autoridad física final de escritura permanece fuera de esta fase.

## [UNKNOWN] Conflictos entre claims

El sistema actual no define un estado formal adicional llamado CONFLICT. FASE 2F-2 no inventó ese estado; claims incompatibles permanecen como claims separados y requieren análisis posterior.

## [UNKNOWN] Persistencia de claims

ClaimStore es actualmente un registro en memoria. No existe persistencia independiente de claims implementada en esta fase.

## [UNKNOWN] Autoridad física de escritura

La identidad o mecanismo que autorizará una escritura real continúa abierto para fases posteriores.

## [OBSERVED] Runtimes protegidos

FASE 2F-2 no modificó TaskEngine, TaskScheduler, WebQueue, Telegram, Discord, TCG, TMA ni GUI.

## Fuentes

FASE 2F-2; PR #63; CI `36432587482`; FASE 2F-1V.
