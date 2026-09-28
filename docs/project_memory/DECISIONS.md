# Project Memory — Decisions

### DEC-008 — Task Contract separado del TaskEngine

- Estado: [DECIDED]
- Origen: FASE 2F-3.
- Decisión: implementar el contrato de tarea y su máquina de estados dentro de Supervisor sin sustituir TaskEngine.
- Motivo: preservar una sola autoridad operativa de ciclo de vida.
- Evidencia: implementación `src/bot_ia/supervisor/task_contract.py`; TaskEngine existente inspeccionado.
- Impacto: futuras integraciones requieren adapter explícito.
- No implica: integración física Supervisor → TaskEngine.
- Fuentes: FASE 2F-3.

### DEC-009 — Respuestas tardías por task_id

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-3.
- Decisión: una respuesta se valida exclusivamente contra task_id y el estado actual; UNKNOWN o terminal se descartan.
- Motivo: impedir que una respuesta tardía reactive o contamine otra tarea.
- Evidencia: tests de `TaskContractStore.validate_response`.
- Impacto: una tarea terminal no vuelve a ser RUNNING por una respuesta.
- No implica: transporte o ejecución física de respuestas.
- Fuentes: FASE 2F-3.

### DEC-010 — Scope Lock como referencia

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-3.
- Decisión: Task puede referenciar un ScopeLock existente mediante scope_id; no crea un sistema paralelo de permisos.
- Motivo: reutilización contractual.
- Evidencia: tests de scope reference.
- Impacto: scope_id requiere un ScopeLock válido en esta capa.
- No implica: enforcement físico.
- Fuentes: FASE 2F-3.
