# Project Memory — Supervisor Design

## Estado general

- [TESTED] Observation Core implementado y validado en PR #62.
- [DECIDED] El contrato del Supervisor de FASE 2E define una capa superior de coordinación y verificación.
- [PROPOSED] Las capacidades no implementadas de este documento son diseño de memoria, no especificación final de implementación.

## Autoridad y límites

[DECIDED] El Supervisor puede observar estado, controlar transiciones autorizadas, validar evidencia, validar diffs, ejecutar verificaciones y autorizar escrituras según alcance.

[DECIDED] Por defecto no escribe cualquier archivo directamente, no modifica arquitectura sin autorización, no reemplaza Cerebro/Obrero/TaskEngine, no decide políticas de contenido y no inventa hechos.

## Máquina de estados

[PROPOSED] El contrato de FASE 2E establece conceptualmente:

`INIT → REPO_SCAN → UNDERSTANDING → PLAN → PRECHECK → IMPLEMENT → DIFF_REVIEW → TEST → POSTCHECK → REPORT → CONTINUE/COMPLETE`

Este flujo pertenece al diseño del Supervisor; no implica que todas las transiciones estén implementadas.

## Evidencia y confianza

[DECIDED] Las afirmaciones deben estar respaldadas por evidencia.

[DECIDED] Estados de confianza: VERIFIED, INSPECTED, INFERRED, BLOCKED, UNKNOWN.

[DECIDED] INFERRED no se eleva automáticamente a VERIFIED.

[PROPOSED] Los tipos conceptuales de evidencia incluyen FILE_EVIDENCE, GIT_EVIDENCE, TEST_EVIDENCE, RUNTIME_EVIDENCE, WEB_EVIDENCE y USER_PROVIDED_EVIDENCE.

## Scope Lock y Change Budget

[DECIDED] FASE 2E define Scope Lock con archivos permitidos/prohibidos, operaciones, directorios y change budget.

[DECIDED] El incumplimiento del alcance debe bloquear la operación.

[PROPOSED] Límites conceptuales: max_files, max_lines_added, max_lines_removed, max_commits, max_repair_attempts y max_scope_expansion.

[UNKNOWN] El mecanismo físico definitivo para hacer cumplir esos límites.

## Recursos y reparación

[PROPOSED] El contrato contempla TOKEN_BUDGET, API_CALL_BUDGET, CPU_BUDGET, RAM_BUDGET, TIME_BUDGET, WEB_CALL_BUDGET y REPAIR_BUDGET.

[PROPOSED] El repair loop conceptual es IMPLEMENT → VERIFY → FAIL → ANALYZE → REPAIR → VERIFY, con límite de intentos.

[UNKNOWN] La implementación física de ambos mecanismos.

## Integración con runtimes

[DECIDED] Relación conceptual: Supervisor → TaskEngine → TaskScheduler → Executor.

[DECIDED] Para WebQueue: Supervisor observa/valida; no controla directamente el navegador.

[DECIDED] BOT-IA moderno y TCG/TMA permanecen como runtimes diferenciados mientras la arquitectura siga sin decisión de integración.

[UNKNOWN] Adapter físico Supervisor → TaskEngine.

## Completion y auditoría

[PROPOSED] Completion requiere scope satisfecho, claims verificados, diff verificado, tests verificados, postcheck verificado y blockers resueltos.

[DECIDED] La trazabilidad conceptual debe seguir REQUEST → PLAN → SCOPE → CHANGE → DIFF → TEST → POSTCHECK → REPORT.

## Fuentes

FASE 2E; PR #62; FASE 2F-1V; `README.md`; `docs/ARQUITECTURA.md`.
