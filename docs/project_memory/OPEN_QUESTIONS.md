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

- Estado: [UNKNOWN]
- No se implementó adapter en esta fase.

## Integración Supervisor → Scheduler

- Estado: [UNKNOWN]
- No se implementó integración ni un segundo scheduler.

## Conflictos entre Claims

- Estado: [UNKNOWN]
- No existe estado CONFLICT formal en Claims.
