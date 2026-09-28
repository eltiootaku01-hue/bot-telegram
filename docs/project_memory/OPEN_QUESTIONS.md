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
