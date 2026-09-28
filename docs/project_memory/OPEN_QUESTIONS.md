# Project Memory — Open Questions

## Compatibilidad Task Contract / TaskEngine

- Estado: [UNKNOWN]
- Pregunta: ¿Cuál será el adapter exacto entre el contrato Supervisor y las reglas operativas del TaskEngine existente?
- Evidencia disponible: ambos modelos fueron inspeccionados.
- Restricción: no modificar TaskEngine durante FASE 2F-3.

## Persistencia de Tasks

- Estado: [UNKNOWN]
- Pregunta: ¿Debe el contrato de tarea adquirir persistencia propia posteriormente?
- Conocido: FASE 2F-3 usa memoria en proceso.

## Enforcement físico de Scope Lock

- Estado: [UNKNOWN]
- La referencia contractual existe; el enforcement físico sigue abierto.

## Autoridad física de escritura

- Estado: [UNKNOWN]
- Continúa abierta y fuera de FASE 2F-3.

## Integración Supervisor → TaskEngine

- Estado: [TESTED]
- FASE 2F-6 implementa únicamente una frontera read-only/contractual `TaskEngineBoundary`.
- [UNKNOWN] No se definió todavía la interfaz futura que entregará solicitudes ALLOWED al lifecycle operacional.

## Integración Supervisor → Scheduler

- Estado: [TESTED]
- FASE 2F-6 puede observar pending/active IDs del Scheduler existente y verifica que comparte la misma instancia de TaskEngine.
- [UNKNOWN] No se implementó entrega de comandos ni selección desde Supervisor.

## Conflictos entre Claims

- Estado: [UNKNOWN]
- No existe estado CONFLICT formal en Claims.

## Integración con AuthorityCore

- Estado: [UNKNOWN]
- Pregunta: ¿Cómo debe adaptarse `AuthorityCore` existente a la autoridad contractual del Supervisor?
- Conocido: `src/bot_ia/security/authority.py` sigue intacto y su alcance actual es identidad/destino/permiso de interfaces remotas.

## Persistencia y auditoría

- Estado: [UNKNOWN]
- Pregunta: ¿Cómo se persistirá y auditará Authorization a través de reinicios o procesos?
- Conocido: FASE 2F-4 no implementa almacenamiento ni revocación persistente.


## Persistencia de Hypothesis/Repair

- Estado: [UNKNOWN]
- Pregunta: ¿Debe Hypothesis/Repair persistirse en el mismo almacenamiento JSONL existente o mediante otra capa futura?
- Conocido: FASE 2F-5 solo mantiene historial contractual de intentos en memoria y no añade una base de datos.
- [UNKNOWN] Auditoría y reconciliación de Hypothesis/Repair entre reinicios/procesos.

## FASE 2F-6 — Boundary operativo

- [UNKNOWN] El mecanismo definitivo para convertir una solicitud contractual aceptada en una llamada operacional al TaskEngine no se implementa todavía.
- [UNKNOWN] La semántica final de BLOCK/REQUEST/CANCEL_REQUEST entre Supervisor y TaskEngine queda pendiente de una futura fase controlada.
- [DECIDED] Esta incertidumbre no justifica modificar TaskEngine ni TaskScheduler en FASE 2F-6.


## FASE 2F-7 — Runtime Observation

- [TESTED] El Supervisor puede observar snapshots del TaskEngine y pending/active IDs del Scheduler sin mutarlos.
- [TESTED] task_id permanece estable en los snapshots observados, incluyendo parent/child.
- [UNKNOWN] No existe todavía una interfaz de handoff operacional desde una decisión contractual ALLOWED hacia TaskEngine/Scheduler.
- [UNKNOWN] No existe todavía autoridad física definida para ejecución desde Supervisor.
- [UNKNOWN] Las transiciones que no están expuestas por el runtime actual no deben inferirse ni fabricarse.


- [TESTED] El escenario WAITING/RESUME requiere respetar la propiedad operacional existente de active registration; no implica una nueva autoridad para Supervisor.


## FASE 2F-8R — Runtime transition causality

- Estado: [UNKNOWN]
- La diferencia entre snapshots puede observarse, pero no existe todavía un mecanismo independiente que pruebe causalidad de una transición.
- Restricción: no convertir RuntimeObservation en executor ni crear una segunda state machine.

## FASE 2F-8R — ScopeLock immutability

- Estado: [TESTED]
- ScopeLock quedó frozen después de creación.
- [UNKNOWN] El enforcement físico del ScopeLock continúa sin implementarse.
