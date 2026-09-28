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

### DEC-011 — Authorization separada de Scope y Execution

- Estado: [DECIDED]
- Origen: FASE 2F-4.
- Decisión: WriteAuthorization es una capa contractual entre ScopeLock y cualquier ejecución futura; no ejecuta ni persiste escrituras.
- Motivo: separar permiso específico de alcance potencial y ejecución física.
- Evidencia: `src/bot_ia/supervisor/authorization.py` y tests de FASE 2F-4.
- Impacto: futuras escrituras deben presentar una autorización válida dentro de un ScopeLock válido.
- No implica: autoridad física definitiva ni integración runtime.
- Fuentes: FASE 2F-4.

### DEC-012 — Hypothesis y Repair como contratos no ejecutores

- Estado: [DECIDED]
- Origen: FASE 2F-5.
- Decisión: Hypothesis, RepairProposal, RepairAttempt, RepairBudget y VerificationResult forman una capa contractual sin escritura física.
- Motivo: preservar la separación OBSERVATION → EVIDENCE → CLAIM → HYPOTHESIS → REPAIR PROPOSAL → AUTHORIZATION → EXECUTION → VERIFICATION.
- Evidencia: src/bot_ia/supervisor/repair.py y tests de FASE 2F-5.
- Impacto: futuras reparaciones deben respetar hipótesis, propuesta, ScopeLock, autorización y presupuesto antes de cualquier ejecución.
- No implica: WriteExecutor, FileWriter, GitWriter, persistencia definitiva ni integración runtime.
- Fuentes: FASE 2F-5.

### DEC-013 — TaskEngine y TaskScheduler como autoridades operacionales únicas

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-6.
- Decisión: TaskEngine conserva la autoridad operacional sobre lifecycle; TaskScheduler conserva scheduling/routing/resource arbitration. Supervisor solo valida/observa mediante `TaskEngineBoundary`.
- Motivo: impedir un segundo TaskEngine o Scheduler y conservar una única fuente de verdad operacional.
- Evidencia: inspección de `src/bot_ia/core/task_engine.py`, `src/bot_ia/core/task_scheduler.py`, `src/bot_ia/supervisor/task_contract.py` y tests de `tests/test_supervisor_taskengine_boundary.py`.
- Impacto: el Task Contract de Supervisor queda como contrato superior/adaptador, no como segundo lifecycle.
- No implica: ejecución, dispatch, cancelación física ni integración automática.
- Fuentes: FASE 2F-6.


### DEC-014 — Runtime Observation es read-only

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-7.
- Decisión: `RuntimeObservation` utiliza exclusivamente snapshots de `TaskEngineBoundary` y registra evidencia mediante el modelo `Evidence` existente.
- Motivo: demostrar comportamiento real sin convertir Supervisor en TaskEngine, Scheduler o executor.
- Evidencia: `src/bot_ia/supervisor/runtime_observation.py` y `tests/test_supervisor_runtime_observation.py`.
- Impacto: lifecycle y scheduling continúan teniendo un único propietario operacional.
- No implica: ejecución física, dispatch desde Supervisor, WebQueue integration ni handoff automático.
